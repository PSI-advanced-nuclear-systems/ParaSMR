"""
Assembly and validation workflow for reactor components.

UNITS: Geometry is UNIT-AGNOSTIC — choose one consistent unit system for all
inputs (metres, millimetres, ...). Units exist in exactly one place: the
optional `units=` argument of assemble_objects() when exporting, which sets
the STEP file's length-unit declaration so the file means what the spec
meant (previously OCCT silently declared millimetres regardless of input).
Omitting it falls back to metres — the convention used throughout this
repo — with a warning, so a spec written in other units is exported
correctly by passing units= explicitly.

Key features:
  • Resolver integration: automatically applies connection rules to compute
    component placement (center_coords, rotation_angles) from geometry
  • Auto-hole generation: generates reactor_top_plate holes for components
    that pass through it (IHX, pumps, above-core structure)
  • Geometry validation: checks each component builds successfully and has
    non-zero volume
  • STEP export: writes meaningful part names (obj_id) into exported STEP
    files, with sub-component names where available
"""

import re
from typing import Any, Dict, List, cast
import cadquery as cq
from ocp_vscode import show
import hashlib
import warnings
import math

from utils import insert_into
from component_resolver import resolve
from components_premade import PREMADE_BUILDERS
# Single source of truth for hole layout -> (x, y) centres (cutting,
# merging and validation must always agree):
from components_premade.components_premade_top_plate import _hole_centers


# Keys consumed at assembly/resolver level (viewer color, insert logic,
# overlap whitelisting, resolver opt-out, auto-hole config, materials).
# They are stripped from spec copies before dispatch to build_solid — as
# keyword arguments they would crash profile-based specs with
# "unexpected keyword argument". Single definition, used by BOTH
# validate_solids and assemble_objects so the two can never drift apart.
#
# The second row is read by the homogeniser (homogenise_solid.py /
# homogenise.py), which takes the very same spec list this function
# does. Premade and primitive specs survive an unknown key regardless — those
# branches pass the dict positionally — but profile-based specs are expanded
# with **, so a spec carrying them must have them stripped here or it raises.
_ASSEMBLY_LEVEL_KEYS = (
    "insert_into", "material", "material_tag",
    "materials", "filler",
    "hom_cylinder", "neutronics_treatment",
    "color", "interfaces_with", "manual_placement",
    "auto_hole", "hole_diameter",
)

# STEP length-unit codes accepted by the OCCT writer, keyed by the
# user-facing `units=` argument of assemble_objects().
_STEP_UNITS = {
    "m": "M", "mm": "MM", "cm": "CM", "um": "UM", "km": "KM",
    "inch": "INCH", "ft": "FT",
}

# Assumed when a caller exports without naming its units: metres, the
# convention every example and the resolver's defaults are written in.
_DEFAULT_STEP_UNITS = "m"


def _color_from_id(obj_id: str) -> cq.Color:
    """Deterministic pleasant color from obj_id string."""
    h = int(hashlib.md5(obj_id.encode()).hexdigest(), 16)
    r = ((h >> 16) & 0xFF) / 255
    g = ((h >> 8)  & 0xFF) / 255
    b = (h         & 0xFF) / 255
    r = 0.3 + r * 0.6
    g = 0.3 + g * 0.6
    b = 0.3 + b * 0.6
    return cq.Color(r, g, b)  


def _patch_step_names(
    step_path: str,
    obj_ids: List[str],
    subnames_per_obj: Dict[str, List[str]] | None = None,
) -> None:
    """
    Replace generic OCCT PRODUCT names in a STEP file with obj_id names.

    CadQuery's STEP exporter uses the OCCT writer, which generates names like:
        'Open CASCADE STEP translator X.Y 1.N'           — top-level component N
        'Open CASCADE STEP translator X.Y 1.N.1.K'       — Kth child of comp N
        'Open CASCADE STEP translator X.Y 1.N.1.K.M'     — deeper nesting

    Naming strategy:
      • Top-level part N → obj_ids[N-1]      (e.g. "rpv", "ihx_1", "pump_1")
      • First-level child K of component N:
          - If obj_ids[N-1] has subnames in subnames_per_obj, use
            "{parent_obj_id}_{subnames_per_obj[parent][K-1]}"
            (e.g. "ihx_1_tube_bundle", "ihx_2_tube_bundle", ...) so multiple
            instances of the same compound type (e.g. three IHX) get
            distinguishable per-instance sub-part names.
          - Otherwise, the sub-part inherits the parent name.
      • Deeper levels: inherit the parent's resolved name (clean Onshape view)

    Args:
        step_path:          path to the already-exported STEP file.
        obj_ids:            list of obj_id strings, in assembly order.
        subnames_per_obj:   for components that expose sub-parts via a sidecar
                            attribute (e.g. `_ihx_subnames`), this dict maps
                            obj_id → list of sub-part names. Used to give
                            meaningful, instance-prefixed names to compound
                            children.
                            NOTE: currently always None/empty — the call site
                            in assemble_objects() is commented out because
                            every builder fuses its internals into a single
                            solid, so components have no compound children.
                            Unexpected children still inherit the parent name.
    """
    subnames_per_obj = subnames_per_obj or {}

    with open(step_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Capture: group(1) = N (top-level index), group(2) = K (first child) or None,
    # group(3) = trailing dotted suffix or None.
    pattern = re.compile(
        r"'Open CASCADE STEP translator [\d.]+ 1\.(\d+)(?:\.\d+\.(\d+))?(\.[\d.]+)?'"
    )

    def replace_match(match: re.Match) -> str:
        n = int(match.group(1)) - 1   # top-level (0-based)
        if not (0 <= n < len(obj_ids)):
            return match.group(0)

        parent_name = obj_ids[n]
        k_str = match.group(2)
        if k_str is None:
            # Top-level part name itself
            return f"'{parent_name}'"

        # First-level child of a compound component
        k = int(k_str) - 1
        subnames = subnames_per_obj.get(parent_name, [])
        if 0 <= k < len(subnames):
            # Prefix sub-part with parent obj_id so 3 IHX produce names like
            # ihx_1_tube_bundle, ihx_2_tube_bundle, ihx_3_tube_bundle.
            return f"'{parent_name}_{subnames[k]}'"
        else:
            # No subname available — inherit parent's name
            return f"'{parent_name}'"

    content = pattern.sub(replace_match, content)

    with open(step_path, "w", encoding="utf-8") as f:
        f.write(content)



_PLATE_PIERCING_TYPES = ("above_core_structure", "ihx", "primary_pump")


def _component_plate_xy(comp: Dict[str, Any]):
    """Nominal (x, y) of a component's axis at the top plate.

    ACS: always on the reactor axis. IHX/pump: from at_radius/at_angle_deg
    (mode 1) or from center_coords (mode 2 - origin-based placement, so its
    XY IS the axis position). None if the position cannot be determined."""
    if comp.get("obj_type") == "above_core_structure":
        return (0.0, 0.0)
    if "at_radius" in comp and "at_angle_deg" in comp:
        rad = math.radians(comp["at_angle_deg"])
        return (comp["at_radius"] * math.cos(rad),
                comp["at_radius"] * math.sin(rad))
    if "center_coords" in comp:
        cc = comp["center_coords"]
        return (float(cc[0]), float(cc[1]))
    return None


def _component_plate_diameter(comp: Dict[str, Any]):
    """Outer diameter of the component where it pierces the top plate.
    None = this component type does not require a hole."""
    obj_type = comp.get("obj_type")
    if obj_type == "ihx":
        inner_r = comp.get("bundle_shell_inner_radius")
        wall_t  = comp.get("bundle_shell_wall")
        if inner_r is None or wall_t is None:
            raise ValueError(
                f"IHX '{comp.get('obj_id')}' missing required dimensions for "
                f"hole sizing: 'bundle_shell_inner_radius' and 'bundle_shell_wall'."
            )
        return 2.0 * (inner_r + wall_t)
    if obj_type == "primary_pump":
        barrel_r = comp.get("barrel_radius")
        if barrel_r is None:
            raise ValueError(
                f"Pump '{comp.get('obj_id')}' missing required dimension "
                f"'barrel_radius' for hole sizing."
            )
        return 2.0 * barrel_r
    if obj_type == "above_core_structure":
        neck_r = comp.get("neck_outer_r")
        return None if neck_r is None else 2.0 * neck_r
    return None


def _compute_hole_for_component(comp: Dict[str, Any]):
    """One auto-hole group (explicit Cartesian position) for a component,
    or None (opted out via auto_hole: false / not a plate-piercing type /
    position unknown)."""
    if comp.get("auto_hole", True) is False:
        return None
    d_comp = _component_plate_diameter(comp)
    if d_comp is None:
        return None
    xy = _component_plate_xy(comp)
    if xy is None:
        return None
    if "hole_diameter" in comp:
        hole_d = float(comp["hole_diameter"])
    else:
        # OLDER VERSION (unit-carrying clearance default):
        # hole_d = d_comp + top_plate.get("auto_hole_clearance", 0.015)
        # Exact fit by design decision: the auto hole diameter equals the
        # component diameter (coincident faces, matching the manual hole
        # groups and the redan-penetration convention). Use the
        # per-component "hole_diameter" override when clearance is wanted.
        hole_d = d_comp
    return {
        "hole_diameter": hole_d,
        "layout": "explicit_positions",
        "positions": [xy],
        "_auto_generated": True,
        "_for_component": comp.get("obj_id"),
        "_component_diameter": d_comp,
    }


def auto_generate_topplate_holes(resolved_dicts: List[Dict[str, Any]]) -> None:
    """Auto-generate top-plate holes for plate-piercing components (IHX,
    pumps, ACS neck) and merge them with the user's hole_groups.

    Two channels, both supported:
      - automatic: one hole per component at its nominal position, sized
        EXACTLY to the component diameter (or the component's
        'hole_diameter' override); disable per component with auto_hole: false.
      - manual: top_plate['hole_groups'] - any layout (symmetric,
        custom_angles, explicit_positions), any number of groups/radii/sizes.

    Merge rule - USER WINS: a user hole whose centre lies within a
    component's footprint claims that component and no auto hole is added;
    a warning fires only if the user hole does not fully contain the
    component. User groups are never modified."""
    top_plate = next((d for d in resolved_dicts
                      if d.get("obj_type") == "reactor_top_plate"), None)
    if top_plate is None:
        return

    user_groups = top_plate.get("hole_groups", [])
    for g_idx, group in enumerate(user_groups):
        if "hole_diameter" not in group:
            raise ValueError(
                f"reactor_top_plate '{top_plate.get('obj_id')}': "
                f"hole_groups[{g_idx}] is missing 'hole_diameter'."
            )

    # Resolve every user hole into Cartesian centres via the same function
    # the cutter uses - all three layouts handled identically.
    user_holes = []                                   # (x, y, diameter)
    for group in user_groups:
        for hx, hy in _hole_centers(group):
            user_holes.append((hx, hy, float(group["hole_diameter"])))

    auto_holes = []
    for comp in resolved_dicts:
        if comp.get("obj_type") not in _PLATE_PIERCING_TYPES:
            continue
        hole = _compute_hole_for_component(comp)
        if hole is None:
            continue
        px, py = hole["positions"][0]
        d_comp = hole["_component_diameter"]

        claimed = None
        for hx, hy, hd in user_holes:
            if math.hypot(hx - px, hy - py) <= d_comp / 2.0:
                claimed = (hx, hy, hd)
                break
        if claimed is not None:
            hx, hy, hd = claimed
            # containment: is the component circle fully inside the user hole?
            if math.hypot(hx - px, hy - py) + d_comp / 2.0 > hd / 2.0 * (1 + 1e-9):
                warnings.warn(
                    f"User hole (diameter {hd:g}) at ({hx:.3f}, {hy:.3f}) claims "
                    f"component '{comp.get('obj_id')}' (diameter {d_comp:g} at "
                    f"({px:.3f}, {py:.3f})) but does not fully contain it - "
                    f"enlarge or recentre the user hole, or remove it to get "
                    f"an auto-generated one.",
                    stacklevel=2,
                )
            continue                    # user wins - no auto hole added
        auto_holes.append(hole)

    top_plate["hole_groups"] = list(user_groups) + auto_holes


def validate_topplate_holes(resolved_dicts: List[Dict[str, Any]]) -> None:
    """Fail loudly if any plate-piercing component lacks a hole that fully
    contains it (correct position AND sufficient diameter). Components whose
    position cannot be determined are skipped with a warning."""
    top_plate = next((d for d in resolved_dicts
                      if d.get("obj_type") == "reactor_top_plate"), None)
    if top_plate is None:
        return

    holes = []                                        # (x, y, diameter)
    for group in top_plate.get("hole_groups", []):
        d = float(group["hole_diameter"])
        for hx, hy in _hole_centers(group):
            holes.append((hx, hy, d))

    errors = []
    for comp in resolved_dicts:
        if comp.get("obj_type") not in _PLATE_PIERCING_TYPES:
            continue
        d_comp = _component_plate_diameter(comp)
        if d_comp is None:
            continue
        xy = _component_plate_xy(comp)
        if xy is None:
            warnings.warn(
                f"Cannot validate top-plate hole for '{comp.get('obj_id')}' - "
                f"no position information (at_radius/at_angle_deg or "
                f"center_coords).",
                stacklevel=2,
            )
            continue
        px, py = xy
        fits = any(
            math.hypot(hx - px, hy - py) + d_comp / 2.0 <= hd / 2.0 * (1 + 1e-9)
            for hx, hy, hd in holes
        )
        if not fits:
            errors.append(
                f"'{comp.get('obj_id')}' at ({px:.3f}, {py:.3f}) needs a hole "
                f"of diameter >= {d_comp:g} fully containing it"
            )
    if errors:
        raise ValueError(
            "TOP_PLATE holes don't cover these components:\n  "
            + "\n  ".join(errors)
        )


def apply_boolean_operations(assembly: cq.Assembly, operations: List[Dict[str, Any]]) -> cq.Assembly:
    """
    Apply Boolean operations between solids in an assembly.

    Parameters
    ----------
    assembly : cq.Assembly
        Assembly containing the solids to operate on.
    operations : list of dict
        Each dict specifies one operation with keys:
          - operation : {"union", "cut", "intersect"}
          - obj1 : str — name of object to modify
          - obj2 : str — name of object to operate with
          - keep_obj2 : bool, default True — retain obj2 in result

    Returns
    -------
    cq.Assembly
        New assembly with Boolean operations applied. Original colors preserved.
    """
    objects = {child.name: child.obj for child in assembly.children}

    for op_spec in operations:
        operation = op_spec["operation"].lower()
        obj1_id   = op_spec["obj1"]
        obj2_id   = op_spec["obj2"]
        keep_obj2 = op_spec.get("keep_obj2", True)

        if obj1_id not in objects or obj2_id not in objects:
            raise ValueError(f"Objects not found in assembly: obj1='{obj1_id}', obj2='{obj2_id}'")

        obj1 = cast(cq.Workplane, objects[obj1_id])
        obj2 = cast(cq.Workplane, objects[obj2_id])

        if operation == "union":
            result = obj1.union(obj2)
        elif operation == "cut":
            result = obj1.cut(obj2)
        elif operation == "intersect":
            result = obj1.intersect(obj2)
        else:
            raise ValueError(f"Unknown operation: '{operation}'. Use 'union', 'cut', or 'intersect'")

        objects[obj1_id] = result
        if not keep_obj2:
            del objects[obj2_id]

    new_assembly = cq.Assembly()
    for obj_id, obj in objects.items():
        original = next((c for c in assembly.children if c.name == obj_id), None)
        color = original.color if original is not None else _color_from_id(obj_id)
        new_assembly.add(obj, name=obj_id, color=color)

    new_assembly._specs = getattr(assembly, "_specs", [])  # type: ignore

    return new_assembly





# ═════════════════════════════════════════════════════════════════════════
#  Active implementation — replaces the commented-out validate_solids +
#  assemble_objects above. Geometry validation now happens INLINE in the
#  build loop (each solid is checked right after it is built), so every
#  component is built exactly ONCE instead of twice.
# ═════════════════════════════════════════════════════════════════════════

def _check_built_solid(solid: cq.Workplane | None, obj_id: str) -> None:
    """
    OCCT validity checks on a freshly built solid — warnings only, never
    blocks. Same checks the old validate_solids pre-pass performed:
      • NULL_SHAPE           — build_solid returned None
      • ZERO_VOLUME          — volume < 1e-9 (collapsed geometry)
      • VOLUME_CHECK_FAILED  — the volume query itself raised
    (BUILD_FAILED is handled at the call site, around build_solid.)
    """
    if solid is None:
        warnings.warn(
            f"[GEOMETRY] [NULL_SHAPE] {obj_id}: build_solid returned None",
            stacklevel=3,
        )
        return
    try:
        vol = solid.val().Volume()  # type: ignore
        if vol < 1e-9:
            warnings.warn(
                f"[GEOMETRY] [ZERO_VOLUME] {obj_id}: Volume = {vol:.2e} "
                f"(collapsed geometry)",
                stacklevel=3,
            )
    except Exception as e:
        warnings.warn(
            f"[GEOMETRY] [VOLUME_CHECK_FAILED] {obj_id}: {e}",
            stacklevel=3,
        )


def assemble_objects(object_specs: List[Dict[str, Any]], export_path: str | None = None,
                     units: str | None = None) -> cq.Assembly:
    """
    Build a list of objects and assemble them.

    Accepts raw component dicts — the resolver and operation defaults are
    applied automatically, so callers only need to define geometry dicts,
    pass them here, and call show() on the result.

    units — OPTIONAL: the unit your spec numbers are in (e.g. "m", "mm",
    "cm"). It is written into the STEP header so the file is physically
    correct; the geometry itself stays unit-agnostic and no numbers are
    rescaled. When exporting without it, metres are assumed (the repo-wide
    convention) and a warning is emitted — pass units= explicitly for a
    spec written in anything else. Viewer-only calls (no export_path)
    ignore units entirely.

    Geometry validation happens INLINE in the build loop: each solid is
    checked (build failure / null shape / zero volume) right after it is
    built, so every component is built exactly once. Issues are printed
    as warnings — they never block the export.

    STEP export: part names (obj_id) are written into the exported STEP
    file.

    NOTE — sub-part naming is currently DISABLED. The `_ihx_subnames`
    sidecar mechanism (per-instance sub-part names like "ihx_1_tube_bundle")
    assumed compound components; today every builder fuses its internals
    into a single solid (required for the neutronics/DAGMC workflow), so no
    builder attaches the attribute and there are no STEP children to name.
    The plumbing is kept commented out below for a potential re-enable.
    """
    from build_3D_solid import build_solid

    for d in object_specs:
        d.setdefault("operation", "primitive")

    # Only premades take part in the connection rules — every rule in the
    # resolver selects its targets by premade obj_type, so profile-based and
    # raw-primitive specs come back from resolve() unchanged. Routing them
    # around it keeps their live CadQuery values intact: resolve() deep-copies,
    # and copy.deepcopy silently downcasts an OCCT shape, so a sweep `path`
    # Wire would return with .wrapped as a generic TopoDS_Shape and fail
    # CadQuery's sweep dispatch further down.
    is_premade = [d.get("obj_type") in PREMADE_BUILDERS for d in object_specs]
    if any(is_premade):
        resolved = iter(resolve([d for d, p in zip(object_specs, is_premade) if p]))
        object_specs = [next(resolved) if p else d
                        for d, p in zip(object_specs, is_premade)]

    auto_generate_topplate_holes(object_specs)
    validate_topplate_holes(object_specs)

    assembly = cq.Assembly()
    objects: Dict[str, cq.Workplane] = {}
    # DISABLED sub-part naming (see docstring note):
    # subnames_per_obj: Dict[str, List[str]] = {}

    for spec in object_specs:
        print(f"  {spec.get('obj_type', spec.get('operation', '?'))}  [{spec.get('obj_id', '')}]")
        spec_copy = spec.copy()
        operation = spec_copy.pop("operation", "primitive")
        for key in _ASSEMBLY_LEVEL_KEYS:
            spec_copy.pop(key, None)

        try:
            if "profile" in spec_copy:
                solid, obj_id = build_solid(operation, **spec_copy)
            elif "obj_type" in spec_copy:
                profile = spec_copy.copy()
                # get, not pop: builders keep obj_id available so their
                # error messages can name the component.
                obj_id            = profile.get("obj_id", None)
                rotation_angles   = profile.pop("rotation_angles", (0, 0, 0))
                center_coords     = profile.pop("center_coords", None)
                center_coords_pol = profile.pop("center_coords_pol", None)
                solid, obj_id = build_solid(operation, profile,
                                            obj_id=obj_id,
                                            rotation_angles=rotation_angles,
                                            center_coords=center_coords,
                                            center_coords_pol=center_coords_pol)
            else:
                solid, obj_id = build_solid(operation, **spec_copy)
        except Exception as e:
            warnings.warn(
                f"[GEOMETRY] [BUILD_FAILED] {spec.get('obj_id', '<unknown>')}: {e}",
                stacklevel=2,
            )
            raise

        # Inline geometry validation — same checks as the old pre-pass,
        # but performed on the solid we just built (no second build).
        _check_built_solid(solid, obj_id)

        # DISABLED sub-part naming: no builder attaches `_ihx_subnames` since
        # create_ihx fuses its internals into one solid (see docstring note).
        # sub = getattr(solid, "_ihx_subnames", None)
        # if sub:
        #     subnames_per_obj[obj_id] = sub

        objects[obj_id] = solid

    # ── insert_into pass ───────────────────────────────────────────────
    for spec in object_specs:
        target_id = spec.get("insert_into")
        if target_id is None:
            continue
        insert_id = spec.get("obj_id")
        if insert_id is None:
            raise ValueError("insert_into: spec is missing 'obj_id'")
        target_ids = [target_id] if isinstance(target_id, str) else target_id
        for tid in target_ids:
            if tid not in objects:
                raise ValueError(f"insert_into: target '{tid}' not found in assembly")
            objects[tid] = insert_into(objects[tid], objects[insert_id])

    # ── Overlap detection ──────────────────────────────────────────────
    intentional_pairs = set()
    for spec in object_specs:
        obj_id = spec.get("obj_id")
        if obj_id is None:
            continue
        # insert_into pairs
        for tid in ([spec["insert_into"]] if isinstance(spec.get("insert_into"), str)
                    else spec.get("insert_into") or []):
            intentional_pairs.add((obj_id, tid))
            intentional_pairs.add((tid, obj_id))
        # interfaces_with pairs — designed touching interfaces (e.g. IHX
        # walls against top-plate hole edges, pump barrel against redan hole)
        for tid in spec.get("interfaces_with", []):
            intentional_pairs.add((obj_id, tid))
            intentional_pairs.add((tid, obj_id))

    overlap_shapes: list[tuple[str, cq.Workplane]] = []
    solid_list = list(objects.items())
    for i in range(len(solid_list)):
        id_i, wp_i = solid_list[i]
        for j in range(i + 1, len(solid_list)):
            id_j, wp_j = solid_list[j]
            if (id_i, id_j) in intentional_pairs:
                continue
            try:
                inter = wp_i.val().intersect(wp_j.val())  # type: ignore
                if not inter.isNull() and inter.Volume() > 1e-4:
                    warnings.warn(
                        f"Overlap detected between '{id_i}' and '{id_j}' "
                        f"(volume ≈ {inter.Volume():.5f} cubic units). ",
                        stacklevel=2,
                    )
                    overlap_shapes.append((
                        f"OVERLAP_{id_i}__{id_j}",
                        cq.Workplane().newObject([inter]),
                    ))
            except Exception:
                pass

    # ── Assemble with deterministic per-component colors ──────────────
    colors = {spec["obj_id"]: spec.get("color") for spec in object_specs if "obj_id" in spec}
    for obj_id, solid in objects.items():
        color_spec = colors.get(obj_id)
        if color_spec is not None:
            if not isinstance(color_spec, (tuple, list)) or len(color_spec) not in (3, 4):
                raise ValueError(
                    f"'{obj_id}' color must be (r, g, b) or (r, g, b, a) with values "
                    f"in 0.0–1.0, got: {color_spec}"
                )
            color = cq.Color(*color_spec)
        else:
            color = _color_from_id(obj_id)
        assembly.add(solid, name=obj_id, color=color)

    assembly._specs = object_specs  # type: ignore

    # ── STEP export (overlap shapes excluded) ──────────────────────────
    if export_path is not None:
        if units is None:
            # The STEP format demands a length-unit declaration, so assume
            # the repo convention rather than blocking the export (before
            # this argument existed, OCCT silently wrote millimetres).
            units = _DEFAULT_STEP_UNITS
            warnings.warn(
                f"assemble_objects: no 'units' given — declaring "
                f"{units!r} in the STEP header. Pass units= "
                "(" + ", ".join(sorted(_STEP_UNITS)) + ") if the spec "
                "numbers are in another unit.",
                stacklevel=2,
            )
        unit_key = str(units).lower()
        if unit_key not in _STEP_UNITS:
            raise ValueError(
                f"assemble_objects: unknown units {units!r}. Accepted: "
                + ", ".join(sorted(_STEP_UNITS)) + "."
            )
        # Declare the unit in the STEP header — numbers are written as-is.
        # Constructing a STEPControl_Writer first registers OCCT's static
        # parameter table (SetCVal_s is a silent no-op before that).
        from OCP.STEPControl import STEPControl_Writer   # type: ignore
        from OCP.Interface import Interface_Static       # type: ignore
        STEPControl_Writer()
        if not Interface_Static.SetCVal_s("write.step.unit", _STEP_UNITS[unit_key]):
            raise RuntimeError(
                f"Could not set the STEP unit {_STEP_UNITS[unit_key]!r} via OCCT."
            )
        import os
        parent = os.path.dirname(export_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        cq.exporters.export(assembly.toCompound(), export_path)
        _patch_step_names(
            export_path,
            list(objects.keys()),
            # DISABLED sub-part naming (see docstring note):
            # subnames_per_obj=subnames_per_obj,
        )
        print(f"Assembly exported to: {export_path}")

    # ── Add overlap solids for viewer only (after STEP export) ─────────
    for overlap_name, overlap_wp in overlap_shapes:
        assembly.add(overlap_wp, name=overlap_name, color=cq.Color(1, 0, 0, 1))

    return assembly
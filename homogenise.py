"""
Assembly-level homogenisation: the neutronics twin of assemble_objects().

Takes the SAME list of component dicts the CAD assembly uses (each extended
with a ``materials`` or ``material`` block) and produces a homogenised model:
the reactor as a set of placed, atom-conserving equivalent cylinders inside a
sodium pool and a native vessel. The model can be

  • turned back into CAD          build_cad(model)  ->  cq.Assembly  (+ STEP)
  • written out as JSON           out_path=...      ->  handed to an OpenMC
                                                        exporter later

UNITS: unit-agnostic, exactly like assemble_objects(). Every length, area and
volume below is in the model's own unit; the homogenisation identity uses only
volume RATIOS, so nothing needs to know what that unit is. A unit is required
in exactly one place — the ``units=`` argument of build_cad(), and only when
exporting STEP, because the file format demands a length declaration. See the
module docstring of homogenise_solid.py for the conservation identity.

Pipeline
────────
  1. resolve(specs)            same resolver as the CAD assembly, so every
                               component lands at the same world position
     auto_generate_topplate_holes(specs)
                               same pre-pass as the CAD assembly, so the top
                               plate is measured WITH its penetrations
  2. per component, by type:
       cylinder (default)      homogenise_solid() -> equivalent cylinder, placed at
                               the resolved position; identical geometries
                               (e.g. 3 IHXs) are built once and reused
       vessel                  reactor_vessel: kept native — annular shell +
                               equivalent flat bottom conserving the CAD
                               steel volume (heads included)
       plate                   reactor_top_plate: kept native — slab minus the
                               penetrating cylinders, steel smeared so the CAD
                               plate volume is conserved
       smear                   redan: steel smeared uniformly into the pool
  3. pool                      vessel interior minus all component cylinders,
                               filled with the pool material + smeared steel
  4. QA                        pairwise cylinder-overlap check, per-component
                               atom balance, volume closure, placement echo

Treatment can be forced per spec with ``"neutronics_treatment":
"cylinder" | "smear" | "skip"``; envelopes resized with ``"hom_cylinder"``.

PLACEMENT: build_solid() rotates a component about its LOCAL ORIGIN and then
translates that origin onto ``center_coords`` (utils.place_origin_at). So a
component's world geometry is its local geometry plus center_coords, and the
equivalent cylinder is placed the same way — see _world_cylinder.
"""

from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import os
import warnings
from typing import Any, Dict, List, Optional

from component_material_zones import MATERIAL_ZONES
from homogenise_solid import (
    FILLER_KEY,
    cylinder_volume,
    generic_zones,
    homogenise_solid,
    homogenise_volumes,
    material_number_densities,
)

# Default treatment per obj_type (override with spec["neutronics_treatment"])
_TREATMENT = {
    "reactor_vessel":    "vessel",
    "reactor_top_plate": "plate",
    "redan":             "smear",
}

# Keys that do not change the homogenisation result — stripped for the
# geometry cache so identical components (3 IHXs, 3 pumps) are built once.
_PLACEMENT_KEYS = {
    "obj_id", "name", "color", "operation", "insert_into", "interfaces_with",
    "at_radius", "at_angle_deg", "center_coords", "center_coords_pol",
    "rotation_angles", "manual_placement", "neutronics_treatment",
}


def _cache_key(spec: Dict[str, Any]) -> str:
    payload = {k: v for k, v in spec.items() if k not in _PLACEMENT_KEYS}
    return hashlib.md5(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


def _treatment(spec: Dict[str, Any]) -> str:
    return spec.get("neutronics_treatment") or _TREATMENT.get(spec["obj_type"], "cylinder")


def _world_cylinder(spec: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, float]:
    """
    Place the local-frame equivalent cylinder at the component's resolved world
    position.

    build_solid() rotates about the LOCAL ORIGIN and then calls
    place_origin_at(solid, center_coords), which is a pure translation. So

        world_point = R(roll, pitch, yaw) · local_point + center_coords

    and for a z-aligned envelope centred on the component's own axis the yaw
    term drops out entirely: rotating about the local origin spins the component
    about that very axis and leaves a circular envelope invariant. Hence the
    world envelope is simply the local envelope translated by center_coords.

    (Roll/pitch tilt the component out of the z direction, which no z-aligned
    cylinder can represent; that case is warned about and placed upright.)
    """
    cyl = result["cylinder"]

    cc = spec.get("center_coords")
    if cc is None and "center_coords_pol" in spec:
        # theta is in RADIANS, exactly as build_solid() reads it. Resolved
        # through the same helper so the CAD and homogenised placements can
        # never drift apart (this once read the angle as degrees, which put a
        # polar-placed component at a different azimuth in the two models).
        from utils import convert_polar_to_cartesian
        cc = convert_polar_to_cartesian(*spec["center_coords_pol"])

    roll, pitch, _yaw = spec.get("rotation_angles", (0.0, 0.0, 0.0))
    if abs(roll) > 1e-9 or abs(pitch) > 1e-9:
        warnings.warn(
            f"{spec.get('obj_id')}: roll/pitch rotation ({roll}, {pitch}) cannot be "
            f"represented by a z-aligned equivalent cylinder — placing it upright anyway."
        )

    off = (0.0, 0.0, 0.0) if cc is None else (float(cc[0]), float(cc[1]), float(cc[2]))
    return {
        "x": off[0], "y": off[1],
        "z_bottom": cyl["z_bottom"] + off[2],
        "height": cyl["height"], "radius": cyl["radius"],
    }


def _z_overlap(a: Dict[str, float], b: Dict[str, float]) -> float:
    return min(a["z_bottom"] + a["height"], b["z_bottom"] + b["height"]) - \
           max(a["z_bottom"], b["z_bottom"])


def _check_overlaps(placed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Pairwise overlap of z-aligned cylinders: axes closer than r1+r2 AND
    intersecting z-ranges. Fix by shrinking an envelope via spec['hom_cylinder']."""
    out = []
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = placed[i]["cylinder"], placed[j]["cylinder"]
            dz = _z_overlap(a, b)
            if dz <= 0:
                continue
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            pen = a["radius"] + b["radius"] - d
            if pen > 1e-9:
                out.append({
                    "pair": [placed[i]["name"], placed[j]["name"]],
                    "radial_penetration": pen,
                    "z_overlap": dz,
                })
    return out


def homogenise_objects(
    specs: List[Dict[str, Any]],
    materials: Optional[Dict[str, Dict[str, Any]]] = None,
    pool: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
    units: Optional[str] = None,
    out_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Homogenise a full reactor spec list (the same one assemble_objects takes)
    into placed equivalent cylinders + pool + native vessel/plate, and
    optionally write the result to ``out_path`` as JSON.

    pool     : {"material": "na_primary"}  (required key: material)
    settings : {"particles": .., "batches": .., "inactive": ..} merged over defaults
    units    : PURE LABEL — the length unit the spec numbers are authored in
               (e.g. "m", "cm"), exactly like assemble_objects()'s ``units=``.
               Nothing is rescaled; the homogenisation stays unit-agnostic (only
               volume ratios are used). It is recorded verbatim in the model's
               ``unit`` field so a downstream reader (e.g. a future OpenMC
               exporter, which requires cm) knows what the geometry lengths mean
               and can convert them. ``None`` leaves the unit unspecified.
               Number densities are ALWAYS atoms/b·cm, independent of this label.
    """
    if materials is None:
        from materials import MATERIALS as materials
    pool = dict(pool or {})
    pool_mat = pool.get("material", "na_primary")

    from component_resolver import resolve
    from assemble import auto_generate_topplate_holes

    resolved = resolve(copy.deepcopy(specs))
    # Same pre-pass the CAD assembly runs: without it the top plate is measured
    # as an unperforated slab and its steel is over-counted by the penetrations.
    auto_generate_topplate_holes(resolved)

    notes: List[str] = []

    # ── classify ────────────────────────────────────────────────────────────
    cylinder_specs, smear_specs = [], []
    vessel_spec = plate_spec = None
    for spec in resolved:
        t = _treatment(spec)
        if t == "skip":
            continue
        if t == "vessel":
            vessel_spec = spec
        elif t == "plate":
            plate_spec = spec
        elif t == "smear":
            smear_specs.append(spec)
        elif t == "cylinder":
            cylinder_specs.append(spec)
        else:
            raise ValueError(f"unknown neutronics_treatment {t!r}")

    if vessel_spec is None:
        raise ValueError("assembly needs exactly one reactor_vessel spec (pool boundary)")

    # ── per-component homogenisation (cache identical geometries) ───────────
    cache: Dict[str, Dict[str, Any]] = {}
    components: List[Dict[str, Any]] = []
    for spec in cylinder_specs:
        key = _cache_key(spec)
        if key not in cache:
            kind = "premade" if spec.get("obj_type") in MATERIAL_ZONES else "generic"
            print(f"  homogenising {str(spec.get('obj_type')):22s} "
                  f"[{spec.get('obj_id')}] ({kind}) ...")
            cache[key] = homogenise_solid(spec, materials)
        else:
            print(f"  reusing      {str(spec.get('obj_type')):22s} "
                  f"[{spec.get('obj_id')}] (identical geometry)")
        res = cache[key]
        worst = max((b["rel_error"] for b in res["balance"].values()), default=0.0)
        components.append({
            "name": spec.get("obj_id", spec["obj_type"]),
            "obj_type": spec["obj_type"],
            "cylinder": _world_cylinder(spec, res),
            "number_densities": res["number_densities"],
            "qa": {
                "worst_rel_atom_error": worst,
                "closure": res["closure"],
                "zones": res["zones"],
                "filler": res["filler"],
                "unfilled": res["unfilled"],
                "by_material": res["by_material"],
                # Atom content V_m * n_m,i contributed by each material, per
                # nuclide. Volumes alone are NOT enough to split a blended cell
                # back into its constituents: a reaction rate follows the atoms,
                # and two materials sharing a nuclide (the primary and secondary
                # sodium of an IHX) hold different numbers of it per unit volume.
                # Summing this over materials reproduces V_cyl * n_hom,i, so it
                # is the same conservation identity the homogenisation uses,
                # reported per source instead of per cell.
                "by_material_atoms": {
                    m: {nuc: v * n for nuc, n
                        in material_number_densities(materials[m]).items()}
                    for m, v in res["by_material"].items()
                },
            },
        })

    overlaps = _check_overlaps(components)
    for ov in overlaps:
        warnings.warn(
            f"equivalent cylinders overlap: {ov['pair']} "
            f"(radial penetration {ov['radial_penetration']:.4g}, "
            f"z overlap {ov['z_overlap']:.4g}). "
            f"Shrink one with spec['hom_cylinder'] = {{'radius': ...}}."
        )

    # ── vessel (native): annulus + equivalent flat bottom ───────────────────
    inner_d = vessel_spec.get("inner_d")
    wall_t = vessel_spec.get("wall_t")
    outer_d = vessel_spec.get("outer_d")
    if inner_d is None:
        inner_d = float(outer_d) - 2.0 * float(wall_t)
    if outer_d is None:
        outer_d = float(inner_d) + 2.0 * float(wall_t)
    r_in, r_out = float(inner_d) / 2.0, float(outer_d) / 2.0
    straight_h = float(vessel_spec.get("straight_h") or vessel_spec.get("height"))

    vessel_mat = _single_material(vessel_spec, "reactor_vessel")
    v_vessel_cad = MATERIAL_ZONES["reactor_vessel"](vessel_spec)["zones"][0].volume

    # pool z-range: deep enough to contain every component cylinder
    z_pool_top = float(plate_spec["z_bottom"]) if plate_spec else straight_h
    z_pool_bot = min([0.0] + [c["cylinder"]["z_bottom"] for c in components])

    v_annulus = math.pi * (r_out**2 - r_in**2) * (straight_h - z_pool_bot)
    t_bottom_eq = (v_vessel_cad - v_annulus) / (math.pi * r_out**2) if r_out > 0 else 0.0
    if t_bottom_eq < 0:
        notes.append(f"vessel: modelled annulus already exceeds CAD steel volume by "
                     f"{-(v_vessel_cad - v_annulus):.4g}; bottom plate clamped to 0.")
        t_bottom_eq = 0.0

    vessel_out = {
        "r_inner": r_in, "r_outer": r_out,
        "z_bottom": z_pool_bot, "z_top": straight_h,
        "bottom_plate_thickness": t_bottom_eq,
        "material": vessel_mat,
        "number_densities": material_number_densities(materials[vessel_mat]),
        "qa": {"cad_steel": v_vessel_cad},
    }

    # ── helper: volume a cylinder takes out of a z-slab of the vessel bore ──
    def _carved(z0: float, z1: float, r_bound: float, warn: bool) -> float:
        v = 0.0
        for c in components:
            cyl = c["cylinder"]
            dz = min(cyl["z_bottom"] + cyl["height"], z1) - max(cyl["z_bottom"], z0)
            if dz <= 0:
                continue
            ax = math.hypot(cyl["x"], cyl["y"])
            if warn and ax + cyl["radius"] > r_bound + 1e-9:
                notes.append(f"{c['name']}: cylinder extends radially past r={r_bound:.4g} "
                             f"(axis {ax:.4g} + r {cyl['radius']:.4g}); carve-out approximated.")
            v += math.pi * cyl["radius"]**2 * dz
        return v

    # ── pool: vessel bore minus cylinders, + smeared steel (redan) ──────────
    v_pool_base = math.pi * r_in**2 * (z_pool_top - z_pool_bot)
    v_pool = v_pool_base - _carved(z_pool_bot, z_pool_top, r_in, warn=True)

    smeared, v_smear_total = [], 0.0
    smear_vols: Dict[str, float] = {}
    for spec in smear_specs:
        zmodel = (MATERIAL_ZONES[spec["obj_type"]](spec)
                  if spec["obj_type"] in MATERIAL_ZONES else generic_zones(spec))
        v = zmodel["zones"][0].volume
        m = _single_material(spec, spec["obj_type"])
        smear_vols[m] = smear_vols.get(m, 0.0) + v
        v_smear_total += v
        smeared.append({"name": spec.get("obj_id"), "material": m, "volume": v})
        print(f"  smearing     {spec['obj_type']:22s} [{spec.get('obj_id')}] into pool "
              f"({v:.4g} of {m})")

    pool_mix = dict(smear_vols)
    pool_mix[pool_mat] = pool_mix.get(pool_mat, 0.0) + (v_pool - v_smear_total)
    pool_hom = homogenise_volumes(pool_mix, materials, v_pool)
    pool_out = {
        "radius": r_in, "z_bottom": z_pool_bot, "z_top": z_pool_top,
        "material": pool_mat,
        "number_densities": pool_hom["number_densities"],
        "volume": v_pool,
        "smeared": smeared,
    }

    # ── top plate (native): slab minus penetrations, steel conserved ────────
    plate_out = None
    if plate_spec is not None:
        r_p = float(plate_spec["outer_d"]) / 2.0
        z_p0 = float(plate_spec["z_bottom"])
        t_p = float(plate_spec["thickness"])
        plate_mat = _single_material(plate_spec, "reactor_top_plate")
        v_plate_cad = MATERIAL_ZONES["reactor_top_plate"](plate_spec)["zones"][0].volume
        v_slab_model = math.pi * r_p**2 * t_p - _carved(z_p0, z_p0 + t_p, r_p, warn=False)
        plate_hom = homogenise_volumes({plate_mat: v_plate_cad}, materials, v_slab_model)
        plate_out = {
            "radius": r_p, "z_bottom": z_p0, "z_top": z_p0 + t_p,
            "material": plate_mat,
            "number_densities": plate_hom["number_densities"],
            "qa": {"cad_steel": v_plate_cad, "model_cell": v_slab_model},
        }

    # ── settings / source ───────────────────────────────────────────────────
    core = next((c for c in components if c["obj_type"] == "reactor_core"), None)
    settings_out = {"particles": 10000, "batches": 50, "inactive": 10}
    settings_out.update(settings or {})
    if core is not None:
        settings_out["source_cylinder"] = core["cylinder"]
    else:
        notes.append("no reactor_core component — source defaults to the origin.")

    model = {
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        # Length unit the geometry is authored in, as declared by the caller
        # (a pure label — nothing was rescaled). None => unspecified. A reader
        # that needs a concrete unit (OpenMC wants cm) converts from this.
        "unit": units,
        "number_density_unit": "atoms/b·cm",
        "components": components,
        "pool": pool_out,
        "vessel": vessel_out,
        "plate": plate_out,
        "settings": settings_out,
        "qa": {
            "overlaps": overlaps,
            "worst_rel_atom_error": max(
                (c["qa"]["worst_rel_atom_error"] for c in components), default=0.0),
            "worst_closure": max(
                (c["qa"]["closure"] for c in components), default=0.0),
            "notes": notes,
        },
    }

    if out_path is not None:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as fh:
            json.dump(model, fh, indent=2)
        print(f"Homogenised model written: {out_path}")

    return model


def _single_material(spec: Dict[str, Any], what: str) -> str:
    """Material of a component the assembly keeps native (vessel/plate/smeared)."""
    if "materials" in spec:
        mats = {k: v for k, v in spec["materials"].items() if k != FILLER_KEY}
        if len(mats) != 1:
            raise KeyError(
                f"{what}: expected exactly one material zone, got {sorted(mats)}."
            )
        return next(iter(mats.values()))
    if "material" in spec:
        return spec["material"]
    raise KeyError(f"{what}: no 'material' or 'materials' assignment on the spec.")


# ─────────────────────────────────────────────────────────────────────────────
# CAD OUTPUT — the homogenised model as buildable geometry
# ─────────────────────────────────────────────────────────────────────────────
def to_cad_specs(model: Dict[str, Any], prefix: str = "hom_") -> List[Dict[str, Any]]:
    """
    The homogenised model as a spec list assemble_objects() can build directly:
    one cylinder primitive per component, the vessel wall as a pipe, and — when
    it has positive thickness — the vessel's equivalent flat bottom as a solid
    disc closing the bore. These cells do not overlap one another, so the CAD
    assembly's own overlap detection acts as an independent check on the
    equivalent-cylinder layout.

    Each spec carries its homogenised composition in "number_densities" for the
    downstream OpenMC export; assemble_objects ignores the key.
    """
    specs: List[Dict[str, Any]] = []
    for c in model["components"]:
        cyl = c["cylinder"]
        specs.append({
            "obj_type": "cylinder",
            "obj_id": f"{prefix}{c['name']}",
            "radius": cyl["radius"],
            "height": cyl["height"],
            "center_coords": (cyl["x"], cyl["y"], cyl["z_bottom"] + cyl["height"] / 2.0),
            "number_densities": c["number_densities"],
        })

    v = model["vessel"]
    specs.append({
        "obj_type": "pipe",
        "obj_id": f"{prefix}vessel",
        "height": v["z_top"] - v["z_bottom"],
        "outer_radius": v["r_outer"],
        "inner_radius": v["r_inner"],
        "center_coords": (0.0, 0.0, (v["z_bottom"] + v["z_top"]) / 2.0),
        "material": v["material"],
        "number_densities": v["number_densities"],
    })
    # Equivalent flat bottom: a solid disc (full outer radius) that closes the
    # bore just below the annular wall and carries the vessel steel the annulus
    # doesn't. Drawn only when it has positive thickness — t_bottom_eq is clamped
    # to 0 when the modelled annulus already accounts for all the CAD steel.
    t_bottom = v.get("bottom_plate_thickness", 0.0)
    if t_bottom > 0.0:
        specs.append({
            "obj_type": "cylinder",
            "obj_id": f"{prefix}vessel_bottom",
            "radius": v["r_outer"],
            "height": t_bottom,
            "center_coords": (0.0, 0.0, v["z_bottom"] - t_bottom / 2.0),
            "material": v["material"],
            "number_densities": v["number_densities"],
        })
    return specs


def _slab_minus_components(model, radius, z0, z1):
    """A z-slab of the given radius with every component cylinder cut out."""
    import cadquery as cq
    solid = (cq.Workplane("XY").workplane(offset=(z0 + z1) / 2.0)
             .cylinder(z1 - z0, radius))
    for c in model["components"]:
        cyl = c["cylinder"]
        dz = min(cyl["z_bottom"] + cyl["height"], z1) - max(cyl["z_bottom"], z0)
        if dz <= 0:
            continue
        zc = (max(cyl["z_bottom"], z0) + min(cyl["z_bottom"] + cyl["height"], z1)) / 2.0
        cutter = (cq.Workplane("XY").workplane(offset=zc)
                  .center(cyl["x"], cyl["y"]).cylinder(dz * 1.001, cyl["radius"]))
        solid = solid.cut(cutter)
    return solid


def build_cad(
    model: Dict[str, Any],
    include_pool: bool = True,
    include_plate: bool = True,
    export_path: Optional[str] = None,
    units: Optional[str] = None,
    prefix: str = "hom_",
):
    """
    Build the homogenised model as a CadQuery assembly: one solid per cell.

    ``units`` is OPTIONAL and means exactly what it means for
    assemble_objects() — the unit the model's numbers are in, written into the
    STEP header. The homogenisation itself never needed it. Omitted, it is taken
    from the model's own ``unit`` field, which homogenise_objects() recorded
    from the caller: the model already knows what it is written in, so the
    export cannot silently disagree with it. Only a model carrying no unit at
    all falls back to the repo convention (metres), with a warning.
    """
    import cadquery as cq
    from assemble import assemble_objects, _color_from_id

    specs = to_cad_specs(model, prefix=prefix)
    assy = assemble_objects(specs, export_path=None)

    if include_pool:
        p = model["pool"]
        pool_solid = _slab_minus_components(model, p["radius"], p["z_bottom"], p["z_top"])
        assy.add(pool_solid, name=f"{prefix}pool", color=cq.Color(0.35, 0.55, 0.85, 0.35))

    if include_plate and model.get("plate"):
        pl = model["plate"]
        plate_solid = _slab_minus_components(model, pl["radius"], pl["z_bottom"], pl["z_top"])
        assy.add(plate_solid, name=f"{prefix}plate", color=_color_from_id("plate"))

    if export_path is not None:
        if units is None:
            # The model records the unit its author declared to
            # homogenise_objects(). Prefer it over any assumed default: it is
            # the only unit the numbers are actually known to be in, and these
            # models are commonly authored in cm (OpenMC's unit), where
            # guessing metres would be wrong by a factor of 100.
            from assemble import _DEFAULT_STEP_UNITS
            units = model.get("unit") or _DEFAULT_STEP_UNITS
            if model.get("unit") is None:
                warnings.warn(
                    f"build_cad: no 'units' given and the model carries no "
                    f"'unit' field — declaring {units!r} in the STEP header. "
                    f"Pass units= if the model numbers are in another unit.",
                    stacklevel=2,
                )
        from assemble import _STEP_UNITS, _patch_step_names
        unit_key = str(units).lower()
        if unit_key not in _STEP_UNITS:
            raise ValueError(f"build_cad: unknown units {units!r}. Accepted: "
                             + ", ".join(sorted(_STEP_UNITS)) + ".")
        from OCP.STEPControl import STEPControl_Writer   # type: ignore
        from OCP.Interface import Interface_Static       # type: ignore
        STEPControl_Writer()
        if not Interface_Static.SetCVal_s("write.step.unit", _STEP_UNITS[unit_key]):
            raise RuntimeError(f"Could not set the STEP unit {_STEP_UNITS[unit_key]!r}.")
        parent = os.path.dirname(export_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        cq.exporters.export(assy.toCompound(), export_path)
        _patch_step_names(export_path, [ch.name for ch in assy.children])
        print(f"Homogenised CAD exported to: {export_path}")

    return assy


# ─────────────────────────────────────────────────────────────────────────────
# QA — independent checks against the real CAD assembly
# ─────────────────────────────────────────────────────────────────────────────
def check_against_cad(model: Dict[str, Any], specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare the homogenised model with the CAD assembly built from the same
    specs. Independent of the numbers the homogeniser produced, so unlike the
    per-nuclide balance (which is true by construction) this can actually fail.

      placement : each equivalent cylinder's z-range vs the real solid's world
                  bounding box — catches any drift in the placement convention
      inventory : total component volume, CAD vs homogenised envelopes
    """
    from assemble import assemble_objects

    assy = assemble_objects(copy.deepcopy(specs), export_path=None)
    cad = {}
    for ch in assy.children:
        try:
            bb = ch.obj.val().BoundingBox()
        except Exception:
            continue
        loc = ch.loc.toTuple()[0] if ch.loc else (0.0, 0.0, 0.0)
        cad[ch.name] = {"z0": bb.zmin + loc[2], "z1": bb.zmax + loc[2],
                        "volume": ch.obj.val().Volume()}

    rows = []
    for c in model["components"]:
        ref = cad.get(c["name"])
        if ref is None:
            continue
        cyl = c["cylinder"]
        rows.append({
            "name": c["name"],
            "cad_z": (ref["z0"], ref["z1"]),
            "cyl_z": (cyl["z_bottom"], cyl["z_bottom"] + cyl["height"]),
            "dz_bottom": cyl["z_bottom"] - ref["z0"],
            "cad_volume": ref["volume"],
            "envelope_volume": cylinder_volume(cyl),
        })
    return {
        "placement": rows,
        "worst_dz_bottom": max((abs(r["dz_bottom"]) for r in rows), default=0.0),
    }


def print_report(model: Dict[str, Any], cad_check: Optional[Dict[str, Any]] = None) -> None:
    """Human-readable summary of a homogenised model."""
    print("\n── homogenised cells " + "─" * 52)
    print(f"{'cell':24s} {'x':>8s} {'y':>8s} {'r':>7s} {'z_bottom':>9s} {'z_top':>9s}")
    for c in model["components"]:
        cy = c["cylinder"]
        print(f"{c['name']:24s} {cy['x']:8.3f} {cy['y']:8.3f} {cy['radius']:7.3f} "
              f"{cy['z_bottom']:9.3f} {cy['z_bottom'] + cy['height']:9.3f}")
    v, p = model["vessel"], model["pool"]
    print(f"{'vessel':24s} {'':8s} {'':8s} {v['r_outer']:7.3f} "
          f"{v['z_bottom']:9.3f} {v['z_top']:9.3f}   (bore {v['r_inner']:.3f}, "
          f"equivalent bottom {v['bottom_plate_thickness']:.4f})")
    print(f"{'pool':24s} {'':8s} {'':8s} {p['radius']:7.3f} "
          f"{p['z_bottom']:9.3f} {p['z_top']:9.3f}   (volume {p['volume']:.4g})")

    print("\n── QA " + "─" * 67)
    q = model["qa"]
    print(f"  overlaps                : {[o['pair'] for o in q['overlaps']] or 'none'}")
    print(f"  worst volume closure    : {q['worst_closure']:.2e}")
    print(f"  worst atom balance      : {q['worst_rel_atom_error']:.2e}  "
          f"(true by construction — see check_against_cad for a real test)")
    if cad_check is not None:
        print(f"  worst placement error   : {cad_check['worst_dz_bottom']:.2e} "
              f"(equivalent cylinder z_bottom vs CAD solid)")
    for n in dict.fromkeys(q["notes"]):
        print(f"  note: {n}")

"""
Homogenise any component into an equivalent cylinder that conserves the
number of atoms of every nuclide.

Three-way separation of concerns
────────────────────────────────
  materials.py                what a material IS        (composition library)
  component_material_zones.py what ZONES a component has (per-component, by obj_type)
  spec["materials"]           which material fills each zone (assignment, by zone name)

UNITS — the tool is UNIT-AGNOSTIC, exactly like assemble_objects(). Geometry is
never converted to centimetres and volumes are never turned into absolute atom
counts. The homogenisation identity is written in terms of volume FRACTIONS::

        n_hom,i  =  Σ_m  (V_m / V_cyl) · n_m,i

V_m / V_cyl is dimensionless, so it does not matter whether the model is in
metres, millimetres or furlongs — as long as one unit is used consistently. The
resulting n_hom,i comes out in the same units as the library's n_m,i
(atoms/b·cm), and conservation holds under any consistent unit choice:

        V_cyl · n_hom,i  ==  Σ_m V_m · n_m,i           (for every nuclide i)

A length unit is needed only when the model is handed to a code that demands
one — the future OpenMC export — which is where assemble_objects() puts it too.

Three build paths
─────────────────
Components reach this module by any of the routes build_solid() supports:

    premade components        obj_type in PREMADE_BUILDERS
    2D profile + operation    spec["profile"] + extrude / revolve / sweep
    CadQuery 3D primitives    obj_type in {cylinder, box, pipe, sphere, ...}

If the obj_type has an entry in MATERIAL_ZONES, that entry decides the zones
(this is how the IHX separates tube-side from shell-side sodium). Otherwise the
component is treated generically: it is built through the very same build_solid()
call the assembler uses, and becomes ONE zone of one material — which is all a
single-material component ever needs. No registration required.

Filler (closure rule)
─────────────────────
The equivalent cylinder is usually larger than the sum of the declared zones.
The remainder ``V_cyl − Σ V_zones`` is the FILLER — in a pool reactor this is
the surrounding sodium, not vacuum. Assign it with the reserved key::

    "materials": {"structure": "ss316", "_filler": "na_primary"}

or, on a single-material component, with the top-level ``"filler"`` key::

    {"obj_type": "cylinder", "material": "ss316", "filler": "na_primary", ...}

If no filler is given the remainder is left as vacuum (reported in the result as
``unfilled``). A negative remainder (zones bigger than the cylinder) is always an
error — enlarge the envelope or fix the zones.

The envelope can be overridden per spec with ``spec["hom_cylinder"]``
(partial dict, e.g. ``{"radius": 2.2}``) — useful to shrink a component's
cylinder so it does not overlap a neighbour; atoms stay conserved.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, Optional

from component_material_zones import MATERIAL_ZONES, Zone

N_A = 6.02214076e23  # Avogadro, atoms / mol

FILLER_KEY = "_filler"   # reserved name in spec["materials"] for the closure material
SOLID_ZONE = "solid"     # zone name used by the generic single-material path

# Keys that carry assembly / homogenisation metadata rather than geometry. They
# are stripped before a spec is handed to build_solid, which would otherwise
# choke on them as unexpected keyword arguments on the profile-based path.
_NON_GEOMETRY_KEYS = (
    "material", "materials", "material_tag", "filler", "hom_cylinder",
    "neutronics_treatment", "color", "insert_into", "interfaces_with",
    "manual_placement", "auto_hole", "hole_diameter",
)


# ─────────────────────────────────────────────────────────────────────────────
# MATERIALS  (pure python)
# ─────────────────────────────────────────────────────────────────────────────
def material_number_densities(mat: Dict[str, Any]) -> Dict[str, float]:
    """
    Per-nuclide number densities in atoms/b·cm. Two accepted forms:

        {"kind": "number_density", "nuclides": {"Fe56": 5.9e-2, ...}}   # atoms/b·cm
        {"kind": "mass_density", "density": 0.85,
         "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}}}                 # g/cm³ + frac
    """
    kind = mat.get("kind", "number_density")
    nucs = mat["nuclides"]
    if kind == "number_density":
        return {k: float(v) for k, v in nucs.items()}
    if kind == "mass_density":
        rho = float(mat["density"])
        ao = {k: float(v["ao"]) for k, v in nucs.items()}
        molar = {k: float(v["M"]) for k, v in nucs.items()}
        tot = sum(ao.values())
        if tot <= 0:
            raise ValueError("atom fractions sum to zero")
        ao = {k: v / tot for k, v in ao.items()}
        m_avg = sum(ao[k] * molar[k] for k in ao)
        n_tot = rho * N_A / m_avg
        return {k: ao[k] * n_tot * 1e-24 for k in ao}
    raise ValueError(f"unknown material kind {kind!r}")


# ─────────────────────────────────────────────────────────────────────────────
# ATOM-CONSERVING HOMOGENISATION  (pure python, unit-agnostic)
# ─────────────────────────────────────────────────────────────────────────────
def homogenise_volumes(
    volume_by_material: Dict[str, float],
    materials: Dict[str, Dict[str, Any]],
    envelope_volume: float,
) -> Dict[str, Any]:
    """
    Mix materials occupying known volumes into one envelope, conserving atoms.

    All volumes are in the model's own length unit cubed; only their RATIO to
    ``envelope_volume`` is ever used, so the result is unit-independent.

    ``balance`` reports, per nuclide, the atom content of the sources versus the
    atom content of the envelope. "Content" here is V·n in model units — it is
    proportional to an atom count by a factor that depends on the length unit,
    which cancels in the comparison.
    """
    if envelope_volume <= 0:
        raise ValueError("envelope volume must be positive")
    n_hom: Dict[str, float] = defaultdict(float)
    source_content: Dict[str, float] = defaultdict(float)
    for mat_name, vol in volume_by_material.items():
        if vol <= 0:
            continue
        if mat_name not in materials:
            raise KeyError(f"material {mat_name!r} used by geometry but absent from library")
        fraction = vol / envelope_volume          # dimensionless — the whole trick
        for nuc, n in material_number_densities(materials[mat_name]).items():
            n_hom[nuc] += fraction * n
            source_content[nuc] += vol * n
    balance: Dict[str, Dict[str, float]] = {}
    for nuc, nd in n_hom.items():
        cell = nd * envelope_volume
        src = source_content[nuc]
        balance[nuc] = {
            "number_density": nd,
            "source_content": src,
            "cell_content": cell,
            "rel_error": abs(cell - src) / src if src else 0.0,
        }
    return {"number_densities": dict(n_hom), "balance": balance}


def cylinder_volume(cyl: Dict[str, Any]) -> float:
    """Volume of an equivalent cylinder, in model units cubed."""
    return math.pi * float(cyl["radius"]) ** 2 * float(cyl["height"])


# ─────────────────────────────────────────────────────────────────────────────
# GENERIC PATH — works for premades, profile+operation and 3D primitives alike
# ─────────────────────────────────────────────────────────────────────────────
def build_local_solid(spec: Dict[str, Any]):
    """
    Build the component in its OWN LOCAL FRAME, through the same build_solid()
    the assembler uses, with placement deliberately withheld.

    Mirrors the dispatch in assemble_objects() so that all three build paths
    produce exactly the solid the CAD assembly would produce, only un-placed:
    build_solid applies rotation about the local origin and then translates the
    origin onto center_coords, so withholding both leaves the local geometry.
    """
    from build_3D_solid import build_solid

    s = {k: v for k, v in spec.items() if k not in _NON_GEOMETRY_KEYS}
    s.pop("center_coords", None)
    s.pop("center_coords_pol", None)
    s.pop("rotation_angles", None)
    operation = s.pop("operation", "primitive")

    if "profile" in s:
        solid, _ = build_solid(operation, **s)
    elif "obj_type" in s:
        solid, _ = build_solid(operation, dict(s), obj_id=s.get("obj_id"))
    else:
        solid, _ = build_solid(operation, **s)
    return solid.val() if hasattr(solid, "val") else solid


def bounding_cylinder(solid, tol: float = 1e-9) -> Dict[str, float]:
    """
    Z-aligned cylinder about the LOCAL ORIGIN that contains the solid.

    The bounding box's corner distance always contains the solid, but for an
    axisymmetric component it is a factor sqrt(2) too wide — which costs
    nothing in atoms yet dilutes the homogenised densities over twice the
    volume they belong in. So try the tighter radius (the largest bounding-box
    extent) first and keep it if a single boolean confirms nothing pokes out.

    Components whose axis is not the local Z axis get a generous envelope from
    this; give them ``spec["hom_cylinder"]`` to tighten it.
    """
    bb = solid.BoundingBox()
    r_corner = max(
        math.hypot(x, y)
        for x in (bb.xmin, bb.xmax)
        for y in (bb.ymin, bb.ymax)
    )
    r_tight = max(abs(bb.xmin), abs(bb.xmax), abs(bb.ymin), abs(bb.ymax))
    height = bb.zmax - bb.zmin
    radius = r_corner
    if r_tight < r_corner - tol and height > 0:
        import cadquery as cq
        probe = (cq.Workplane("XY").workplane(offset=(bb.zmin + bb.zmax) / 2.0)
                 .cylinder(height * 1.01, r_tight).val())
        try:
            if solid.cut(probe).Volume() <= tol * max(solid.Volume(), 1.0):
                radius = r_tight
        except Exception:
            pass  # keep the safe corner radius
    return {"radius": radius, "z_bottom": bb.zmin, "height": height}


def generic_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback zone model for any component without a MATERIAL_ZONES entry: the
    whole solid is one zone, and the envelope is its own bounding cylinder.
    Enough for every single-material component, whatever path built it.
    """
    solid = build_local_solid(spec)
    return {
        "zones": [Zone(SOLID_ZONE, "solid", solid.Volume())],
        "cylinder": bounding_cylinder(solid),
        "solids": {SOLID_ZONE: solid},
    }


def zone_model(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Registered zone declaration if there is one, generic single zone otherwise."""
    obj_type = spec.get("obj_type")
    if obj_type in MATERIAL_ZONES:
        return MATERIAL_ZONES[obj_type](spec)
    return generic_zones(spec)


def _assignment(spec: Dict[str, Any], declared: set) -> Dict[str, Optional[str]]:
    """
    Resolve the zone -> material binding from either form:

        "materials": {"structure": "ss316", "_filler": "na_primary"}   # multi-zone
        "material": "ss316", "filler": "na_primary"                    # single zone
    """
    if "materials" in spec:
        return dict(spec["materials"])
    if "material" in spec:
        if declared != {SOLID_ZONE}:
            raise KeyError(
                f"{spec.get('obj_type')!r} declares zones {sorted(declared)}, so it "
                f"needs a 'materials' block binding each zone to a material; the "
                f"single-material 'material' key is only valid for components with "
                f"one zone."
            )
        out: Dict[str, Optional[str]] = {SOLID_ZONE: spec["material"]}
        if spec.get("filler") is not None:
            out[FILLER_KEY] = spec["filler"]
        return out
    raise KeyError(
        f"{spec.get('obj_id', spec.get('obj_type'))}: no material assignment. Give "
        f"'material' (single-material component) or 'materials' (zone -> material)."
    )


# ─────────────────────────────────────────────────────────────────────────────
# DRIVER
# ─────────────────────────────────────────────────────────────────────────────
def homogenise(
    spec: Dict[str, Any],
    materials: Optional[Dict[str, Dict[str, Any]]] = None,
    cylinder: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build the component described by ``spec``, measure each zone, assign
    materials, and return the equivalent cylinder with conserved per-nuclide
    number densities. Unit-agnostic throughout.

    ``materials`` defaults to the central library in materials.py; pass a dict
    only to override it (e.g. a temperature-perturbed composition set).

    Returns a dict with:
        obj_type          : the component type that was homogenised
        cylinder          : radius / z_bottom / height (model units) + volume
        number_densities  : {nuclide: atoms/b·cm} of the equivalent cylinder
        balance           : per-nuclide source vs cylinder atom content
        zones             : {zone: (role, volume)} as measured from the CAD solid
        by_material       : total volume assigned to each material (incl. filler)
        filler            : closure volume filled by the filler material
        unfilled          : closure volume left as vacuum (no filler given)
        closure           : |Σ zones + filler − V_cyl| / V_cyl, should be ~0
    """
    if materials is None:
        from materials import MATERIALS as materials  # central library default

    model = zone_model(spec)
    zones = model["zones"]
    declared = {z.name for z in zones}

    assign = _assignment(spec, declared)
    filler_mat = assign.pop(FILLER_KEY, None)

    used = set(assign)
    missing = declared - used
    unknown = used - declared
    if missing:
        raise KeyError(
            f"{spec.get('obj_type')}: zones {sorted(missing)} have no material "
            f"assigned. Declared zones: {sorted(declared)}."
        )
    if unknown:
        raise KeyError(
            f"{spec.get('obj_type')}: material assignment names {sorted(unknown)}, "
            f"which are not zones of this component. Valid zone names: {sorted(declared)}."
        )

    by_material: Dict[str, float] = defaultdict(float)
    for z in zones:
        by_material[assign[z.name]] += z.volume

    # Envelope: explicit argument > spec["hom_cylinder"] override > declared default
    cyl = dict(model["cylinder"])
    if spec.get("hom_cylinder"):
        cyl.update(spec["hom_cylinder"])
    if cylinder is not None:
        cyl.update(cylinder)
    v_cyl = cylinder_volume(cyl)
    cyl["volume"] = v_cyl

    # Closure: the remainder of the cylinder is filler (or vacuum if unassigned)
    v_zones = sum(z.volume for z in zones)
    v_rest = v_cyl - v_zones
    if v_rest < -1e-6 * v_cyl:
        raise ValueError(
            f"{spec.get('obj_type')}: declared zones ({v_zones:.6g}) exceed the "
            f"equivalent-cylinder volume ({v_cyl:.6g}). Enlarge the envelope "
            f"(spec['hom_cylinder']) or fix the zone volumes."
        )
    v_rest = max(v_rest, 0.0)
    if filler_mat is not None and v_rest > 0.0:
        by_material[filler_mat] += v_rest

    hom = homogenise_volumes(dict(by_material), materials, v_cyl)
    return {
        "obj_type": spec.get("obj_type"),
        "cylinder": cyl,
        "number_densities": hom["number_densities"],
        "balance": hom["balance"],
        "zones": {z.name: (z.role, z.volume) for z in zones},
        "by_material": dict(by_material),
        "filler": v_rest if filler_mat is not None else 0.0,
        "unfilled": 0.0 if filler_mat is not None else v_rest,
        "closure": abs(sum(by_material.values()) - v_cyl) / v_cyl,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Self-test (pure math — no CadQuery)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    materials = {
        "ss316": {"kind": "number_density",
                  "nuclides": {"Fe56": 5.9e-2, "Cr52": 1.6e-2, "Ni58": 8.0e-3}},
        "na": {"kind": "mass_density", "density": 0.85,
               "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}}},
    }

    hom = homogenise_volumes({"ss316": 1234.0, "na": 8765.0}, materials, 50000.0)
    worst = max(b["rel_error"] for b in hom["balance"].values())
    for nuc, b in hom["balance"].items():
        print(f"  {nuc:6s} n_hom={b['number_density']:.4e}  rel_err={b['rel_error']:.2e}")
    print(f"worst relative atom error: {worst:.2e}")
    assert worst < 1e-12

    # Unit-invariance: scaling every length by k scales every volume by k³ and
    # must leave the homogenised number densities untouched.
    k = 1000.0
    scaled = homogenise_volumes(
        {"ss316": 1234.0 * k**3, "na": 8765.0 * k**3}, materials, 50000.0 * k**3
    )
    drift = max(
        abs(scaled["number_densities"][n] - hom["number_densities"][n])
        / hom["number_densities"][n]
        for n in hom["number_densities"]
    )
    print(f"number-density drift over a {k:g}x unit change: {drift:.2e}")
    assert drift < 1e-12

    print("\nUsage (needs CadQuery + the components package):")
    print("  from materials import MATERIALS")
    print("  result = homogenise(ihx_spec, MATERIALS)   # ihx_spec['obj_type']=='ihx'")

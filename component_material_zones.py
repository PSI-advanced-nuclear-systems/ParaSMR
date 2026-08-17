"""
component_material_zones.py
───────────────────────────
Each premade component declares its MATERIAL ZONES here — analogous to the
connection points in ``component_anchors.py``. A zone is a named region of the
component made of one material: a solid steel part, or a fluid region (a bore,
a cavity, a pool side). The homogeniser asks a component for its zones, measures
each zone's volume, looks up the material the user assigned to that zone name,
and conserves atoms into a single cylinder.

Registration is OPTIONAL. A component with no entry here is homogenised
generically by ``homogenise_solid.generic_zones``: built through the same build_solid()
the assembler uses, treated as one zone of one material, with its own bounding
cylinder as the envelope. That covers every single-material component on all
three build paths (premade, 2D profile + operation, CadQuery 3D primitive). Add
an entry here only when a component has internal structure that ONE material
cannot express — the IHX, whose bundle separates secondary sodium in the tubes
from primary sodium on the shell side, is the motivating case.

Why this lives in its own file (same reasoning as anchors)
──────────────────────────────────────────────────────────
The "what parts does this component have, and how big is each" knowledge is
component-specific. Keeping it out of the generic homogeniser means adding a new
component is a one-function change, and the homogeniser never grows an
``if obj_type == ...`` ladder.

A zone function takes the component's dict and returns::

    {"zones":    [Zone(name, role, volume_model_units3), ...],
     "cylinder": {"radius": R, "z_bottom": z0, "height": H},   # model units
     "solids":   {zone_name: Shape, ...}}                      # optional

``role`` ("solid"/"fluid") is informational to the homogeniser — atom
conservation treats both identically — but the cost report bills only the
"solid" ones, since a bill of materials lists parts to buy and not the coolant
they sit in. Volumes are in the model's own length unit cubed; nothing here
converts units, and nothing downstream does either.

``solids`` hands back the measured solids themselves, for any caller that needs
the shape rather than just its volume.

FRAME: everything a zone function returns is in the component's LOCAL frame —
the frame build_solid() works in before it places the origin at center_coords.
The assembly-level homogeniser translates the envelope by center_coords, so a
zone function must never bake a world position into its cylinder beyond what the
builder itself uses.

The user's component dict assigns a material to each declared zone name::

    "materials": {"structure": "ss316", "tube_side": "na2", "shell_side": "na1"}

Zone names that don't match a declared zone (or declared zones with no material)
raise a clear error in the homogeniser — that is how the binding is checked.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple


@dataclass
class Zone:
    name: str
    role: str       # "solid" | "fluid"  (informational)
    volume: float   # model length-units cubed


# ─────────────────────────────────────────────────────────────────────────────
# Small reusable helpers
# ─────────────────────────────────────────────────────────────────────────────
def _solid_from_premade(spec: Dict[str, Any]):
    """Build the component exactly as the assembly does and return the Shape."""
    from components_premade import build_premade_component
    s = build_premade_component(spec)
    return s.val() if hasattr(s, "val") else s


def _structure_only(solid, cylinder: Dict[str, float]) -> Dict[str, Any]:
    """Zone model of a component that is one lump of steel and nothing else.

    Its surroundings are not its own business: whatever the component does not
    occupy inside the vessel is pool coolant, which the assembly accounts for
    once, globally, rather than component by component.
    """
    return {
        "zones": [Zone("structure", "solid", solid.Volume())],
        "cylinder": cylinder,
        "solids": {"structure": solid},
    }


def _ihx_z_layout(spec: Dict[str, Any]) -> Dict[str, float]:
    z_lp_top = float(spec["lower_plenum_height"])
    z_up_bot = z_lp_top + float(spec["bundle_height"])
    z_up_top = z_up_bot + float(spec["upper_plenum_height"])
    return {"z_lp_top": z_lp_top, "z_up_bot": z_up_bot, "z_up_top": z_up_top}


def _ihx_ring_positions(spec: Dict[str, Any]) -> List[Tuple[float, float, float, float]]:
    """[(x, y, inner_radius, outer_radius), ...] for every tube."""
    out: List[Tuple[float, float, float, float]] = []
    if "tube_rings" in spec:
        for ring in spec["tube_rings"]:
            t_ir = float(ring["inner_radius"])
            t_or = t_ir + float(ring["wall"])
            n = int(ring["n"])
            r = float(ring["pitch_radius"])
            a0 = float(ring.get("start_angle_deg", 0.0))
            for i in range(n):
                a = math.radians(a0 + 360.0 * i / n)
                out.append((r * math.cos(a), r * math.sin(a), t_ir, t_or))
    else:
        t_ir = float(spec["tube_inner_radius"])
        t_or = t_ir + float(spec["tube_wall"])
        positions = spec.get("tube_positions")
        if positions is not None:
            for r, th in positions:
                a = math.radians(th)
                out.append((r * math.cos(a), r * math.sin(a), t_ir, t_or))
        else:
            n = int(spec["n_tubes"])
            r = float(spec["tube_pitch_radius"])
            for i in range(n):
                a = 2 * math.pi * i / n
                out.append((r * math.cos(a), r * math.sin(a), t_ir, t_or))
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  IHX — structure (steel) + tube-side fluid + shell-side fluid
#
#  The only component that genuinely needs a zone declaration: its bundle keeps
#  secondary sodium inside the tubes and primary sodium outside them, within one
#  fused solid. The steel comes from the assembly's own builder; the tube-side
#  region is rebuilt here from the same parameters create_ihx() uses and then cut
#  against that structure — so the two must be kept in step. The closure figure
#  reported by homogenise_solid() is the guard:
#  if this reconstruction drifts from create_ihx(), zone volumes stop summing to
#  the envelope and the discrepancy shows up there.
# ─────────────────────────────────────────────────────────────────────────────
def ihx_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    import cadquery as cq

    L = _ihx_z_layout(spec)
    z_lp_top, z_up_bot, z_up_top = L["z_lp_top"], L["z_up_bot"], L["z_up_top"]

    lp_ir = float(spec["lower_plenum_inner_radius"]); lp_wall = float(spec["lower_plenum_wall"])
    lp_dr = float(spec["lower_plenum_dome_radius"])
    up_ir = float(spec["upper_plenum_inner_radius"]); up_wall = float(spec["upper_plenum_wall"])
    up_dr = float(spec["upper_plenum_dome_radius"]); up_or = up_ir + up_wall
    overshoot = min(lp_wall, up_wall) / 2.0

    structure = _solid_from_premade(spec)

    def cyl(r, z0, z1, x=0.0, y=0.0):
        h = z1 - z0
        return (cq.Workplane("XY").workplane(offset=z0 + h / 2.0)
                .center(x, y).cylinder(h, r).val())

    def hemi(r, z_eq, upper):
        s = cq.Workplane("XY").workplane(offset=z_eq).sphere(r)
        b = r * 4
        cut = (cq.Workplane("XY").workplane(offset=z_eq - r).box(b, b, r * 2) if upper
               else cq.Workplane("XY").workplane(offset=z_eq + r).box(b, b, r * 2))
        return s.cut(cut).val()

    # ── Tube-side (secondary): tight interiors, then minus steel ──────────────
    parts = [
        cyl(lp_ir, 0.0, z_lp_top - lp_wall),
        hemi(lp_dr - lp_wall, z_eq=0.0, upper=False),
        cyl(up_ir, z_up_bot + up_wall, z_up_top),
        hemi(up_dr - up_wall, z_eq=z_up_top, upper=True),
    ]
    for x, y, t_ir, _ in _ihx_ring_positions(spec):
        parts.append(cyl(t_ir, z_lp_top - lp_wall, z_up_bot + up_wall, x, y))

    cp_ir = float(spec["central_pipe_inner_radius"])
    cp_bend = float(spec["central_pipe_bend_radius"])
    cp_z = float(spec["central_pipe_z_offset"]); cp_horiz = float(spec["central_pipe_horiz_len"])
    z_cp_bend = z_up_bot + cp_z
    z_cp_horiz = z_cp_bend + cp_bend
    z_cp_bot = z_lp_top - overshoot
    x_cp_far = cp_bend + up_or + cp_horiz
    cp_path = (cq.Workplane("XZ").moveTo(0, z_cp_bot).lineTo(0, z_cp_bend)
               .radiusArc((cp_bend, z_cp_horiz), cp_bend).lineTo(x_cp_far, z_cp_horiz)
               .wire().val())
    parts.append(cq.Workplane("XY").workplane(offset=z_cp_bot).circle(cp_ir)
                 .sweep(cq.Workplane("XY").newObject([cp_path]), isFrenet=True).val())

    rs_ir = float(spec["riser_inner_radius"]); rs_wall = float(spec["riser_wall"])
    rs_h = float(spec["riser_height"]); rs_or = rs_ir + rs_wall
    z_clip = z_up_top + math.sqrt(up_dr * up_dr - rs_or * rs_or)
    z_rs_low = z_clip - overshoot
    z_rs_bot = z_up_top + up_dr
    z_cap_top = z_rs_low + rs_h + (z_rs_bot - z_rs_low)
    parts.append(cyl(rs_ir, z_up_top, z_cap_top - rs_wall))

    lat_ir = float(spec["lateral_pipe_inner_radius"]); lat_len = float(spec["lateral_pipe_length"])
    lat_z = float(spec["lateral_pipe_z_offset"])
    parts.append(cq.Workplane("YZ").workplane(offset=rs_ir).center(0, z_rs_bot + lat_z)
                 .circle(lat_ir).extrude(rs_or - rs_ir + lat_len).val())

    secondary = cq.Workplane().newObject([parts[0]])
    for p in parts[1:]:
        secondary = secondary.union(cq.Workplane().newObject([p]))
    secondary = secondary.cut(cq.Workplane().newObject([structure])).val()

    # ── Shell-side (primary): bundle-shell bore between tube sheets, minus rest ─
    bs_ir = float(spec.get("bundle_shell_inner_radius", min(lp_ir, up_ir)))
    h = z_up_bot - z_lp_top
    region = cq.Workplane("XY").workplane(offset=z_lp_top + h / 2.0).cylinder(h, bs_ir).val()
    primary = (cq.Workplane().newObject([region])
               .cut(cq.Workplane().newObject([structure]))
               .cut(cq.Workplane().newObject([secondary])).val())

    radius = max(lp_ir + lp_wall, lp_dr, up_or, up_dr)
    if "bundle_shell_wall" in spec:
        radius = max(radius, bs_ir + float(spec["bundle_shell_wall"]))

    return {
        "zones": [
            Zone("structure", "solid", structure.Volume()),
            Zone("tube_side", "fluid", secondary.Volume()),
            Zone("shell_side", "fluid", primary.Volume()),
        ],
        "cylinder": {"radius": radius, "z_bottom": -lp_dr, "height": (z_up_top + up_dr) - (-lp_dr)},
        # The measured solids themselves, in the component's LOCAL frame. The
        # cost report places these and cuts them out of the vessel bore to find
        # what is left for coolant, so a zone without a solid here is a zone the
        # pool cannot account for.
        "solids": {"structure": structure, "tube_side": secondary, "shell_side": primary},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Reactor core — one solid zone (cylinder or n-sided prism)
# ─────────────────────────────────────────────────────────────────────────────
def reactor_core_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    solid = _solid_from_premade(spec)
    z0 = float(spec.get("z_bottom", 0.0))
    return {
        "zones": [Zone("core", "solid", solid.Volume())],
        "cylinder": {"radius": float(spec["radius"]), "z_bottom": z0, "height": float(spec["height"])},
        "solids": {"core": solid},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Diagrid — solid shell + the closed interior cavity (a fluid zone)
# ─────────────────────────────────────────────────────────────────────────────
def diagrid_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    import cadquery as cq

    diameter = float(spec["diameter"]); height = float(spec["height"])
    z0 = float(spec.get("z_bottom", 0.0))

    # Wall-thickness precedence must match _build_diagrid: an individual
    # wall_t_side/top/bottom WINS over the uniform wall_t shortcut. (Reading
    # them the other way round measured a different shell than the one built.)
    def _wall(key: str) -> float:
        v = spec.get(key)
        return float(v) if v is not None else float(spec["wall_t"])

    ws, wt, wb = _wall("wall_t_side"), _wall("wall_t_top"), _wall("wall_t_bottom")

    # Built through the assembly's own builder, so the pump nozzle bosses and
    # bores the resolver injects are part of the measured steel. create_diagrid()
    # alone returns the bare shell and under-counts it by the bosses.
    shell = _solid_from_premade(spec)

    r_inner = diameter / 2.0 - ws
    cavity_h = height - wt - wb
    cavity = (cq.Workplane("XY").workplane(offset=z0 + wb + cavity_h / 2.0)
              .cylinder(cavity_h, r_inner).val())          # closed interior (no bores)
    cavity_vol = math.pi * r_inner * r_inner * cavity_h

    # The bosses protrude past the outer wall, so the envelope has to grow with
    # them — otherwise the declared zones exceed it and closure goes negative.
    radius = diameter / 2.0
    if spec.get("nozzle_boss_angles_deg"):
        radius += float(spec.get("nozzle_boss_height", 0.0))

    return {
        "zones": [
            Zone("shell", "solid", shell.Volume()),
            Zone("cavity", "fluid", cavity_vol),
        ],
        "cylinder": {"radius": radius, "z_bottom": z0, "height": height},
        "solids": {"shell": shell, "cavity": cavity},
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Primary pump — steel structure only; bore + surroundings are pool sodium,
#  i.e. the "_filler" closure material. Nozzles/flange overhang the barrel
#  envelope: their atoms are still counted, just smeared into the cylinder.
# ─────────────────────────────────────────────────────────────────────────────
def primary_pump_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    solid = _solid_from_premade(spec)
    z0 = float(spec.get("z_bottom", 0.0))
    return _structure_only(solid, {"radius": float(spec["barrel_radius"]),
                                   "z_bottom": z0,
                                   "height": float(spec["barrel_height"])})


# ─────────────────────────────────────────────────────────────────────────────
#  Strongback — steel structure only; rest is pool ("_filler")
# ─────────────────────────────────────────────────────────────────────────────
def strongback_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    solid = _solid_from_premade(spec)
    z0 = float(spec.get("z_bottom", 0.0))
    pts = spec.get("profile_pts")
    if pts is not None:
        radius = max(r for r, _ in pts)
        height = max(z for _, z in pts)
    else:
        radius = float(spec["skirt_outer_radius"])
        height = float(spec["total_height"])
    return _structure_only(solid, {"radius": radius, "z_bottom": z0, "height": height})


# ─────────────────────────────────────────────────────────────────────────────
#  Above-core structure — steel structure only; rest is pool ("_filler").
#  Envelope covers the offset top cylinder and any CRDL / bottom-plate
#  protrusions below z=0.
# ─────────────────────────────────────────────────────────────────────────────
def above_core_structure_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    solid = _solid_from_premade(spec)
    z0 = float(spec.get("z_bottom", 0.0))

    z4 = (float(spec["bottom_ring_height"]) + float(spec["cone_height"])
          + float(spec["neck_height"]) + float(spec["top_cyl_height"]))
    ox = float(spec.get("top_cyl_offset_x", 0.0))
    oy = float(spec.get("top_cyl_offset_y", 0.0))
    radius = max(float(spec["cone_bottom_outer_r"]),
                 math.hypot(ox, oy) + float(spec["top_cyl_outer_r"]))

    z_lo, z_hi = 0.0, z4
    crdl = spec.get("crdl")
    if crdl:
        z_lo = min(z_lo, -float(crdl.get("pipe_extend_bottom", 0.0)))
        z_hi = max(z_hi, z4 + float(crdl.get("pipe_extend_top", 0.0)))
    if spec.get("bottom_plate"):
        z_lo = min(z_lo, -float(spec["bottom_plate"]["thickness"]))

    return _structure_only(solid, {"radius": radius, "z_bottom": z0 + z_lo,
                                   "height": z_hi - z_lo})


# ─────────────────────────────────────────────────────────────────────────────
#  Redan — thin revolved shell spanning the whole pool. Declared like any
#  component, but the assembly-level homogeniser SMEARS its steel into the
#  pool cell instead of giving it a cylinder (a cylinder of r_top would
#  swallow the IHXs and pumps).
# ─────────────────────────────────────────────────────────────────────────────
def redan_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    solid = _solid_from_premade(spec)
    pts = spec.get("profile_pts")
    if pts is not None:
        radius = max(r for r, _ in pts)
        z_lo = min(z for _, z in pts)
        z_hi = max(z for _, z in pts)
    else:
        radius = float(spec["r_top"])
        z_lo = float(spec["z_bottom"])
        z_hi = float(spec["z_top"])
    z_off = float(spec.get("z_offset", 0.0))
    return _structure_only(solid, {"radius": radius, "z_bottom": z_lo + z_off,
                                   "height": z_hi - z_lo})


# ─────────────────────────────────────────────────────────────────────────────
#  Reactor vessel — modelled natively at assembly level (cylindrical shell +
#  equivalent flat bottom); this zone function supplies the exact CAD steel
#  volume that the native model must conserve.
# ─────────────────────────────────────────────────────────────────────────────
def reactor_vessel_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    solid = _solid_from_premade(spec)
    outer_d = spec.get("outer_d")
    if outer_d is None:
        outer_d = float(spec["inner_d"]) + 2.0 * float(spec["wall_t"])
    bb = solid.BoundingBox()
    return _structure_only(solid, {"radius": float(outer_d) / 2.0, "z_bottom": bb.zmin,
                                   "height": bb.zmax - bb.zmin})


# ─────────────────────────────────────────────────────────────────────────────
#  Reactor top plate — modelled natively at assembly level (slab minus the
#  penetrating component cylinders); CAD volume here is the steel to conserve.
#  NOTE the plate must be measured AFTER auto_generate_topplate_holes() has run,
#  or it comes back as an unperforated slab.
# ─────────────────────────────────────────────────────────────────────────────
def reactor_top_plate_zones(spec: Dict[str, Any]) -> Dict[str, Any]:
    solid = _solid_from_premade(spec)
    return _structure_only(solid, {"radius": float(spec["outer_d"]) / 2.0,
                                   "z_bottom": float(spec["z_bottom"]),
                                   "height": float(spec["thickness"])})


# ─────────────────────────────────────────────────────────────────────────────
#  Registry  (extend like component_anchors / PREMADE_BUILDERS)
#
#  Only components whose internals need more than one material belong here.
#  Anything absent is homogenised generically by homogenise_solid.generic_zones().
# ─────────────────────────────────────────────────────────────────────────────
MATERIAL_ZONES: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "ihx":                  ihx_zones,
    "reactor_core":         reactor_core_zones,
    "diagrid":              diagrid_zones,
    "primary_pump":         primary_pump_zones,
    "strongback":           strongback_zones,
    "above_core_structure": above_core_structure_zones,
    "redan":                redan_zones,
    "reactor_vessel":       reactor_vessel_zones,
    "reactor_top_plate":    reactor_top_plate_zones,
}

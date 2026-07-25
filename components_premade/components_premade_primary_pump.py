"""
Parametric primary pump: hollow barrel cylinder with two lateral elbow
nozzles (right and left, mirror-symmetric) and one top flange.
"""
 
from __future__ import annotations
import math
import cadquery as cq
 
from profile_built_in_2D_sketch import build_2D_sketch
from utils import sweep_profile


def elbow_overshoot(barrel_wall_t: float) -> float:
    """Radial depth the elbow root is sunk into the barrel wall, measured
    inward from the barrel OUTER surface.

    Single shared definition: used by create_primary_pump to BUILD the
    geometry and by component_anchors.pump_elbow_mouth_local to PREDICT the
    elbow mouth position for the resolver. The two must never disagree, or
    the diagrid bosses are sized/aimed at a mouth position that does not
    match the built pump.

    1.0 x wall_t embeds the elbow root through the full wall thickness
    (volumetric overlap -> reliable OCCT fusion) with the root face flush
    at the barrel inner surface. The fluid opening does NOT depend on this
    value: it is cut separately by the straight radial bore punches in
    create_primary_pump.
    """
    return 1.0 * barrel_wall_t


# ──────────────────────────────────────────────────────────────────────
# Elbow centerline + sweep
# ──────────────────────────────────────────────────────────────────────
def _elbow_path_wire(
    R_bend: float, arc_deg: float, L_inlet: float, L_leg: float,
    overshoot: float = 0.0,
    mirror_x: bool = False,
) -> cq.Wire:
    arc_rad = math.radians(arc_deg)
    sx = -1.0 if mirror_x else 1.0  # reflects arc into -X half-plane
 
    P_arc_start = (0.0, L_inlet, 0.0)
    P_arc_end   = (sx * R_bend * (1.0 - math.cos(arc_rad)),
                   L_inlet + R_bend * math.sin(arc_rad),
                   0.0)
    tan_end     = (sx * math.sin(arc_rad), math.cos(arc_rad), 0.0)

    leg_total = L_leg + overshoot
    P_end     = (P_arc_end[0] + leg_total * tan_end[0],
                 P_arc_end[1] + leg_total * tan_end[1],
                 0.0)
 
    half      = arc_rad / 2.0
    P_arc_mid = (sx * R_bend * (1.0 - math.cos(half)),
                 L_inlet + R_bend * math.sin(half),
                 0.0)
 
    edges = [
        cq.Edge.makeLine(cq.Vector(0.0, 0.0, 0.0),
                         cq.Vector(*P_arc_start)),
        cq.Edge.makeThreePointArc(cq.Vector(*P_arc_start),
                                  cq.Vector(*P_arc_mid),
                                  cq.Vector(*P_arc_end)),
    ]
    if leg_total > 0:
        edges.append(cq.Edge.makeLine(cq.Vector(*P_arc_end),
                                      cq.Vector(*P_end)))
 
    return cq.Wire.assembleEdges(edges)
 
 
def _build_elbow_outer_inner(
    r_pipe: float, wall_t: float,
    R_bend: float, arc_deg: float,
    L_inlet: float, L_leg: float,
    inner_overshoot: float,
    mirror_x: bool = False,
):
    outer_path = _elbow_path_wire(R_bend, arc_deg, L_inlet, L_leg,
                                  overshoot=0.0,            mirror_x=mirror_x)
    inner_path = _elbow_path_wire(R_bend, arc_deg, L_inlet, L_leg,
                                  overshoot=inner_overshoot, mirror_x=mirror_x)
 
    profile_outer = build_2D_sketch({"obj_type": "circle", "radius": r_pipe},          sketch_plane="XY")
    profile_inner = build_2D_sketch({"obj_type": "circle", "radius": r_pipe - wall_t}, sketch_plane="XY")
 
    outer = sweep_profile(profile_outer, outer_path, isFrenet=True)
    inner = sweep_profile(profile_inner, inner_path, isFrenet=True)
    return outer, inner
 
 
def _place_right_nozzle(elbow: cq.Workplane,
                        barrel_radius: float, overshoot: float,
                        nozzle_z: float) -> cq.Workplane:
    """Rotate so local +Y → world +X, translate to right side of barrel."""
    return (elbow
            .rotate((0, 0, 0), (0, 0, 1), -90)
            .translate((barrel_radius - overshoot, 0, nozzle_z)))
 
 
def _place_left_nozzle(elbow: cq.Workplane,
                       barrel_radius: float, overshoot: float,
                       nozzle_z: float) -> cq.Workplane:
    """Rotate so local +Y → world -X, translate to left side of barrel."""
    return (elbow
            .rotate((0, 0, 0), (0, 0, 1), 90)
            .translate((-(barrel_radius - overshoot), 0, nozzle_z)))
 
 
# ──────────────────────────────────────────────────────────────────────
# Pump assembly
# ──────────────────────────────────────────────────────────────────────
def create_primary_pump(
    barrel_radius:  float,
    barrel_wall_t:  float,
    barrel_height:  float,
    nozzle_r_pipe:  float,
    nozzle_wall_t:  float,
    nozzle_L_leg:   float,
    nozzle_R_bend:  float,
    nozzle_arc_deg: float,
    nozzle_L_inlet: float,
    nozzle_z:       float,
    flange_width:   float,
    flange_height:  float,
    flange_depth:   float,
    z_bottom:       float = 0.0,
    flange_z_top:   float | None = None,
) -> cq.Workplane:
    """
    Build a primary pump: hollow barrel with two mirror-symmetric elbows and top flange.

    The barrel is a hollow cylinder centered on the Z axis. Two elbow nozzles
    (right and left) curve outward from the barrel wall at height nozzle_z
    above the barrel bottom. A flange sits on top, perpendicular to the barrel.
    The pump is built with the barrel bottom face at z = z_bottom; nozzle_z
    and flange_z_top are measured from the barrel bottom, not from world z=0.

    Local origin / datum: barrel axis = local Z; z = 0 at the barrel bottom.
    Facing: elbows on ±X (mouths angled toward −Y), flange on +Y. The
    resolver's yaw maps these onto the reactor: flange radially outward,
    elbow mouths inward toward the diagrid.

    All parameters are unitless and must be provided consistently.

    Returns a single Workplane solid (union of barrel, elbows, and flange).
    """

    if flange_z_top is None:
        # OLDER VERSION (unit-carrying default): flange_z_top = barrel_height - 0.5
        raise ValueError(
            "create_primary_pump requires 'flange_z_top' (top of the flange, "
            "measured from the barrel bottom). No default: the old fallback "
            "barrel_height - 0.5 assumed metre-scale geometry."
        )

    overshoot       = elbow_overshoot(barrel_wall_t)
    inner_overshoot = nozzle_wall_t * 2
 
    barrel_outer = cq.Workplane("XY").circle(barrel_radius).extrude(barrel_height)
 
    # Right elbow: arc curves toward +X
    elbow_out_R, elbow_in_R = _build_elbow_outer_inner(
        r_pipe=nozzle_r_pipe, wall_t=nozzle_wall_t,
        R_bend=nozzle_R_bend, arc_deg=nozzle_arc_deg,
        L_inlet=nozzle_L_inlet, L_leg=nozzle_L_leg,
        inner_overshoot=inner_overshoot, mirror_x=False,
    )
    # Left elbow: arc curves toward -X (mirrored path)
    elbow_out_L, elbow_in_L = _build_elbow_outer_inner(
        r_pipe=nozzle_r_pipe, wall_t=nozzle_wall_t,
        R_bend=nozzle_R_bend, arc_deg=nozzle_arc_deg,
        L_inlet=nozzle_L_inlet, L_leg=nozzle_L_leg,
        inner_overshoot=inner_overshoot, mirror_x=True,
    )
 
    j_right_out = _place_right_nozzle(elbow_out_R, barrel_radius, overshoot, nozzle_z)
    j_right_in  = _place_right_nozzle(elbow_in_R,  barrel_radius, overshoot, nozzle_z)
    j_left_out  = _place_left_nozzle( elbow_out_L, barrel_radius, overshoot, nozzle_z)
    j_left_in   = _place_left_nozzle( elbow_in_L,  barrel_radius, overshoot, nozzle_z)
 
    flange = (cq.Workplane("XY")
              .workplane(offset=flange_z_top - flange_height)
              .moveTo(0, barrel_radius + flange_width / 2 - overshoot)
              .rect(flange_depth, flange_width)
              .extrude(flange_height))
 
    barrel_bore = (cq.Workplane("XY")
                   .workplane(offset=barrel_wall_t)
                   .circle(barrel_radius - barrel_wall_t)
                   .extrude(barrel_height - 2 * barrel_wall_t))
 
    # Straight radial punches open the barrel wall into each nozzle bore.
    nozzle_r_bore    = nozzle_r_pipe - nozzle_wall_t
    bore_punch_right = (
        cq.Workplane("YZ")
        .workplane(offset=0)
        .center(0, nozzle_z)
        .circle(nozzle_r_bore)
        .extrude(barrel_radius + barrel_wall_t)   # one wall past the outer surface (was +1.0 absolute)
    )
    bore_punch_left = bore_punch_right.mirror("YZ")
 
    # Box cutter hollows the flange, leaving barrel_wall_t on all sides and open toward the barrel interior.
    _fb_w   = flange_depth  - 2 * barrel_wall_t
    _fb_len = barrel_radius + flange_width - 2 * barrel_wall_t
    _fb_h   = flange_height - 2 * barrel_wall_t
    flange_bore_cutter = (
        cq.Workplane("XY")
        .box(_fb_w, _fb_len, _fb_h)
        .translate((0.0, _fb_len / 2, flange_z_top - flange_height / 2))
    )
 
    barrel       = barrel_outer.cut(barrel_bore).cut(j_right_in).cut(j_left_in).cut(bore_punch_right).cut(bore_punch_left).cut(flange_bore_cutter).clean()
    nozzle_right = j_right_out.cut(j_right_in).clean()
    nozzle_left  = j_left_out.cut(j_left_in).clean()
    flange       = flange.cut(flange_bore_cutter).clean()
 
    pump = barrel.union(nozzle_right).union(nozzle_left).union(flange).clean()
    if z_bottom != 0.0:
        pump = pump.translate((0, 0, z_bottom))
    return pump
 
 
# ──────────────────────────────────────────────────────────────────────
# Demo
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from ocp_vscode import show
 
    pump = create_primary_pump(
        barrel_radius  = 1.350 / 2,
        barrel_wall_t  = 0.040,
        barrel_height  = 12.000,
        nozzle_r_pipe  = 0.460 / 2,
        nozzle_wall_t  = 0.025,
        nozzle_L_leg   = 0.600,
        nozzle_R_bend  = 0.460,
        nozzle_arc_deg = 105.0,
        nozzle_L_inlet = 0.050,
        nozzle_z       = 0.450,
        flange_width   = 0.548,
        flange_height  = 0.900,
        flange_depth   = 0.500,
        flange_z_top   = 11.5,
    )
    show(pump)
 
 
 
 
 
 
 
 
 
 
 
 
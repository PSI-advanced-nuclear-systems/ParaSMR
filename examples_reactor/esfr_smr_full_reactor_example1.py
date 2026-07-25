"""
Example user assembly — paramak-style.

The user writes ONLY geometric parameters. There are no `center_coords`,
no `rotation_angles`, no cross-component fields like `nozzle_z_abs` on
the diagrid. The resolver fills those in by inspecting which components
are in the assembly and applying its connection rules.

How the user influences placement:
  • Each component declares its OWN positioning intent in human terms
    (e.g. a pump declares `at_angle_deg` and `at_radius`).
  • Diagrid/strongback/etc. just declare `z_bottom` (vertical stack).
  • The resolver does the rest.

Manual override
  • To bypass the resolver for one component, set both `center_coords`
    and `rotation_angles` explicitly — the resolver will respect them
    and only fill in cross-component params on the OTHER side of the
    connection (e.g. boss angles on the diagrid).
  • To remove a component from resolver consideration entirely, set
    `manual_placement: True`.
"""

import datetime
from assemble import assemble_objects
from ocp_vscode import show


_SB_Z_BOTTOM       = -1.702
_DIAGRID_Z_BOTTOM  = _SB_Z_BOTTOM + 1.242
_DIAGRID_TOP_Z     = _DIAGRID_Z_BOTTOM + 1.050
_CORE_Z_BOTTOM     = _DIAGRID_TOP_Z
_CORE_HEIGHT       = 3.910

_RV_STRAIGHT_H = 9.0

_PUMP_BARREL_H = 12.0
_PUMP_CENTER_Z = _RV_STRAIGHT_H + 0.5 - _PUMP_BARREL_H / 2

RV = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            8.91,
    "wall_t":             0.05,
    "straight_h":         _RV_STRAIGHT_H,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": 5.245, "rk": 0.379},
}

TOP_PLATE = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,
    "z_bottom":  _RV_STRAIGHT_H,
    "hole_groups": [
        {"hole_diameter": 2.224, "layout": "explicit_positions",
         "positions": [(0.0, 0.0)]},
        {"hole_diameter": 1.600, "layout": "symmetric", "count": 3,
         "placement_radius": 3.100, "start_angle_deg": 0.0},
        {"hole_diameter": 1.350, "layout": "symmetric", "count": 3,
         "placement_radius": 3.369, "start_angle_deg": 60.0},
    ],
}

_IHX_R = 3.100
def _make_ihx(obj_id, angle_deg):
    return {
        "obj_type":     "ihx",
        "obj_id":       obj_id,
        "at_radius":    _IHX_R,
        "at_angle_deg": angle_deg,
        "lower_plenum_inner_radius": 0.760, "lower_plenum_wall": 0.025,
        "lower_plenum_height":       0.600, "lower_plenum_dome_radius": 0.785,
        "upper_plenum_inner_radius": 0.760, "upper_plenum_wall": 0.025,
        "upper_plenum_height":       0.600, "upper_plenum_dome_radius": 0.785,
        "bundle_height":             6.0,
        "tube_rings": [
            dict(n=16, inner_radius=0.018, wall=0.003, pitch_radius=0.25),
            dict(n=24, inner_radius=0.016, wall=0.003, pitch_radius=0.40),
            dict(n=32, inner_radius=0.014, wall=0.003, pitch_radius=0.55),
            dict(n=40, inner_radius=0.014, wall=0.003, pitch_radius=0.70),
        ],
        "central_pipe_inner_radius": 0.20, "central_pipe_wall": 0.025,
        "central_pipe_bend_radius":  0.25, "central_pipe_z_offset": 0.20,
        "central_pipe_horiz_len":    0.60,
        "riser_inner_radius":        0.20, "riser_wall": 0.025,
        "riser_height":              0.60,
        "lateral_pipe_inner_radius": 0.10, "lateral_pipe_wall": 0.015,
        "lateral_pipe_length":       0.50, "lateral_pipe_z_offset": 0.30,
        "bundle_shell_inner_radius": 0.775, "bundle_shell_wall": 0.025,
        "bundle_shell_n_bars":       8,    "bundle_shell_bar_width": 0.030,
        "bundle_shell_window_fraction": 0.1,
        "bundle_shell_window_z_from_top": 1,
        "bundle_shell_window_z_from_bottom": 0.3,
        "z_bottom": 2,
    }
IHX1 = _make_ihx("ihx_1",   0.0)
IHX2 = _make_ihx("ihx_2", 120.0)
IHX3 = _make_ihx("ihx_3", 240.0)


def _make_pump(obj_id, angle_deg):
    return {
        "obj_type":          "primary_pump",
        "obj_id":            obj_id,
        "barrel_radius":     1.350 / 2,
        "barrel_wall_t":     0.040,
        "barrel_height":     _PUMP_BARREL_H,
        "nozzle_r_pipe":     0.460 / 2,
        "nozzle_wall_t":     0.025,
        "nozzle_L_leg":      0.600,
        "nozzle_R_bend":     0.460,
        "nozzle_arc_deg":    105.0,
        "nozzle_L_inlet":    0.050,
        "nozzle_z":          0.450,
        "flange_width":      0.548,
        "flange_height":     0.900,
        "flange_depth":      0.500,
        "flange_z_top":      11.5,
        "at_radius":         3.369,
        "at_angle_deg":      angle_deg,
    }
PUMP1 = _make_pump("pump_1",  60.0)
PUMP2 = _make_pump("pump_2", 180.0)
PUMP3 = _make_pump("pump_3", 300.0)


DIAGRID = {
    "obj_type":      "diagrid",
    "obj_id":        "diagrid",
    "diameter":      4.660,
    "height":        1.050,
    "z_bottom":      _DIAGRID_Z_BOTTOM,
    "wall_t_side":   0.030,
    "wall_t_top":    0.030,
    "wall_t_bottom": 0.030,
    "boss_wall_t":   0.071,
}

CORE = {
    "obj_type": "reactor_core",
    "obj_id":   "core",
    "radius":   3.600 / 2,
    "height":   _CORE_HEIGHT,
    "z_bottom": _CORE_Z_BOTTOM,
}

STRONGBACK = {
    "obj_type":               "strongback",
    "obj_id":                 "strongback",
    "total_height":           1.242,
    "flange_radius":          2.684,
    "skirt_outer_radius":     3.030,
    "skirt_inner_radius":     2.243,
    "skirt_height":           0.436,
    "taper_bottom_z":         0.356,
    "bore_radius":            0.303,
    "small_hole_radius":      0.0755,
    "small_hole_count":       6,
    "small_hole_placement_r": 0.900,
    "z_bottom":               _SB_Z_BOTTOM,
}

# Redan: half-section A → B → C revolved 360° about Z
# The polyline is the OUTER surface; wall grows inward by thickness.
# No penetrations for IHX/pump nozzles — overlap warnings expected as a follow-up.
_REDAN_R_TOP      = 8.91 / 2
_REDAN_R_LOWER    = 2.200
_REDAN_Z_KNEE     = _CORE_Z_BOTTOM + _CORE_HEIGHT
_REDAN_Z_BOTTOM   = _DIAGRID_TOP_Z
_REDAN_Z_SHOULDER = 6.500

REDAN = {
    "obj_type":       "redan",
    "obj_id":         "redan",
    "r_top":          _REDAN_R_TOP,
    "z_top":          _RV_STRAIGHT_H,
    "r_lower":        _REDAN_R_LOWER,
    "z_knee":         _REDAN_Z_KNEE,
    "z_bottom":       _REDAN_Z_BOTTOM,
    "thickness":      0.025,
    "z_shoulder":     _REDAN_Z_SHOULDER,
}

# Above-core structure: lower shell sits on local origin, top cylinder offset sideways.
_ACS_TOP_CYL_HEIGHT      = 1.008
_ACS_CONE_HEIGHT         = 2.429
_ACS_BOTTOM_RING_HEIGHT  = 0.498
_ACS_NECK_HEIGHT         = 0.661


# Vertical placement is resolver-driven (_resolve_acs_topplate): z_bottom is
# computed so the BOTTOM of the top cylinder rests ON the TOP of the top plate.
ABOVE_CORE_STRUCTURE = {
    "obj_type":             "above_core_structure",
    "obj_id":               "above_core_structure",
    "top_cyl_outer_r":      1.843,
    "top_cyl_height":       _ACS_TOP_CYL_HEIGHT,
    "neck_outer_r":         1.1085,
    "neck_height":          _ACS_NECK_HEIGHT,
    "wall_t":               0.025,
    "cone_height":          _ACS_CONE_HEIGHT,
    "cone_bottom_outer_r":  1.403,
    "bottom_ring_height":   _ACS_BOTTOM_RING_HEIGHT,
    "top_cyl_offset_x":     0.6056,
    "top_cyl_offset_y":     0.0,
    "crdl": {
        "through_d":          0.080,
        "pitch":              0.300,
        "pipe_wall_t":        0.005,
        "pipe_extend_bottom": 0.300,
        "pipe_extend_top":    0.300,
    },
    "bottom_plate": {"thickness": 0.050},
}


_TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
show(assemble_objects(
    [RV, TOP_PLATE, IHX1, IHX2, IHX3, PUMP1, PUMP2, PUMP3,
     DIAGRID, CORE, STRONGBACK, REDAN, ABOVE_CORE_STRUCTURE],
    export_path=f"output/esfr_smr_full_reactor_{_TS}.step",
    units="m",
))
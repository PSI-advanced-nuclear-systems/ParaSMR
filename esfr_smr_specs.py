"""
SPECS for the ESFR-SMR, copied verbatim from
    examples_reactor/example_final_esfr_smr_with_materials_cm.py
so the TRACE tooling has a source it can import without triggering the
example's top-level homogenisation (which writes a JSON on import).

UNITS: centimetres — identical to the example.

DRIFT WARNING: this is a copy. If the geometry in the example changes, re-sync
the affected blocks here. The values below are the flow-relevant heterogeneous
geometry (tube_rings, barrel, diagrid, ...) that nodalization.py reads.
"""

_SB_Z_BOTTOM      = -170.2
_DIAGRID_Z_BOTTOM = _SB_Z_BOTTOM + 124.2
_DIAGRID_TOP_Z    = _DIAGRID_Z_BOTTOM + 105.0
_CORE_Z_BOTTOM    = _DIAGRID_TOP_Z
_CORE_HEIGHT      = 391.0
_RV_STRAIGHT_H    = 900.0
_PUMP_BARREL_H    = 1200.0

STEEL = "ss316"
NA1   = "na_primary"
NA2   = "na_secondary"


RV = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            891.0,
    "wall_t":             5.0,
    "straight_h":         _RV_STRAIGHT_H,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": 524.5, "rk": 37.9},
    "material":           STEEL,
}

TOP_PLATE = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "top_plate",
    "outer_d":   1000.0,
    "thickness": 50.0,
    "z_bottom":  _RV_STRAIGHT_H,
    "material":  "ss304",
}


def _make_ihx(obj_id, angle_deg):
    return {
        "obj_type":     "ihx",
        "obj_id":       obj_id,
        "at_radius":    320.0,
        "at_angle_deg": angle_deg,
        "lower_plenum_inner_radius": 76.0, "lower_plenum_wall": 2.5,
        "lower_plenum_height":       60.0, "lower_plenum_dome_radius": 78.5,
        "upper_plenum_inner_radius": 76.0, "upper_plenum_wall": 2.5,
        "upper_plenum_height":       60.0, "upper_plenum_dome_radius": 78.5,
        "bundle_height":             600.0,
        "tube_rings": [
            dict(n=16, inner_radius=1.8, wall=0.3, pitch_radius=25.0),
            dict(n=24, inner_radius=1.6, wall=0.3, pitch_radius=40.0),
            dict(n=32, inner_radius=1.4, wall=0.3, pitch_radius=55.0),
            dict(n=40, inner_radius=1.4, wall=0.3, pitch_radius=70.0),
        ],
        "central_pipe_inner_radius": 20.0, "central_pipe_wall": 2.5,
        "central_pipe_bend_radius":  25.0, "central_pipe_z_offset": 20.0,
        "central_pipe_horiz_len":    60.0,
        "riser_inner_radius":        20.0, "riser_wall": 2.5,
        "riser_height":              60.0,
        "lateral_pipe_inner_radius": 10.0, "lateral_pipe_wall": 1.5,
        "lateral_pipe_length":       50.0, "lateral_pipe_z_offset": 30.0,
        "bundle_shell_inner_radius": 77.5, "bundle_shell_wall": 2.5,
        "bundle_shell_n_bars":       8,    "bundle_shell_bar_width": 3.0,
        "bundle_shell_window_fraction": 0.1,
        "bundle_shell_window_z_from_top": 100.0,
        "bundle_shell_window_z_from_bottom": 30.0,
        "z_bottom": 200.0,
        # secondary sodium inside the tubes, primary sodium on the shell side
        "materials": {"structure": STEEL, "tube_side": NA2,
                      "shell_side": NA1, "_filler": NA1},
    }


def _make_pump(obj_id, angle_deg):
    return {
        "obj_type":       "primary_pump",
        "obj_id":         obj_id,
        "barrel_radius":  135.0 / 2,
        "barrel_wall_t":  4.0,
        "barrel_height":  _PUMP_BARREL_H,
        "nozzle_r_pipe":  46.0 / 2,
        "nozzle_wall_t":  2.5,
        "nozzle_L_leg":   60.0,
        "nozzle_R_bend":  46.0,
        "nozzle_arc_deg": 105.0,
        "nozzle_L_inlet": 5.0,
        "nozzle_z":       45.0,
        "flange_width":   54.8,
        "flange_height":  90.0,
        "flange_depth":   50.0,
        "flange_z_top":   1150.0,
        "at_radius":      336.9,
        "at_angle_deg":   angle_deg,
        "materials": {"structure": STEEL, "_filler": NA1},
    }


DIAGRID = {
    "obj_type":      "diagrid",
    "obj_id":        "diagrid",
    "diameter":      466.0,
    "height":        105.0,
    "z_bottom":      _DIAGRID_Z_BOTTOM,
    "wall_t_side":   3.0,
    "wall_t_top":    3.0,
    "wall_t_bottom": 3.0,
    "boss_wall_t":   7.1,
    "materials": {"shell": STEEL, "cavity": NA1, "_filler": NA1},
}

CORE = {
    "obj_type": "reactor_core",
    "obj_id":   "core",
    "radius":   360.0 / 2,
    "height":   _CORE_HEIGHT,
    "z_bottom": _CORE_Z_BOTTOM,
    # NOTE core_smear was homogenised over 95 cm of active fuel; this cylinder
    # is 391.0 cm tall, so the fissile inventory it implies is correspondingly
    # overstated. Re-homogenise the composition before trusting k-eff.
    "materials": {"core": "core_smear"},
}

STRONGBACK = {
    "obj_type":               "strongback",
    "obj_id":                 "strongback",
    "total_height":           124.2,
    "flange_radius":          268.4,
    "skirt_outer_radius":     303.0,
    "skirt_inner_radius":     224.3,
    "skirt_height":           43.6,
    "taper_bottom_z":         35.6,
    "bore_radius":            30.3,
    "small_hole_radius":      7.55,
    "small_hole_count":       6,
    "small_hole_placement_r": 90.0,
    "z_bottom":               _SB_Z_BOTTOM,
    "materials": {"structure": STEEL, "_filler": NA1},
}

REDAN = {
    "obj_type":   "redan",
    "obj_id":     "redan",
    "r_top":      891.0 / 2,
    "z_top":      _RV_STRAIGHT_H,
    "r_lower":    220.0,
    "z_knee":     _CORE_Z_BOTTOM + _CORE_HEIGHT,
    "z_bottom":   _DIAGRID_TOP_Z,
    "thickness":  2.5,
    "z_shoulder": 650.0,
    "material":   STEEL,
}

ABOVE_CORE_STRUCTURE = {
    "obj_type":            "above_core_structure",
    "obj_id":              "above_core_structure",
    "top_cyl_outer_r":     175.0,
    "top_cyl_height":      100.8,
    "neck_outer_r":        110.85,
    "neck_height":         66.1,
    "wall_t":              2.5,
    "cone_height":         242.9,
    "cone_bottom_outer_r": 140.3,
    "bottom_ring_height":  49.8,
    "top_cyl_offset_x":    60.56,
    "top_cyl_offset_y":    0.0,
    "crdl": {
        "through_d":          8.0,
        "pitch":              30.0,
        "pipe_wall_t":        0.5,
        "pipe_extend_bottom": 30.0,
        "pipe_extend_top":    30.0,
    },
    "bottom_plate": {"thickness": 5.0},
    "materials": {"structure": STEEL, "_filler": NA1},
}


SPECS = [
    RV, TOP_PLATE,
    _make_ihx("ihx_1", 0.0), _make_ihx("ihx_2", 120.0), _make_ihx("ihx_3", 240.0),
    _make_pump("pump_1", 60.0), _make_pump("pump_2", 180.0), _make_pump("pump_3", 300.0),
    DIAGRID, CORE, STRONGBACK, REDAN, ABOVE_CORE_STRUCTURE,
]

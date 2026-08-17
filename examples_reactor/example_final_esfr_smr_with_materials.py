"""
Homogenised twin of example_final_esfr_smr.py.

Same geometry dicts, same resolver, same placement — each component simply
carries a material assignment as well. The homogeniser turns them into
atom-conserving equivalent cylinders and hands them back as CAD.

Zone names come from component_material_zones.py:
    ihx           structure / tube_side / shell_side
    diagrid       shell / cavity
    reactor_core  core
    everything else (pump, strongback, above-core structure, redan, vessel,
                     plate)  ->  one "structure" zone
"_filler" is what fills the equivalent cylinder around the component: pool
sodium, not vacuum.

UNITS: none. The numbers below are the same ones example_final_esfr_smr.py
uses; a unit is named only when a STEP file is written.
"""

import datetime

from assemble import assemble_objects
from ocp_vscode import show
from materials import MATERIALS
from homogenise import (
    homogenise_objects, build_cad, check_against_cad, print_report,
)

_SB_Z_BOTTOM      = -1.702
_DIAGRID_Z_BOTTOM = _SB_Z_BOTTOM + 1.242
_DIAGRID_TOP_Z    = _DIAGRID_Z_BOTTOM + 1.050
_CORE_Z_BOTTOM    = _DIAGRID_TOP_Z
_CORE_HEIGHT      = 3.910
_RV_STRAIGHT_H    = 9.0
_PUMP_BARREL_H    = 12.0

STEEL = "ss316"
NA1   = "na_primary"
NA2   = "na_secondary"


RV = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            8.91,
    "wall_t":             0.05,
    "straight_h":         _RV_STRAIGHT_H,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": 5.245, "rk": 0.379},
    "material":           STEEL,
}

TOP_PLATE = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,
    "z_bottom":  _RV_STRAIGHT_H,
    "material":  "ss304",
}


def _make_ihx(obj_id, angle_deg):
    return {
        "obj_type":     "ihx",
        "obj_id":       obj_id,
        "at_radius":    3.200,
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
        # secondary sodium inside the tubes, primary sodium on the shell side
        "materials": {"structure": STEEL, "tube_side": NA2,
                      "shell_side": NA1, "_filler": NA1},
    }


def _make_pump(obj_id, angle_deg):
    return {
        "obj_type":       "primary_pump",
        "obj_id":         obj_id,
        "barrel_radius":  1.350 / 2,
        "barrel_wall_t":  0.040,
        "barrel_height":  _PUMP_BARREL_H,
        "nozzle_r_pipe":  0.460 / 2,
        "nozzle_wall_t":  0.025,
        "nozzle_L_leg":   0.600,
        "nozzle_R_bend":  0.460,
        "nozzle_arc_deg": 105.0,
        "nozzle_L_inlet": 0.050,
        "nozzle_z":       0.450,
        "flange_width":   0.548,
        "flange_height":  0.900,
        "flange_depth":   0.500,
        "flange_z_top":   11.5,
        "at_radius":      3.369,
        "at_angle_deg":   angle_deg,
        "materials": {"structure": STEEL, "_filler": NA1},
    }


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
    "materials": {"shell": STEEL, "cavity": NA1, "_filler": NA1},
}

CORE = {
    "obj_type": "reactor_core",
    "obj_id":   "core",
    "radius":   3.600 / 2,
    "height":   _CORE_HEIGHT,
    "z_bottom": _CORE_Z_BOTTOM,
    # NOTE core_smear was homogenised over 95 cm of active fuel; this cylinder
    # is 3.910 tall, so the fissile inventory it implies is correspondingly
    # overstated. Re-homogenise the composition before trusting k-eff.
    "materials": {"core": "core_smear"},
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
    "materials": {"structure": STEEL, "_filler": NA1},
}

REDAN = {
    "obj_type":   "redan",
    "obj_id":     "redan",
    "r_top":      8.91 / 2,
    "z_top":      _RV_STRAIGHT_H,
    "r_lower":    2.200,
    "z_knee":     _CORE_Z_BOTTOM + _CORE_HEIGHT,
    "z_bottom":   _DIAGRID_TOP_Z,
    "thickness":  0.025,
    "z_shoulder": 6.500,
    # smeared into the pool (see _TREATMENT): a cylinder of r_top would
    # swallow the IHXs and pumps.
    "material":   STEEL,
}

ABOVE_CORE_STRUCTURE = {
    "obj_type":            "above_core_structure",
    "obj_id":              "above_core_structure",
    "top_cyl_outer_r":     1.750,
    "top_cyl_height":      1.008,
    "neck_outer_r":        1.1085,
    "neck_height":         0.661,
    "wall_t":              0.025,
    "cone_height":         2.429,
    "cone_bottom_outer_r": 1.403,
    "bottom_ring_height":  0.498,
    "top_cyl_offset_x":    0.6056,
    "top_cyl_offset_y":    0.0,
    "crdl": {
        "through_d":          0.080,
        "pitch":              0.300,
        "pipe_wall_t":        0.005,
        "pipe_extend_bottom": 0.300,
        "pipe_extend_top":    0.300,
    },
    "bottom_plate": {"thickness": 0.050},
    "materials": {"structure": STEEL, "_filler": NA1},
}


SPECS = [
    RV, TOP_PLATE,
    _make_ihx("ihx_1", 0.0), _make_ihx("ihx_2", 120.0), _make_ihx("ihx_3", 240.0),
    _make_pump("pump_1", 60.0), _make_pump("pump_2", 180.0), _make_pump("pump_3", 300.0),
    DIAGRID, CORE, STRONGBACK, REDAN, ABOVE_CORE_STRUCTURE,
]


_TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# assemble_objects(
#         SPECS,
#         export_path=f"output/esfr_smr_full_reactor_{_TS}.step",
#         units="m",
#     )

# The homogenised twin of the same SPECS — atom-conserving equivalent cylinders
# in a sodium pool — in the OCP CAD Viewer. The material library is the default,
# so the only thing the specs above needed was their "materials" blocks.
show(build_cad(homogenise_objects(SPECS)))

# Both geometries at once, from the same SPECS list: the real one solid, the
# equivalent cylinders translucent on top of it. Each is its own branch of the
# viewer tree, so either can be toggled off.
# show(
#     assemble_objects(SPECS),
#     build_cad(homogenise_objects(SPECS)),
#     names=["heterogeneous", "homogenised"],
#     alphas=[1.0, 0.35],
# )


"""
homogenise_objects(
    SPECS,
    MATERIALS,
    pool={"material": NA1},
    units="m",                       # label only — this model is authored in metres
    out_path=f"output/homogenised_model_{_TS}.json",
)
"""



# if __name__ == "__main__":
#     _TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

#     model = homogenise_objects(
#         SPECS,
#         MATERIALS,
#         pool={"material": NA1},
#         out_path=f"output/homogenised_model_{_TS}.json",
#     )

#     # Independent check: placement and inventory against the real CAD assembly.
#     cad_check = check_against_cad(model, SPECS)
#     print_report(model, cad_check)

#     # The homogenised model as CAD. "m" is only needed because STEP demands a
#     # unit declaration — nothing above this line knew or cared.
#     assy = build_cad(
#         model,
#         export_path=f"output/homogenised_esfr_{_TS}.step",
#         units="m",
#     )
#     show(assy)

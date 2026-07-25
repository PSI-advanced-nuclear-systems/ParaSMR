from ocp_vscode import show
from assemble import assemble_objects

# ACS with staggered flow holes.
# Odd rows start at 0°, even rows are offset by half the angular step
# (360 / n_holes / 2 = 10° for 18 holes), producing a brick-like pattern
# instead of straight vertical columns.
# All other geometry is identical to above_core_structure.py.

_STEP = 360 / 18 / 2   # 10° — half the angular spacing between holes

acs = {
    "obj_type":            "above_core_structure",
    "obj_id":              "acs_staggered",
    "cone_bottom_outer_r": 1.403,
    "cone_height":         2.429,
    "bottom_ring_height":  0.498,
    "neck_outer_r":        1.1085,
    "neck_height":         0.661,
    "top_cyl_outer_r":     1.843,
    "top_cyl_height":      1.008,
    "top_cyl_offset_x":    0.6056,
    "top_cyl_offset_y":    0.0,
    "wall_t":              0.025,
    "flow_hole_groups": [
        {"n_holes": 18, "hole_r": 0.040, "z_center": 0.700, "start_angle_deg": 0.0   },
        {"n_holes": 18, "hole_r": 0.039, "z_center": 0.883, "start_angle_deg": 10.0 },
        {"n_holes": 18, "hole_r": 0.038, "z_center": 1.067, "start_angle_deg": 0.0   },
        {"n_holes": 18, "hole_r": 0.037, "z_center": 1.250, "start_angle_deg": 10.0 },
        {"n_holes": 18, "hole_r": 0.037, "z_center": 1.433, "start_angle_deg": 0.0   },
        {"n_holes": 18, "hole_r": 0.036, "z_center": 1.617, "start_angle_deg": 10.0 },
        {"n_holes": 18, "hole_r": 0.035, "z_center": 1.800, "start_angle_deg": 0.0   },
    ],
    "crdl": {
        "through_d":          0.080,
        "pitch":              0.300,
        "pipe_wall_t":        0.005,
        "pipe_extend_bottom": 0.300,
        "pipe_extend_top":    0.300,
    },
    "bottom_plate": {"thickness": 0.050},
}

show(assemble_objects([acs]))

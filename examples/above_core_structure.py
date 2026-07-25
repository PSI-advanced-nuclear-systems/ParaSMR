from ocp_vscode import show
from assemble import assemble_objects

# ACS geometry: a wide cone at the bottom (over the core) narrows into a neck
# that registers into the top plate, then a top cylinder offset to one side
# to clear the IHX and pump nozzles above.

acs = {
    "obj_type":            "above_core_structure",
    "obj_id":              "acs",
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
        {"n_holes": 18, "hole_r": 0.040, "z_center": 0.700},
        {"n_holes": 18, "hole_r": 0.039, "z_center": 0.883},
        {"n_holes": 18, "hole_r": 0.038, "z_center": 1.067},
        {"n_holes": 18, "hole_r": 0.037, "z_center": 1.250},
        {"n_holes": 18, "hole_r": 0.037, "z_center": 1.433},
        {"n_holes": 18, "hole_r": 0.036, "z_center": 1.617},
        {"n_holes": 18, "hole_r": 0.035, "z_center": 1.800},
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

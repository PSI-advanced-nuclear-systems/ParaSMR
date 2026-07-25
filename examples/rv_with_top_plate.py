from ocp_vscode import show
from assemble import assemble_objects

rv_hemispherical = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            8,
    "wall_t":             0.1,
    "straight_h":         10.0,
    "bottom_head_type":   "hemispherical",
}



top_plate_symmetric = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,

    "hole_groups": [
        {"hole_diameter": 1.600, "layout": "symmetric", "count": 3,
         "placement_radius": 3.100, "start_angle_deg": 0.0},
    ],
}
assy_top_plate_symmetric = assemble_objects([rv_hemispherical, top_plate_symmetric])
show(assy_top_plate_symmetric)



top_plate_custom_angles = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "top_plate",
    "outer_d":   10.0,
    "thickness": 0.5,
    "hole_groups": [{"hole_diameter": 1.600, "layout": "custom_angles",
                     "angles_deg": [0.0, 100.0, 200.0], "placement_radius": 2.000},
    ],
}
assy_top_plate_custom_angles = assemble_objects([rv_hemispherical, top_plate_custom_angles])
show(assy_top_plate_custom_angles)



top_plate_explicit_positions = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "top_plate",
    "outer_d":   8.5,
    "thickness": 0.5,
    "hole_groups": [
        {"hole_diameter": 1.600, "layout": "explicit_positions",
         "positions": [(-1.0, +2.0)]},
    ],
}
assy_top_plate_explicit_positions = assemble_objects([rv_hemispherical, top_plate_explicit_positions])
show(assy_top_plate_explicit_positions)



top_plate_combination = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "top_plate",
    "outer_d":   8.5,
    "thickness": 0.5,

    "hole_groups": [
        {"hole_diameter": 1.100, "layout": "explicit_positions",
         "positions": [(0.0, 0.0)]},
        {"hole_diameter": 1.200, "layout": "symmetric", "count": 6,
         "placement_radius": 3.000, "start_angle_deg": 20.0},
        {"hole_diameter": 1.00, "layout": "custom_angles",
         "angles_deg": [40.0, 160.0, 300.0], "placement_radius": 1.800},
    ],
}
assy_top_plate_combination = assemble_objects([rv_hemispherical, top_plate_combination])
show(assy_top_plate_combination)
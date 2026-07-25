from ocp_vscode import show
from assemble import assemble_objects

strongback = {
    "obj_type":               "strongback",
    "obj_id":                 "strongback",
    "total_height":           1.242,
    "flange_radius":          2.684,
    "skirt_outer_radius":     3.030,
    "skirt_inner_radius":     2.243,
    "skirt_height":           0.436,
    "taper_bottom_z":         0.356,
    "bore_radius":            0.303,
    "small_hole_radius":      0.076,
    "small_hole_count":       6,
    "small_hole_placement_r": 0.900,
}

show(assemble_objects([strongback]))

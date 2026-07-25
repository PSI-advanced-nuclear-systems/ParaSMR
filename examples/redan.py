from ocp_vscode import show
from assemble import assemble_objects

redan = {
    "obj_type":   "redan",
    "obj_id":     "redan",
    "r_top":      4.455,
    "z_top":      9.0,
    "r_lower":    2.300,
    "z_knee":     4.590,
    "z_bottom":   0.590,
    "thickness":  0.025,
    "z_shoulder": 7.0,
}

show(assemble_objects([redan]))

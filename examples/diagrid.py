from ocp_vscode import show
from assemble import assemble_objects

diagrid = {
    "obj_type": "diagrid",
    "obj_id":   "diagrid",

    "diameter":      4.660,
    "height":        1.050,
    "wall_t":    0.030,
    "boss_wall_t":   0.071,
    #"z_bottom":      -0.460,
    #"wall_t_side":   0.030,
    #"wall_t_top":    0.030,
    #"wall_t_bottom": 0.030,
}


pump = {
    "obj_type": "primary_pump",
    "obj_id":   "primary_pump",

    "barrel_radius":  1.350 / 2,
    "barrel_wall_t":  0.040,
    "barrel_height":  12.000,
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
    "at_angle_deg":   0.0,
}

assy = assemble_objects([diagrid, pump])
#assy = assemble_objects([diagrid])
show(assy)
from ocp_vscode import show
from assemble import assemble_objects

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
}
assy = assemble_objects([pump])
show(assy)
 
 
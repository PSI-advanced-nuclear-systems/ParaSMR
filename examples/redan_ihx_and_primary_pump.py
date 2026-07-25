from ocp_vscode import show
from assemble import assemble_objects

# The resolver reads the IHX and pump positions and automatically cuts
# circular penetrations through the redan shell for each one.

redan = {
    "obj_type":   "redan",
    "obj_id":     "redan",
    "r_top":      4.455,
    "z_top":      9.0,
    "r_lower":    2.300,
    "z_knee":     4.590,
    "z_bottom":   1.000,
    "thickness":  0.025,
    "z_shoulder": 7.0,
}

ihx = {
    "obj_type":     "ihx",
    "obj_id":       "ihx",
    "at_radius":    3.200,
    "at_angle_deg": 0.0,
    "lower_plenum_inner_radius": 0.760, "lower_plenum_wall": 0.025,
    "lower_plenum_height":       0.600, "lower_plenum_dome_radius": 0.785,
    "upper_plenum_inner_radius": 0.760, "upper_plenum_wall": 0.025,
    "upper_plenum_height":       0.600, "upper_plenum_dome_radius": 0.785,
    "bundle_height": 8.0,
    "tube_rings": [
        dict(n=16, inner_radius=0.016, wall=0.002, pitch_radius=0.25),
        dict(n=24, inner_radius=0.014, wall=0.002, pitch_radius=0.40),
    ],
    "central_pipe_inner_radius": 0.180, "central_pipe_wall": 0.025,
    "central_pipe_bend_radius":  0.220, "central_pipe_z_offset": 0.200,
    "central_pipe_horiz_len":    0.550,
    "riser_inner_radius":        0.180, "riser_wall": 0.025,
    "riser_height":              0.550,
    "lateral_pipe_inner_radius": 0.090, "lateral_pipe_wall": 0.015,
    "lateral_pipe_length":       0.450, "lateral_pipe_z_offset": 0.280,
    "bundle_shell_inner_radius": 0.775, "bundle_shell_wall": 0.025,
    "bundle_shell_n_bars":       6,     "bundle_shell_bar_width": 0.025,
    "bundle_shell_window_fraction": 0.10,
    "z_bottom": 0.0,
}

pump = {
    "obj_type":      "primary_pump",
    "obj_id":        "pump",
    "at_radius":     3.200,
    "at_angle_deg":  90.0,
    "barrel_radius":  0.650,
    "barrel_wall_t":  0.040,
    "barrel_height":  12.0,
    "nozzle_r_pipe":  0.220,
    "nozzle_wall_t":  0.025,
    "nozzle_L_leg":   0.600,
    "nozzle_R_bend":  0.440,
    "nozzle_arc_deg": 105.0,
    "nozzle_L_inlet": 0.050,
    "nozzle_z":       0.450,
    "flange_width":   0.520,
    "flange_height":  0.850,
    "flange_depth":   0.480,
    "flange_z_top":   11.5,
    "rotation_angles": (0.0, 0.0, 0.0),
}

pump2 = {
    "obj_type":      "primary_pump",
    "obj_id":        "pump2",
    "at_radius":     3.200,
    "at_angle_deg":  270.0,
    "barrel_radius":  0.650,
    "barrel_wall_t":  0.040,
    "barrel_height":  12.0,
    "nozzle_r_pipe":  0.220,
    "nozzle_wall_t":  0.025,
    "nozzle_L_leg":   0.600,
    "nozzle_R_bend":  0.440,
    "nozzle_arc_deg": 105.0,
    "nozzle_L_inlet": 0.050,
    "nozzle_z":       0.450,
    "flange_width":   0.520,
    "flange_height":  0.850,
    "flange_depth":   0.480,
    "flange_z_top":   11.5,
    "rotation_angles": (0.0, 0.0, 180.0),
}

ihx2 = {**ihx, "obj_id": "ihx2", "at_angle_deg": 180.0}
#pump2 = {**pump, "obj_id": "pump2", "at_angle_deg": 270.0, "rotation_angles": (0.0, 0.0, 0.0)}

show(assemble_objects([redan, ihx, pump, ihx2, pump2]))

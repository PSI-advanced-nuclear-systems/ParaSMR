from ocp_vscode import show
from assemble import assemble_objects


# small IHX, no bundle shell
ihx_small = {
    "obj_type": "ihx",
    "obj_id":   "ihx_small",

    "lower_plenum_inner_radius": 0.295, "lower_plenum_wall": 0.018,
    "lower_plenum_height":       0.360, "lower_plenum_dome_radius": 0.315,
    "upper_plenum_inner_radius": 0.295, "upper_plenum_wall": 0.018,
    "upper_plenum_height":       0.360, "upper_plenum_dome_radius": 0.315,

    "bundle_height": 3.2,
    "tube_rings": [
        dict(n=16, inner_radius=0.015, wall=0.002, pitch_radius=0.215),
    ],

    "central_pipe_inner_radius": 0.115, "central_pipe_wall": 0.018,
    "central_pipe_bend_radius":  0.145, "central_pipe_z_offset": 0.155,
    "central_pipe_horiz_len":    0.420,

    "riser_inner_radius": 0.115, "riser_wall": 0.018,
    "riser_height":       0.390,

    "lateral_pipe_inner_radius": 0.058, "lateral_pipe_wall": 0.012,
    "lateral_pipe_length":       0.380, "lateral_pipe_z_offset": 0.210,
}


ihx_medium = {
    "obj_type": "ihx",
    "obj_id":   "ihx_medium",

    "lower_plenum_inner_radius": 0.545, "lower_plenum_wall": 0.022,
    "lower_plenum_height":       0.520, "lower_plenum_dome_radius": 0.568,
    "upper_plenum_inner_radius": 0.545, "upper_plenum_wall": 0.022,
    "upper_plenum_height":       0.520, "upper_plenum_dome_radius": 0.568,

    "bundle_height": 5.4,
    "tube_rings": [
        dict(n=16, inner_radius=0.018, wall=0.002, pitch_radius=0.215),
        dict(n=24, inner_radius=0.016, wall=0.002, pitch_radius=0.345),
        dict(n=32, inner_radius=0.014, wall=0.002, pitch_radius=0.470),
    ],

    "central_pipe_inner_radius": 0.158, "central_pipe_wall": 0.022,
    "central_pipe_bend_radius":  0.195, "central_pipe_z_offset": 0.185,
    "central_pipe_horiz_len":    0.520,

    "riser_inner_radius": 0.158, "riser_wall": 0.022,
    "riser_height":       0.480,

    "lateral_pipe_inner_radius": 0.078, "lateral_pipe_wall": 0.014,
    "lateral_pipe_length":       0.460, "lateral_pipe_z_offset": 0.255,

    "bundle_shell_inner_radius": 0.545, "bundle_shell_wall": 0.022,
    "bundle_shell_n_bars":       6,     "bundle_shell_bar_width": 0.025,
    "bundle_shell_window_fraction": 0.10,#30,
    "bundle_shell_window_z_from_top":    0.25,
    "bundle_shell_window_z_from_bottom": 0.25,
}


ihx_large = {
    "obj_type": "ihx",
    "obj_id":   "ihx_large",

    "lower_plenum_inner_radius": 0.790, "lower_plenum_wall": 0.028,
    "lower_plenum_height":       0.680, "lower_plenum_dome_radius": 0.820,
    "upper_plenum_inner_radius": 0.790, "upper_plenum_wall": 0.028,
    "upper_plenum_height":       0.680, "upper_plenum_dome_radius": 0.820,

    "bundle_height": 7.8,
    "tube_rings": [
        dict(n=24, inner_radius=0.014, wall=0.002, pitch_radius=0.355),
        dict(n=32, inner_radius=0.012, wall=0.002, pitch_radius=0.495),
        dict(n=48, inner_radius=0.012, wall=0.002, pitch_radius=0.645),
    ],

    "central_pipe_inner_radius": 0.218, "central_pipe_wall": 0.025,
    "central_pipe_bend_radius":  0.275, "central_pipe_z_offset": 0.245,
    "central_pipe_horiz_len":    0.680,

    "riser_inner_radius": 0.218, "riser_wall": 0.025,
    "riser_height":       0.680,

    "lateral_pipe_inner_radius": 0.118, "lateral_pipe_wall": 0.020,
    "lateral_pipe_length":       0.620, "lateral_pipe_z_offset": 0.355,

    "bundle_shell_inner_radius":         0.790, "bundle_shell_wall": 0.028,
    "bundle_shell_n_bars":               8,     "bundle_shell_bar_width": 0.030,
    "bundle_shell_window_fraction":      0.20,
    "bundle_shell_window_z_from_top":    0.75,
    "bundle_shell_window_z_from_bottom": 0.38,
}


#show(assemble_objects([ihx_small]))
show(assemble_objects([ihx_medium]))
#show(assemble_objects([ihx_large]))

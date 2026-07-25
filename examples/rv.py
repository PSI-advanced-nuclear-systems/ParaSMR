from ocp_vscode import show
from assemble import assemble_objects

rv_flat = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            8,
    "wall_t":             0.1,
    "straight_h":         10.0,
    "bottom_head_type":   "flat",
}
assy_flat = assemble_objects([rv_flat])
show(assy_flat)




rv_ellipsoidal = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            8,
    "wall_t":             0.1,
    "straight_h":         10.0,
    "bottom_head_type":   "ellipsoidal",
    "bottom_head_params": {"head_depth": 2.0},
}
assy_ellipsoidal = assemble_objects([rv_ellipsoidal])
show(assy_ellipsoidal)




rv_hemispherical = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            8,
    "wall_t":             0.1,
    "straight_h":         10.0,
    "bottom_head_type":   "hemispherical",
}
assy_hemispherical = assemble_objects([rv_hemispherical])
show(assy_hemispherical)




rv_torispherical = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "rv",
    "inner_d":            8,
    "wall_t":             0.1,
    "straight_h":         10.0,
    "bottom_head_type":   "torispherical",
    "bottom_head_params": {"Rc": 5.0, "rk": 1},
}
assy_torispherical = assemble_objects([rv_torispherical])
show(assy_torispherical)
import time
import cadquery as cq
from ocp_vscode import show
from profile_built_in_2D_sketch import build_2D_sketch
from utils import revolve_profile
from typing import List, Tuple, Literal

AxisType = Literal["X", "Y", "Z"]
examples: List[Tuple[str, dict, str, float, AxisType, Tuple[float, float, float]]] = []

ex_rect            = {"obj_type": "rectangle",      "width": 10,  "height": 6}
ex_circle          = {"obj_type": "circle",          "radius": 4}
ex_ellipse         = {"obj_type": "ellipse",         "r1": 6, "r2": 3}
ex_trapezoid       = {"obj_type": "trapezoid",       "width": 10, "height": 6, "a1": 70}
ex_slot            = {"obj_type": "slot",            "width": 12, "height": 4}
ex_regular_polygon = {"obj_type": "regular_polygon", "radius": 5, "nmb_of_sides": 6}
ex_polygon         = {"obj_type": "polygon",         "pts": [(2,2), (10,2), (12,8), (6,12), (1,7)]}

# (label, shape_dict, sketch_plane, angle, axis, axis_point)
examples = [
    # --- Rectangle ---
    # XZ plane: shape spans x=[-5,+5], axis at x=-10 → clear
    ("rect revolve Z 360",      ex_rect,            "XZ", 360.0, "Z", (-10, 0, 0)),
    ("rect revolve Z 180",      ex_rect,            "XZ", 180.0, "Z", (-10, 0, 0)),
    # XY plane: shape spans y=[-3,+3], axis at y=-10 → clear
    ("rect revolve Y 360",      ex_rect,            "YZ", 360.0, "Y", (0, 0, -10)),

    # --- Circle ---
    ("circle revolve Z 360",    ex_circle,          "XZ", 360.0, "Z", (-8,  0, 0)),
    ("circle revolve Z 270",    ex_circle,          "XZ", 270.0, "Z", (-8,  0, 0)),
    ("circle revolve Y 360",    ex_circle,          "YZ", 360.0, "Y", (0, 0, -8)),

    # --- Ellipse ---
    ("ellipse revolve Z 360",   ex_ellipse,         "XZ", 360.0, "Z", (-10, 0, 0)),
    ("ellipse revolve Z 180",   ex_ellipse,         "XZ", 180.0, "Z", (-10, 0, 0)),
    ("ellipse revolve Y 360",   ex_ellipse,         "YZ", 360.0, "Y", (0, 0, -10)),

    # --- Trapezoid ---
    ("trapezoid revolve Z 360", ex_trapezoid,       "XZ", 360.0, "Z", (-10, 0, 0)),
    ("trapezoid revolve Z 90",  ex_trapezoid,       "XZ",  90.0, "Z", (-10, 0, 0)),
    ("trapezoid revolve Y 360", ex_trapezoid,       "YZ", 360.0, "Y", (0, 0, -10)),

    # --- Slot ---
    ("slot revolve Z 360",      ex_slot,            "XZ", 360.0, "Z", (-10, 0, 0)),
    ("slot revolve Z 180",      ex_slot,            "XZ", 180.0, "Z", (-10, 0, 0)),
    ("slot revolve Y 360",      ex_slot,            "YZ", 360.0, "Y", (0, 0, -10)),

    # --- Regular polygon ---
    ("hex revolve Z 360",       ex_regular_polygon, "XZ", 360.0, "Z", (-8,  0, 0)),
    ("hex revolve Z 270",       ex_regular_polygon, "XZ", 270.0, "Z", (-8,  0, 0)),
    ("hex revolve Y 360",       ex_regular_polygon, "YZ", 360.0, "Y", (0, 0, -8)),

    # --- Polygon: min x=1, axis at x=-2 → clear ---
    ("polygon revolve Z 360",   ex_polygon,         "XZ", 360.0, "Z", (-2,  0, 0)),
    ("polygon revolve Z 180",   ex_polygon,         "XZ", 180.0, "Z", (-2,  0, 0)),
    ("polygon revolve Y 360",   ex_polygon,         "YZ", 360.0, "Y", (0, 0, -2)),
]

for label, shape_dict, sketch_plane, angle, axis, axis_point in examples:
    print(f"Showing: {label}")
    profile = build_2D_sketch(shape_dict, sketch_plane=sketch_plane)
    result  = revolve_profile(profile, angle=angle, axis=axis, axis_point=axis_point)
    show(result)
    time.sleep(1)
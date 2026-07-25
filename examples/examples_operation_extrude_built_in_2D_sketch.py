# examples.py
import time
import cadquery as cq
from ocp_vscode import show

from profile_built_in_2D_sketch import build_2D_sketch
from utils import extrude_profile, revolve_profile


# ------------------------------------------------------------------------------
# ── 2D → extrude examples ─────────────────────────────────────────────────────
# ------------------------------------------------------------------------------
ex_rect            = {"obj_type": "rectangle",       "width": 20,  "height": 10}
ex_circle          = {"obj_type": "circle",           "radius": 8}
ex_ellipse         = {"obj_type": "ellipse",          "r1": 12,     "r2": 6}
ex_trapezoid       = {"obj_type": "trapezoid",        "width": 20,  "height": 10, "a1": 75}
ex_slot            = {"obj_type": "slot",             "width": 25,  "height": 8}
ex_regular_polygon = {"obj_type": "regular_polygon",  "radius": 10, "nmb_of_sides": 6}
ex_polygon         = {"obj_type": "polygon",          "pts": [(0, 0), (20, 0), (10, 15)]}

rect            = extrude_profile(build_2D_sketch(ex_rect, sketch_plane="XZ"),            height=10)
circle          = extrude_profile(build_2D_sketch(ex_circle),          height=10)
ellipse         = extrude_profile(build_2D_sketch(ex_ellipse),         height=10)
trapezoid       = extrude_profile(build_2D_sketch(ex_trapezoid),       height=10)
slot            = extrude_profile(build_2D_sketch(ex_slot),            height=10)
regular_polygon = extrude_profile(build_2D_sketch(ex_regular_polygon), height=10)
polygon         = extrude_profile(build_2D_sketch(ex_polygon),         height=10)

ellipse_sym     = extrude_profile(build_2D_sketch(ex_ellipse),                    height=10, both=True)
circle_xz       = extrude_profile(build_2D_sketch(ex_circle, sketch_plane="XZ"), height=15)

#show(rect)
objects = [rect, circle, ellipse, trapezoid, slot, regular_polygon, polygon]
for obj in objects:
    show(obj)
    time.sleep(7)
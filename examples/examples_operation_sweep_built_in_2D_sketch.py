import time
import numpy as np
import cadquery as cq
from ocp_vscode import show
from profile_built_in_2D_sketch import build_2D_sketch
from utils import sweep_profile

# ----------------------------------------------------------------
# Profile builders — all using build_2D_sketch
# ----------------------------------------------------------------
def p_rect():
    return build_2D_sketch({"obj_type": "rectangle", "width": 0.4, "height": 0.2})

def p_circle():
    return build_2D_sketch({"obj_type": "circle", "radius": 0.3})

def p_ellipse():
    return build_2D_sketch({"obj_type": "ellipse", "r1": 0.4, "r2": 0.2})

def p_trapezoid():
    return build_2D_sketch({"obj_type": "trapezoid", "width": 0.4, "height": 0.2, "a1": 70})

def p_slot():
    return build_2D_sketch({"obj_type": "slot", "width": 0.5, "height": 0.2})

def p_hex():
    return build_2D_sketch({"obj_type": "regular_polygon", "radius": 0.3, "nmb_of_sides": 6})

def p_triangle():
    return build_2D_sketch({"obj_type": "regular_polygon", "radius": 0.3, "nmb_of_sides": 3})

def p_polygon():
    return build_2D_sketch({"obj_type": "polygon",
        "pts": [(-0.2,-0.2),(0.2,-0.2),(0.3,0.1),(0.0,0.3),(-0.3,0.1)]})

# ----------------------------------------------------------------
# Path builders (same as before)
# ----------------------------------------------------------------
def path_line_z():
    return cq.Wire.assembleEdges([
        cq.Edge.makeLine(cq.Vector(0,0,0), cq.Vector(0,0,20))])

def path_line_x():
    return cq.Wire.assembleEdges([
        cq.Edge.makeLine(cq.Vector(0,0,0), cq.Vector(20,0,0))])

def path_line_diag():
    return cq.Wire.assembleEdges([
        cq.Edge.makeLine(cq.Vector(0,0,0), cq.Vector(10,10,10))])

def path_helix_tall():
    return cq.Wire.makeHelix(pitch=3, height=30, radius=4)

def path_helix_tight():
    return cq.Wire.makeHelix(pitch=1, height=20, radius=2)

def path_spline_gentle():
    return cq.Wire.assembleEdges([cq.Edge.makeSpline([
        cq.Vector(0,0,0), cq.Vector(5,3,8), cq.Vector(10,0,15)])])

def path_spline_wave():
    return cq.Wire.assembleEdges([cq.Edge.makeSpline([
        cq.Vector(0,0,0), cq.Vector(5,4,5), cq.Vector(10,-4,10), cq.Vector(15,0,15)])])

def path_bezier():
    return cq.Wire.assembleEdges([cq.Edge.makeBezier([
        cq.Vector(0,0,0), cq.Vector(10,0,10), cq.Vector(10,10,20)])])

def path_arc():
    return cq.Wire.assembleEdges([cq.Edge.makeThreePointArc(
        cq.Vector(0,0,0), cq.Vector(5,5,3), cq.Vector(10,0,0))])

def path_analytical_helix():
    return lambda t: (2*np.sin(2*np.pi*t), 2*(np.cos(2*np.pi*t)-1), 15*t)

def path_analytical_spiral():
    return lambda t: (t*4*np.cos(2*np.pi*t), t*4*np.sin(2*np.pi*t), 8*t)

def path_analytical_wave():
    return lambda t: (15*t, 2*np.sin(2*np.pi*t), 0)

def path_analytical_s_curve():
    return lambda t: (10*t, 3*np.sin(np.pi*t), 3*(1-np.cos(np.pi*t)))

def path_tuple_z():
    return ((0,0,0), (0,0,20))

def path_tuple_diag():
    return ((0,0,0), (10,5,15))

# ----------------------------------------------------------------
# Examples
# ----------------------------------------------------------------
examples = [
    # --- line Z, all profiles ---
    # ("rect     + line Z",         p_rect(),     path_line_z()),
    # ("circle   + line Z",         p_circle(),   path_line_z()),
    # ("ellipse  + line Z",         p_ellipse(),  path_line_z()),
    # ("trapezoid + line Z",        p_trapezoid(),path_line_z()),
    # ("slot     + line Z",         p_slot(),     path_line_z()),
    # ("hexagon  + line Z",         p_hex(),      path_line_z()),
    # ("triangle + line Z",         p_triangle(), path_line_z()),
    # ("polygon  + line Z",         p_polygon(),  path_line_z()),

    # --- line X ---
    # ("rect     + line X",         p_rect(),     path_line_x()),
    # ("circle   + line X",         p_circle(),   path_line_x()),
    # ("ellipse  + line X",         p_ellipse(),  path_line_x()),
    # ("hexagon  + line X",         p_hex(),      path_line_x()),

    # # --- diagonal line ---
    # ("rect     + line diag",      p_rect(),     path_line_diag()),
    # ("circle   + line diag",      p_circle(),   path_line_diag()),
    # ("triangle + line diag",      p_triangle(), path_line_diag()),

    # --- helix tall, all profiles ---
    ("rect     + helix tall",     p_rect(),     path_helix_tall()),
    ("circle   + helix tall",     p_circle(),   path_helix_tall()),
    ("ellipse  + helix tall",     p_ellipse(),  path_helix_tall()),
    ("trapezoid + helix tall",    p_trapezoid(),path_helix_tall()),
    ("slot     + helix tall",     p_slot(),     path_helix_tall()),
    ("hexagon  + helix tall",     p_hex(),      path_helix_tall()),
    ("triangle + helix tall",     p_triangle(), path_helix_tall()),
    ("polygon  + helix tall",     p_polygon(),  path_helix_tall()),

    # --- helix tight ---
    ("rect     + helix tight",    p_rect(),     path_helix_tight()),
    ("circle   + helix tight",    p_circle(),   path_helix_tight()),
    ("ellipse  + helix tight",    p_ellipse(),  path_helix_tight()),

    # --- spline gentle ---
    ("rect     + spline gentle",  p_rect(),     path_spline_gentle()),
    ("circle   + spline gentle",  p_circle(),   path_spline_gentle()),
    ("ellipse  + spline gentle",  p_ellipse(),  path_spline_gentle()),
    ("slot     + spline gentle",  p_slot(),     path_spline_gentle()),
    ("polygon  + spline gentle",  p_polygon(),  path_spline_gentle()),

    # --- spline wave ---
    ("rect     + spline wave",    p_rect(),     path_spline_wave()),
    ("circle   + spline wave",    p_circle(),   path_spline_wave()),
    ("hexagon  + spline wave",    p_hex(),      path_spline_wave()),
    ("trapezoid + spline wave",   p_trapezoid(),path_spline_wave()),

    # --- bezier ---
    ("rect     + bezier",         p_rect(),     path_bezier()),
    ("circle   + bezier",         p_circle(),   path_bezier()),
    ("ellipse  + bezier",         p_ellipse(),  path_bezier()),
    ("slot     + bezier",         p_slot(),     path_bezier()),
    ("hexagon  + bezier",         p_hex(),      path_bezier()),

    # --- arc ---
    ("rect     + arc",            p_rect(),     path_arc()),
    ("circle   + arc",            p_circle(),   path_arc()),
    ("ellipse  + arc",            p_ellipse(),  path_arc()),
    ("triangle + arc",            p_triangle(), path_arc()),

    # --- analytical helix ---
    ("rect     + analytical helix",    p_rect(),     path_analytical_helix()),
    ("circle   + analytical helix",    p_circle(),   path_analytical_helix()),
    ("ellipse  + analytical helix",    p_ellipse(),  path_analytical_helix()),
    ("slot     + analytical helix",    p_slot(),     path_analytical_helix()),
    ("hexagon  + analytical helix",    p_hex(),      path_analytical_helix()),
    ("polygon  + analytical helix",    p_polygon(),  path_analytical_helix()),

    # --- analytical spiral ---
    ("rect     + analytical spiral",   p_rect(),     path_analytical_spiral()),
    ("circle   + analytical spiral",   p_circle(),   path_analytical_spiral()),
    ("ellipse  + analytical spiral",   p_ellipse(),  path_analytical_spiral()),
    ("trapezoid + analytical spiral",  p_trapezoid(),path_analytical_spiral()),

    # --- analytical wave ---
    ("rect     + analytical wave",     p_rect(),     path_analytical_wave()),
    ("circle   + analytical wave",     p_circle(),   path_analytical_wave()),
    ("hexagon  + analytical wave",     p_hex(),      path_analytical_wave()),

    # --- analytical S-curve ---
    ("rect     + analytical S-curve",  p_rect(),     path_analytical_s_curve()),
    ("circle   + analytical S-curve",  p_circle(),   path_analytical_s_curve()),
    ("ellipse  + analytical S-curve",  p_ellipse(),  path_analytical_s_curve()),
    ("slot     + analytical S-curve",  p_slot(),     path_analytical_s_curve()),

    # --- tuple paths ---
    ("rect     + tuple Z",        p_rect(),     path_tuple_z()),
    ("circle   + tuple Z",        p_circle(),   path_tuple_z()),
    ("ellipse  + tuple Z",        p_ellipse(),  path_tuple_z()),
    ("rect     + tuple diag",     p_rect(),     path_tuple_diag()),
    ("circle   + tuple diag",     p_circle(),   path_tuple_diag()),
]

for label, profile, path in examples:
    print(f"Showing: {label}")
    try:
        result = sweep_profile(profile, path)
        show(result)
    except Exception as e:
        print(f"  FAILED: {e}")
    time.sleep(1)
import time
import numpy as np
import cadquery as cq
from ocp_vscode import show
from profile_from_straight_connections import create_profile_from_straight_connections
from utils import sweep_profile

# ----------------------------------------------------------------
# Profile builders — all using create_profile_from_straight_connections
# ----------------------------------------------------------------
def p_rectangle():
    return create_profile_from_straight_connections(
        [(-0.2,-0.1),(0.2,-0.1),(0.2,0.1),(-0.2,0.1)], closed=True)

def p_triangle():
    return create_profile_from_straight_connections(
        [(0,0),(0.3,0),(0.15,0.3)], closed=True)

def p_trapezoid():
    return create_profile_from_straight_connections(
        [(-0.2,0),(0.2,0),(0.15,0.2),(-0.15,0.2)], closed=True)

def p_lshape():
    return create_profile_from_straight_connections(
        [(0,0),(0.3,0),(0.3,0.1),(0.1,0.1),(0.1,0.3),(0,0.3)], closed=True)

def p_pentagon():
    import math
    pts = [(0.25*math.cos(2*math.pi*i/5), 0.25*math.sin(2*math.pi*i/5)) for i in range(5)]
    return create_profile_from_straight_connections(pts, closed=True)

def p_star():
    import math
    pts = []
    for i in range(5):
        angle_out = 2*math.pi*i/5 - math.pi/2
        angle_in  = angle_out + math.pi/5
        pts.append((0.3*math.cos(angle_out), 0.3*math.sin(angle_out)))
        pts.append((0.12*math.cos(angle_in),  0.12*math.sin(angle_in)))
    return create_profile_from_straight_connections(pts, closed=True)

def p_custom():
    return create_profile_from_straight_connections(
        [(0,0),(0.4,0),(0.4,0.15),(0.25,0.3),(0.15,0.3),(0,0.15)], closed=True)

# ----------------------------------------------------------------
# Path builders
# ----------------------------------------------------------------
# Wire paths
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

# Analytical paths (must start at origin)
def path_analytical_helix():
    return lambda t: (2*np.sin(2*np.pi*t), 2*(np.cos(2*np.pi*t)-1), 15*t)

def path_analytical_spiral():
    return lambda t: (t*4*np.cos(2*np.pi*t), t*4*np.sin(2*np.pi*t), 8*t)

def path_analytical_wave():
    return lambda t: (15*t, 2*np.sin(2*np.pi*t), 0)

def path_analytical_s_curve():
    return lambda t: (10*t, 3*np.sin(np.pi*t), 3*(1-np.cos(np.pi*t)))

# Tuple paths
def path_tuple_z():
    return ((0,0,0), (0,0,20))

def path_tuple_diag():
    return ((0,0,0), (10,5,15))

# ----------------------------------------------------------------
# Examples
# ----------------------------------------------------------------
examples = [
    #--- straight line Z, all profiles ---
    ("rectangle + line Z",        p_rectangle(), path_line_z()),
    ("triangle  + line Z",        p_triangle(),  path_line_z()),
    ("trapezoid + line Z",        p_trapezoid(), path_line_z()),
    ("L-shape   + line Z",        p_lshape(),    path_line_z()),
    ("pentagon  + line Z",        p_pentagon(),  path_line_z()),
    ("star      + line Z",        p_star(),      path_line_z()),
    ("custom    + line Z",        p_custom(),    path_line_z()),

    # --- straight line X ---
    ("rectangle + line X",        p_rectangle(), path_line_x()),
    ("triangle  + line X",        p_triangle(),  path_line_x()),
    ("pentagon  + line X",        p_pentagon(),  path_line_x()),

    # --- diagonal line ---
    ("rectangle + line diag",     p_rectangle(), path_line_diag()),
    ("triangle  + line diag",     p_triangle(),  path_line_diag()),

    # --- helix tall ---
    ("rectangle + helix tall",    p_rectangle(), path_helix_tall()),
    ("triangle  + helix tall",    p_triangle(),  path_helix_tall()),
    ("trapezoid + helix tall",    p_trapezoid(), path_helix_tall()),
    ("L-shape   + helix tall",    p_lshape(),    path_helix_tall()),
    ("pentagon  + helix tall",    p_pentagon(),  path_helix_tall()),
    ("star      + helix tall",    p_star(),      path_helix_tall()),
    ("custom    + helix tall",    p_custom(),    path_helix_tall()),

    # --- helix tight ---
    ("rectangle + helix tight",   p_rectangle(), path_helix_tight()),
    ("triangle  + helix tight",   p_triangle(),  path_helix_tight()),

    # --- spline gentle ---
    ("rectangle + spline gentle", p_rectangle(), path_spline_gentle()),
    ("triangle  + spline gentle", p_triangle(),  path_spline_gentle()),
    ("trapezoid + spline gentle", p_trapezoid(), path_spline_gentle()),
    ("star      + spline gentle", p_star(),      path_spline_gentle()),

    # --- spline wave ---
    ("rectangle + spline wave",   p_rectangle(), path_spline_wave()),
    ("pentagon  + spline wave",   p_pentagon(),  path_spline_wave()),
    ("custom    + spline wave",   p_custom(),    path_spline_wave()),

    # --- bezier ---
    ("rectangle + bezier",        p_rectangle(), path_bezier()),
    ("triangle  + bezier",        p_triangle(),  path_bezier()),
    ("trapezoid + bezier",        p_trapezoid(), path_bezier()),
    ("L-shape   + bezier",        p_lshape(),    path_bezier()),

    # --- arc ---
    ("rectangle + arc",           p_rectangle(), path_arc()),
    ("triangle  + arc",           p_triangle(),  path_arc()),
    ("pentagon  + arc",           p_pentagon(),  path_arc()),

    # --- analytical helix ---
    ("rectangle + analytical helix",   p_rectangle(), path_analytical_helix()),
    ("triangle  + analytical helix",   p_triangle(),  path_analytical_helix()),
    ("trapezoid + analytical helix",   p_trapezoid(), path_analytical_helix()),
    ("star      + analytical helix",   p_star(),      path_analytical_helix()),
    ("custom    + anal. helix",   p_custom(),    path_analytical_helix()),

    # --- analytical spiral ---
    ("rectangle + analytical spiral",  p_rectangle(), path_analytical_spiral()),
    ("triangle  + analytical spiral",  p_triangle(),  path_analytical_spiral()),
    ("L-shape   + analytical spiral",  p_lshape(),    path_analytical_spiral()),

    # --- analytical wave ---
    ("rectangle + analytical wave",    p_rectangle(), path_analytical_wave()),
    ("triangle  + analytical wave",    p_triangle(),  path_analytical_wave()),
    ("pentagon  + analytical wave",    p_pentagon(),  path_analytical_wave()),

    # --- analytical S-curve ---
    ("rectangle + analytical S-curve", p_rectangle(), path_analytical_s_curve()),
    ("triangle  + analytical. S-curve", p_triangle(),  path_analytical_s_curve()),
    ("custom    + analytical S-curve", p_custom(),    path_analytical_s_curve()),

    # --- tuple paths ---
    ("rectangle + tuple Z",       p_rectangle(), path_tuple_z()),
    ("triangle  + tuple Z",       p_triangle(),  path_tuple_z()),
    ("rectangle + tuple diag",    p_rectangle(), path_tuple_diag()),
    ("star      + tuple diag",    p_star(),      path_tuple_diag()),
]

for label, profile, path in examples:
    print(f"Showing: {label}")
    try:
        result = sweep_profile(profile, path)
        show(result)
    except Exception as e:
        print(f"  FAILED: {e}")
    time.sleep(1)
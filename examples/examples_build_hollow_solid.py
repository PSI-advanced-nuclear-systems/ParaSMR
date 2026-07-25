"""
zz_examples_build_solid.py
==========================
Illustrative examples for build_solid() covering:
  - All 3 operations: extrude, revolve, sweep
  - All built-in 2D profile types: circle, rectangle, ellipse, trapezoid,
    slot, regular_polygon, polygon
  - Straight-connection (freeform) profiles
  - Solid vs hollow (wall_thickness) variants
  - Positioning: center_coords, center_coords_pol, rotation_angles

Run one SECTION at a time in ocp_vscode by executing only that block.
Each section ends with a show() call.
"""

import math
import cadquery as cq
from ocp_vscode import show
from build_3D_solid import build_solid
import time

# ============================================================
# SHARED PATH WIRES  (reused across sections)
# ============================================================

# Straight vertical path  (0,0,0) -> (0,0,30)
PATH_STRAIGHT = ((0, 0, 0), (0, 0, 30))

# L-shaped path: go up 20, then sideways 20
PATH_L = cq.Wire.assembleEdges([
    cq.Edge.makeLine(cq.Vector(0,  0, 0),  cq.Vector(0,  0, 20)),
    cq.Edge.makeLine(cq.Vector(0,  0, 20), cq.Vector(20, 0, 20)),
])

# U-shaped path: up 20, arc across, down 20
# PATH_U = cq.Wire.assembleEdges([
#     cq.Edge.makeLine(cq.Vector(0,  0, 0),  cq.Vector(0,  0, 20)),
#     cq.Edge.makeThreePointArc(
#         cq.Vector(0, 0, 20), cq.Vector(10, 0, 25), cq.Vector(20, 0, 20)
#     ),
#     cq.Edge.makeLine(cq.Vector(20, 0, 20), cq.Vector(20, 0, 0)),
# ])
PATH_U = cq.Wire.assembleEdges([
    cq.Edge.makeLine(cq.Vector(0,  0, 0),  cq.Vector(0,  0, 20)),
    cq.Edge.makeThreePointArc(
        cq.Vector(0, 0, 20), cq.Vector(10, 0, 30), cq.Vector(20, 0, 20)  # 30 instead of 25
    ),
    cq.Edge.makeLine(cq.Vector(20, 0, 20), cq.Vector(20, 0, 0)),
])

# Helix path
PATH_HELIX = cq.Wire.makeHelix(pitch=10, height=40, radius=8)

# Shared freeform point lists
TRI_PTS  = [(0, 0), (10, 0), (5, 8)]
T_PTS    = [(-5,0),(5,0),(5,1),(1,1),(1,6),(-1,6),(-1,1),(-5,1)]
L_PTS_2D = [(0,0),(8,0),(8,3),(3,3),(3,8),(0,8)]
PENT_PTS = [(math.cos(math.radians(90 + i*72))*6,
             math.sin(math.radians(90 + i*72))*6) for i in range(5)]


# ============================================================
# SECTION 1 — EXTRUDE: built-in 2D profiles
# Solid on left, hollow counterpart offset +20 in X
# ============================================================

e_circle_s, _   = build_solid("extrude", {"obj_type": "circle",          "radius": 4},                    height=15)
e_circle_h, _   = build_solid("extrude", {"obj_type": "circle",          "radius": 4},                    height=15, wall_thickness=1.0,  center_coords=(20,  0, 0))

e_rect_s, _     = build_solid("extrude", {"obj_type": "rectangle",       "width": 8,  "height": 5},       height=15, center_coords=(45,  0, 0))
e_rect_h, _     = build_solid("extrude", {"obj_type": "rectangle",       "width": 8,  "height": 5},       height=15, wall_thickness=1.2,  center_coords=(65,  0, 0))

e_ellipse_s, _  = build_solid("extrude", {"obj_type": "ellipse",         "r1": 6,     "r2": 3},           height=12, center_coords=(90,  0, 0))
e_ellipse_h, _  = build_solid("extrude", {"obj_type": "ellipse",         "r1": 6,     "r2": 3},           height=12, wall_thickness=1.0,  center_coords=(110, 0, 0))

e_slot_s, _     = build_solid("extrude", {"obj_type": "slot",            "width": 12, "height": 4},       height=10, center_coords=(132, 0, 0))
e_slot_h, _     = build_solid("extrude", {"obj_type": "slot",            "width": 12, "height": 4},       height=10, wall_thickness=0.8,  center_coords=(152, 0, 0))

e_trap_s, _     = build_solid("extrude", {"obj_type": "trapezoid",       "width": 10, "height": 6, "a1": 70}, height=12, center_coords=(174, 0, 0))
e_trap_h, _     = build_solid("extrude", {"obj_type": "trapezoid",       "width": 10, "height": 6, "a1": 70}, height=12, wall_thickness=1.0,  center_coords=(194, 0, 0))

e_hex_s, _      = build_solid("extrude", {"obj_type": "regular_polygon", "radius": 5, "nmb_of_sides": 6}, height=14, center_coords=(216, 0, 0))
e_hex_h, _      = build_solid("extrude", {"obj_type": "regular_polygon", "radius": 5, "nmb_of_sides": 6}, height=14, wall_thickness=1.0,  center_coords=(234, 0, 0))

e_poly_s, _     = build_solid("extrude", {"obj_type": "polygon",         "pts": L_PTS_2D},                height=10, center_coords=(252, 0, 0))
e_poly_h, _     = build_solid("extrude", {"obj_type": "polygon",         "pts": L_PTS_2D},                height=10, wall_thickness=0.8,  center_coords=(270, 0, 0))

show(e_circle_s, e_circle_h,
     e_rect_s,   e_rect_h,
     e_ellipse_s,e_ellipse_h,
     e_slot_s,   e_slot_h,
     e_trap_s,   e_trap_h,
     e_hex_s,    e_hex_h,
     e_poly_s,   e_poly_h)
time.sleep(3)  

# ============================================================
# SECTION 2 — EXTRUDE: straight-connection (freeform) profiles
# ============================================================

e_tri_s, _  = build_solid("extrude", TRI_PTS,  height=12)
e_tri_h, _  = build_solid("extrude", TRI_PTS,  height=12, wall_thickness=1.0, center_coords=(20, 0, 0))

e_pent_s, _ = build_solid("extrude", PENT_PTS, height=10, center_coords=(40, 0, 0))
e_pent_h, _ = build_solid("extrude", PENT_PTS, height=10, wall_thickness=1.0, center_coords=(60, 0, 0))

e_T_s, _    = build_solid("extrude", T_PTS,    height=40, center_coords=(80, 0, 0))
e_T_h, _    = build_solid("extrude", T_PTS,    height=40, wall_thickness=0.3, center_coords=(96, 0, 0))

show(e_tri_s, e_tri_h, e_pent_s, e_pent_h, e_T_s, e_T_h)
time.sleep(3)  

# ============================================================
# SECTION 3 — REVOLVE: built-in 2D profiles
# All use plane="XZ", axis="Z", axis_point offset in X
# ============================================================

# Circle 360° → torus
r_torus_s, _    = build_solid("revolve", {"obj_type": "circle",          "radius": 2},
                               plane="XZ", axis="Z", axis_point=(8, 0, 0), angle=360)
r_torus_h, _    = build_solid("revolve", {"obj_type": "circle",          "radius": 2},
                               plane="XZ", axis="Z", axis_point=(8, 0, 0), angle=360,
                               wall_thickness=0.5, center_coords=(28, 0, 0))

# Rectangle 360° → cylinder / pipe
r_cyl_s, _      = build_solid("revolve", {"obj_type": "rectangle",       "width": 2, "height": 10},
                               plane="XZ", axis="Z", axis_point=(6, 0, 0), angle=360,
                               center_coords=(50, 0, 0))
r_cyl_h, _      = build_solid("revolve", {"obj_type": "rectangle",       "width": 2, "height": 10},
                               plane="XZ", axis="Z", axis_point=(6, 0, 0), angle=360,
                               wall_thickness=0.4, center_coords=(66, 0, 0))

# Trapezoid 360° → cone frustum
r_frus_s, _     = build_solid("revolve", {"obj_type": "trapezoid",       "width": 4, "height": 8, "a1": 75},
                               plane="XZ", axis="Z", axis_point=(6, 0, 0), angle=360,
                               center_coords=(86, 0, 0))
r_frus_h, _     = build_solid("revolve", {"obj_type": "trapezoid",       "width": 4, "height": 8, "a1": 75},
                               plane="XZ", axis="Z", axis_point=(6, 0, 0), angle=360,
                               wall_thickness=0.6, center_coords=(104, 0, 0))

# Rectangle 270° → 3/4 arc solid
r_arc_s, _      = build_solid("revolve", {"obj_type": "rectangle",       "width": 3, "height": 8},
                               plane="XZ", axis="Z", axis_point=(8, 0, 0), angle=270,
                               center_coords=(124, 0, 0))

# Ellipse 360° → elliptical torus
r_eltorus_s, _  = build_solid("revolve", {"obj_type": "ellipse",         "r1": 3, "r2": 1.5},
                               plane="XZ", axis="Z", axis_point=(9, 0, 0), angle=360,
                               center_coords=(144, 0, 0))
r_eltorus_h, _  = build_solid("revolve", {"obj_type": "ellipse",         "r1": 3, "r2": 1.5},
                               plane="XZ", axis="Z", axis_point=(9, 0, 0), angle=360,
                               wall_thickness=0.7, center_coords=(162, 0, 0))

show(r_torus_s,  r_torus_h,
     r_cyl_s,    r_cyl_h,
     r_frus_s,   r_frus_h,
     r_arc_s,
     r_eltorus_s,r_eltorus_h)
time.sleep(3)

# ============================================================
# SECTION 4 — SWEEP: built-in 2D profiles
# ============================================================

# Circle — straight path → rod / pipe
sw_rod_s, _     = build_solid("sweep", {"obj_type": "circle",            "radius": 3},            path=PATH_STRAIGHT)
sw_rod_h, _     = build_solid("sweep", {"obj_type": "circle",            "radius": 3},            path=PATH_STRAIGHT, wall_thickness=0.8, center_coords=(14,  0, 0))

# Circle — L-path → L-bend pipe  (KEY motivating use case)
sw_Lrod_s, _    = build_solid("sweep", {"obj_type": "circle",            "radius": 3},            path=PATH_L,        center_coords=(30,  0, 0))
sw_Lrod_h, _    = build_solid("sweep", {"obj_type": "circle",            "radius": 3},            path=PATH_L,        wall_thickness=0.8, center_coords=(60,  0, 0))

# Circle — U-path → U-bend hollow pipe
sw_Urod_h, _    = build_solid("sweep", {"obj_type": "circle",            "radius": 3},            path=PATH_U,        wall_thickness=0.8, center_coords=(90,  0, 0))

# Rectangle — L-path → rectangular duct with bend
sw_duct_s, _    = build_solid("sweep", {"obj_type": "rectangle",         "width": 6, "height": 4}, path=PATH_L,      center_coords=(120, 0, 0))
sw_duct_h, _    = build_solid("sweep", {"obj_type": "rectangle",         "width": 6, "height": 4}, path=PATH_L,      wall_thickness=0.8, center_coords=(150, 0, 0))

# Ellipse — U-path → hollow elliptical tube
sw_eltube_h, _  = build_solid("sweep", {"obj_type": "ellipse",           "r1": 3, "r2": 1.5},     path=PATH_U,        wall_thickness=0.5, center_coords=(178, 0, 0))

# Hexagon — helix path → solid helical rod
sw_helix_s, _   = build_solid("sweep", {"obj_type": "regular_polygon",   "radius": 2, "nmb_of_sides": 6}, path=PATH_HELIX, center_coords=(205, 0, 0))

# Rectangle — helix path → hollow helical duct
sw_helix_h, _   = build_solid("sweep", {"obj_type": "rectangle",         "width": 4, "height": 2}, path=PATH_HELIX,  wall_thickness=0.4, center_coords=(230, 0, 0))

show(sw_rod_s,   sw_rod_h,
     sw_Lrod_s,  sw_Lrod_h,
     sw_Urod_h,
     sw_duct_s,  sw_duct_h,
     sw_eltube_h,
     sw_helix_s, sw_helix_h)
time.sleep(3)

# ============================================================
# SECTION 5 — SWEEP: straight-connection (freeform) profiles
# ============================================================

sw_tri_s, _  = build_solid("sweep", TRI_PTS,  path=PATH_STRAIGHT)
sw_tri_h, _  = build_solid("sweep", TRI_PTS,  path=PATH_STRAIGHT, wall_thickness=0.8, center_coords=(18, 0, 0))

sw_T_s, _    = build_solid("sweep", T_PTS,    path=PATH_L,        center_coords=(36, 0, 0))

sw_pent_h, _ = build_solid("sweep", PENT_PTS, path=PATH_U,        wall_thickness=0.8, center_coords=(70, 0, 0))

show(sw_tri_s, sw_tri_h, sw_T_s, sw_pent_h)
time.sleep(3)

# ============================================================
# SECTION 6 — POSITIONING & ROTATION
# ============================================================

p_base, _   = build_solid("extrude", {"obj_type": "rectangle", "width": 6, "height": 3}, height=10)

# 90° pitch → lying on its side
p_pitch, _  = build_solid("extrude", {"obj_type": "rectangle", "width": 6, "height": 3}, height=10,
                           rotation_angles=(0, 90, 0), center_coords=(20, 0, 0))

# 45° roll
p_roll, _   = build_solid("extrude", {"obj_type": "rectangle", "width": 6, "height": 3}, height=10,
                           rotation_angles=(45, 0, 0), center_coords=(40, 0, 0))

# 30° yaw
p_yaw, _    = build_solid("extrude", {"obj_type": "rectangle", "width": 6, "height": 3}, height=10,
                           rotation_angles=(0, 0, 30), center_coords=(60, 0, 0))

# Hollow pipe placed via polar coordinates (r=15, theta=45°, z=5)
p_polar, _  = build_solid("extrude", {"obj_type": "circle",    "radius": 4},             height=12,
                           wall_thickness=1.0,
                           center_coords_pol=(15, math.radians(45), 5))

# Rotation + polar placement combined
p_combo, _  = build_solid("extrude", {"obj_type": "ellipse",   "r1": 5, "r2": 2},        height=8,
                           rotation_angles=(0, 45, 0),
                           center_coords_pol=(25, math.radians(120), 0))

show(p_base, p_pitch, p_roll, p_yaw, p_polar, p_combo)
time.sleep(3)
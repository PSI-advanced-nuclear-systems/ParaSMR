import time
import cadquery as cq
from ocp_vscode import show
from profile_from_straight_connections import create_profile_from_straight_connections
from utils import extrude_profile

examples = []

# 1: Simple rectangle extruded upward (XY plane)
profile = create_profile_from_straight_connections(
    [(0,0), (2,0), (2,1), (0,1)], plane="XY", closed=True)
examples.append(("Rectangle extruded in Z (XY plane)",
    extrude_profile(profile, height=2.0)))

# 2: L-shape extruded (XY plane)
profile = create_profile_from_straight_connections(
    [(0,0), (3,0), (3,1), (1,1), (1,3), (0,3)], plane="XY", closed=True)
examples.append(("L-shape extruded in Z (XY plane)",
    extrude_profile(profile, height=1.0)))

# 3: Triangle extruded (XY plane)
profile = create_profile_from_straight_connections(
    [(0,0), (3,0), (1.5,2.5)], plane="XY", closed=True)
examples.append(("Triangle extruded in Z (XY plane)",
    extrude_profile(profile, height=1.5)))

# 4: Symmetric extrusion (both=True)
profile = create_profile_from_straight_connections(
    [(0,0), (2,0), (2,1), (0,1)], plane="XY", closed=True)
examples.append(("Rectangle symmetric extrusion (both=True)",
    extrude_profile(profile, height=1.5, both=True)))

# 5: Extruded in XZ plane (extrudes along Y)
profile = create_profile_from_straight_connections(
    [(0,0), (2,0), (2,1), (0,1)], plane="XZ", closed=True)
examples.append(("Rectangle extruded in Y (XZ plane)",
    extrude_profile(profile, height=2.0)))

# 6: Extruded in YZ plane (extrudes along X)
profile = create_profile_from_straight_connections(
    [(0,0), (2,0), (2,1), (0,1)], plane="YZ", closed=True)
examples.append(("Rectangle extruded in X (YZ plane)",
    extrude_profile(profile, height=2.0)))

# 7: Pentagon (XY plane)
import math
n, r = 5, 2.0
pts = [(r*math.cos(2*math.pi*i/n), r*math.sin(2*math.pi*i/n)) for i in range(n)]
profile = create_profile_from_straight_connections(pts, plane="XY", closed=True)
examples.append(("Pentagon extruded in Z (XY plane)",
    extrude_profile(profile, height=1.0)))

# 8: Vase-like profile (XY plane)
profile = create_profile_from_straight_connections(
    [(0,0), (2,0), (2,0.5), (1.5,0.5), (1.5,2.5), (2,2.5), (2,3), (0,3)],
    plane="XY", closed=True)
examples.append(("Vase-like profile extruded in Z (XY plane)",
    extrude_profile(profile, height=0.5)))

for label, solid in examples:
    print(label)
    show(solid)
    time.sleep(1)
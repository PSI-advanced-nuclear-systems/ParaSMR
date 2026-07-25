import time
import cadquery as cq
from ocp_vscode import show
from profile_from_straight_connections import create_profile_from_straight_connections
from utils import revolve_profile



pts = [(0,0), (1,0), (1,1), (2,2), (2,3), (0,3)]
profile = create_profile_from_straight_connections(pts, plane="XZ", closed=True)
solid_no_hole = revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0, 0, 0))
show(solid_no_hole)

#pts = [(0,0), (1,0), (1,1), (2,2), (2,3), (0,3)]
#profile = create_profile_from_straight_connections(pts, plane="XZ") #, closed=True)

# No hole — axis along left edge
#solid_no_hole = revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0, 0, 0))
#show(solid_no_hole)

#pts = [(0,0), (1,0), (1,1), (2,2), (2,3), (0,3)]

#profile = create_profile_from_straight_connections(pts, plane="XZ")#, closed=True)

# No hole — axis along left edge
#solid_no_hole = revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0, 0, 0))

# Small hole
# solid_small_hole = revolve_profile_global(profile, angle=360.0, axis="Z", axis_point=(0, 0, 0))
# solid_small_hole = revolve_profile_global(profile, angle=360.0, axis="Z", axis_point=(-1, 0, 0))
# Large hole
#solid_large_hole = revolve_profile_global(profile, angle=360.0, axis="Z", axis_point=(-5, 0, 0))

# Partial revolve — 180°
# solid_half = revolve_profile_global(profile, angle=180.0, axis="Z", axis_point=(0, 0, 0))





#pts = [(0,0), (1,0), (1,1), (2,2), (2,3), (0,3)]

#profile = create_profile_from_straight_connections(pts, closed=True)

#solid_no_hole = revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0, 0, 0))
#show(solid_no_hole)















examples = []

# 1: Full 360° vase-like solid around Z, XZ plane
profile = create_profile_from_straight_connections(
    [(0,0), (1,0), (1,1), (2,2), (2,3), (0,3)], plane="XZ", closed=True)
examples.append(("Full 360 vase around Z (XZ plane)", 
    revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0,0,0))))

# 2: Partial 180° vase around Z, XZ plane
profile = create_profile_from_straight_connections(
    [(0,0), (1,0), (1,1), (2,2), (2,3), (0,3)], plane="XZ", closed=True)
examples.append(("Partial 180 vase around Z (XZ plane)",
    revolve_profile(profile, angle=180.0, axis="Z", axis_point=(0,0,0))))

# 3: Rectangle offset from Z → ring/torus, XZ plane
profile = create_profile_from_straight_connections(
    [(1,0), (2,0), (2,1), (1,1)], plane="XZ", closed=True)
examples.append(("Ring offset from Z (XZ plane)",
    revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0,0,0))))

# 4: Rectangle, XY plane, revolve around Y
profile = create_profile_from_straight_connections(
    [(1,0), (2,0), (2,1), (1,1)], plane="XY", closed=True)
examples.append(("Rectangle around Y (XY plane)",
    revolve_profile(profile, angle=360.0, axis="Y", axis_point=(0,0,0))))

# 5: Triangle → cone, XZ plane, around Z
profile = create_profile_from_straight_connections(
    [(0,0), (2,0), (0,3)], plane="XZ", closed=True)
examples.append(("Triangle cone around Z (XZ plane)",
    revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0,0,0))))

# 6: Rectangle, YZ plane, revolve around Y
profile = create_profile_from_straight_connections(
    [(1,0), (2,0), (2,1), (1,1)], plane="YZ", closed=True)
examples.append(("Rectangle around Y (YZ plane)",
    revolve_profile(profile, angle=360.0, axis="Y", axis_point=(0,0,0))))

# 7: Rectangle, YZ plane, revolve around Z
profile = create_profile_from_straight_connections(
    [(1,0), (2,0), (2,1), (1,1)], plane="YZ", closed=True)
examples.append(("Rectangle around Z (YZ plane)",
    revolve_profile(profile, angle=360.0, axis="Z", axis_point=(0,0,0))))

# 8: Partial 90° rectangle around Z, XZ plane
profile = create_profile_from_straight_connections(
    [(1,0), (2,0), (2,1), (1,1)], plane="XZ", closed=True)
examples.append(("Partial 90 rectangle around Z (XZ plane)",
    revolve_profile(profile, angle=90.0, axis="Z", axis_point=(0,0,0))))

# 9: Axis offset — ring orbiting displaced Z axis
profile = create_profile_from_straight_connections(
    [(0,0), (0.5,0), (0.5,0.5), (0,0.5)], plane="XZ", closed=True)
examples.append(("Ring orbiting Z axis offset to x=3",
    revolve_profile(profile, angle=360.0, axis="Z", axis_point=(3,0,0))))

# 10: Vase partial 270° around Z, XZ plane
profile = create_profile_from_straight_connections(
    [(0,0), (1,0), (1,1), (2,2), (2,3), (0,3)], plane="XZ", closed=True)
examples.append(("Partial 270 vase around Z (XZ plane)",
    revolve_profile(profile, angle=270.0, axis="Z", axis_point=(0,0,0))))

# for label, solid in examples:
#     print(label)
#     show(solid)
#     time.sleep(2)
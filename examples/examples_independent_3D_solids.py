import time
import math
import cadquery as cq
from ocp_vscode import show
from build_3D_solid import build_solid

examples = [
    ("Extruded rectangle",
     "extrude",
     {"obj_type": "rectangle", "width": 10, "height": 6},
     {"height": 20, "plane": "XY"}),

    ("Revolved circle (full torus)",
     "revolve",
     {"obj_type": "circle", "radius": 3},
     {"angle": 360, "plane": "XZ", "axis": "Z", "axis_point": (-8, 0, 0)}),

    ("Extruded hexagon",
     "extrude",
     {"obj_type": "regular_polygon", "radius": 5, "nmb_of_sides": 6},
     {"height": 15, "plane": "XY"}),

    ("Revolved trapezoid (180°)",
     "revolve",
     {"obj_type": "trapezoid", "width": 8, "height": 5, "a1": 70},
     {"angle": 180, "plane": "XZ", "axis": "Z", "axis_point": (-10, 0, 0)}),

    ("Swept ellipse along straight path",
     "sweep",
     {"obj_type": "ellipse", "r1": 4, "r2": 2},
     {"path": cq.Wire.assembleEdges([
         cq.Edge.makeLine(cq.Vector(0,0,0), cq.Vector(0,0,30))
     ])}),
]
for label, operation, profile, kwargs in examples:
    print(f"Showing: {label}")
    solid, obj_id = build_solid(operation, profile, **kwargs)
    show(solid)
    print(f"Created: {obj_id}")
    time.sleep(1)


# ================================================================================================
# EXAMPLE: SMR primary loop - vessel, core, steam generators (polar coordinates)
# Dimensions in meters
# ================================================================================================

REACTOR_CORE = {
    "obj_id": "core",
    "obj_type": "cylinder",
    "height": 1.3,
    "radius": 2 / 2,
    "center_coords": (0, 0, 1.5),
    "rotation_angles": (0, 0, 0)
}

REACTOR_VESSEL = {
    "obj_id": "rpv",
    "obj_type": "cylinder_closed_bottom",
    "height": 5.5,
    "outer_radius": 4.8 / 2,
    "wall_thickness": 0.04,
    "bottom_thickness": 5.5 - 4.3,
    "center_coords_pol": (0, 0, 0)
}

REACTOR_HX_RADIUS = 1.7
EXAMPLE_3 = [REACTOR_CORE, REACTOR_VESSEL] + [
    {
        "obj_id": f"hx{i + 1}",
        "obj_type": "cylinder",
        "height": 2,
        "radius": 0.25,
        "center_coords_pol": (REACTOR_HX_RADIUS, i * math.pi / 2, 3.5)
    }
    for i in range(4)
]

solid1, id1 = build_solid("primitive", REACTOR_CORE)        # single primitive
print(f"Created: {id1}")
time.sleep(1)

solid2, id2 = build_solid("primitive", REACTOR_VESSEL)      # single primitive
print(f"Created: {id2}")    
import math
import time
import cadquery as cq
from ocp_vscode import show
from assemble import assemble_objects

# ----------------------------------------------------------------
# SWEEP — circle profile along a tight helix path
# ----------------------------------------------------------------
example_sweep_built_in_2D = {
    "obj_id": "circle_helix_tight",
    "operation": "sweep",
    "profile": {"obj_type": "circle", "radius": 0.3},
    "path": cq.Wire.makeHelix(pitch=1, height=20, radius=2),
}
assembly = assemble_objects([example_sweep_built_in_2D,
                             ])
#show(assembly)
time.sleep(1)




# ----------------------------------------------------------------
# SWEEP — pentagon profile from straight connections along an arc path
# ----------------------------------------------------------------
example_sweep_straight_connections = {
    "obj_id": "pentagon_arc",
    "operation": "sweep",
    "profile": [(0.25 * math.cos(2 * math.pi * i / 5),
                 0.25 * math.sin(2 * math.pi * i / 5)) for i in range(5)],
    "path": cq.Wire.assembleEdges([cq.Edge.makeThreePointArc(
        cq.Vector(0, 0, 0), cq.Vector(5, 5, 3), cq.Vector(10, 0, 0))]),
}
assembly = assemble_objects([example_sweep_straight_connections,
                             ])
#show(assembly)
time.sleep(1)




# ----------------------------------------------------------------
# EXTRUDE — vase-like profile from straight connections, extruded in Z
# ----------------------------------------------------------------
example_extrude_straight_connections = {
    "obj_id": "vase_profile",
    "operation": "extrude",
    "profile": [(0, 0), (2, 0), (2, 0.5), (1.5, 0.5),
                (1.5, 2.5), (2, 2.5), (2, 3), (0, 3)],
    "plane": "XY",
    "height": 0.5,
}
assembly = assemble_objects([example_extrude_straight_connections,
                             ])
#show(assembly)
time.sleep(1)





# ----------------------------------------------------------------
# EXTRUDE — built-in ellipse sketch, extruded in Z
# ----------------------------------------------------------------
example_extrude_built_in_2D = {
    "obj_id": "ellipse_extrude",
    "operation": "extrude",
    "profile": {"obj_type": "ellipse", "r1": 12, "r2": 6},
    "plane": "XY",
    "height": 10,
}
assembly = assemble_objects([example_extrude_built_in_2D,
                             ])
#show(assembly)
time.sleep(1)





# ----------------------------------------------------------------
# REVOLVE — stepped profile from straight connections, full 360° about Z
# ----------------------------------------------------------------
example_revolve_straight_connections = {
    "obj_id": "revolved_stepped_profile",
    "operation": "revolve",
    "profile": [(0, 0), (1, 0), (1, 1), (2, 2), (2, 3), (0, 3)],
    "plane": "XZ",
    "angle": 360.0,
    "axis": "Z",
    "axis_point": (0, 0, 0),
}
assembly = assemble_objects([example_revolve_straight_connections,
                             ])
#show(assembly)
time.sleep(1)






# ----------------------------------------------------------------
# REVOLVE — built-in trapezoid sketch, 90° about Z at x = -10
# ----------------------------------------------------------------
example_revolve_built_in_2D = {
    "obj_id": "trapezoid_revolve_z_90",
    "operation": "revolve",
    "profile": {"obj_type": "trapezoid", "width": 10, "height": 6, "a1": 70},
    "plane": "XZ",
    "angle": 90.0,
    "axis": "Z",
    "axis_point": (-10, 0, 0),
}

assembly = assemble_objects([example_revolve_built_in_2D,
                             ])
show(assembly)
time.sleep(1)

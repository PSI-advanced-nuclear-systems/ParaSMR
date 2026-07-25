from assemble import assemble_objects
from ocp_vscode import show

# ─────────────────────────────────────────────────────────────────────────
# Example 1: Cylindrical Core
# ─────────────────────────────────────────────────────────────────────────
# A simple circular cylinder (n_sides=None or omitted defaults to cylinder)

CORE_CYLINDER = {
    "obj_type": "reactor_core",
    "obj_id": "core_cylinder",
    "radius": 1.5,          
    "height": 2.0,         
    "z_bottom": 0.0,       
}

assy_cylinder = assemble_objects([CORE_CYLINDER])
show(assy_cylinder)


# ─────────────────────────────────────────────────────────────────────────
# Example 2: Hexagonal Core (6-sided polygon)
# ─────────────────────────────────────────────────────────────────────────
# A regular hexagon prism. The radius is the circumscribed radius, i.e.,
# the distance from the center to any vertex (circumcircle radius).
# Common in SFR lattice designs.

CORE_HEXAGON = {
    "obj_type": "reactor_core",
    "obj_id": "core_hexagon",
    "radius": 1.5,          
    "height": 2.0,         
    "z_bottom": 0.0,
    "n_sides": 6,          
}

assy_hexagon = assemble_objects([CORE_HEXAGON])
#show(assy_hexagon)

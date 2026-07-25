"""
3D primitive shape generation module using CadQuery.

Provides functionality to define and construct 3D primitive shapes (box, cylinder,
sphere, wedge, pipe, cylinder_closed_bottom) with support for positioning in
Cartesian or polar coordinates and rotation operations.
"""

from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, cast
import math
import logging
import cadquery as cq
from ocp_vscode import show
from utils import rotate_rpy_about_self_global_axes, move_center_to

# Configure logging
logger = logging.getLogger(__name__)

# Constants
TOLERANCE = 1e-6
EPSILON = 0.02  # Small offset for cylinder cutout operations


class ShapeType(Enum):
    """Supported 3D primitive shape types."""
    BOX = "box"
    CYLINDER = "cylinder"
    SPHERE = "sphere"
    WEDGE = "wedge"
    CYLINDER_CLOSED_BOTTOM = "cylinder_closed_bottom"
    PIPE = "pipe"  


# Required parameters for each shape type
REQUIRED_PARAMS: Dict[ShapeType, set] = {
    ShapeType.BOX: {"length", "width", "height"},
    ShapeType.CYLINDER: {"height", "radius"},
    ShapeType.SPHERE: {"radius"},
    ShapeType.WEDGE: {"dx", "dy", "dz", "xmin", "zmin", "xmax", "zmax"},
    ShapeType.CYLINDER_CLOSED_BOTTOM: {"height", "outer_radius", "wall_thickness"},
    ShapeType.PIPE: {"height"},  # any two of {outer_radius, inner_radius, wall_thickness} also required, checked at build time
}


# Maps hollow primitive types to their solid outer envelope profile.
# Add new hollow primitives here — the builder dispatch never needs to change.
OUTER_PROFILE_BUILDERS: Dict[str, Any] = {
    "pipe": lambda p: {"obj_type": "cylinder", "height": p["height"], "radius": p["outer_radius"]},
    "cylinder_closed_bottom": lambda p: {"obj_type": "cylinder", "height": p["height"], "radius": p["outer_radius"]},
}

def get_outer_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return the solid outer envelope profile for any primitive, hollow or not."""
    obj_type = profile.get("obj_type", "")
    if obj_type in OUTER_PROFILE_BUILDERS:
        return OUTER_PROFILE_BUILDERS[obj_type](profile)
    return profile  # already solid, outer = itself



def _polar_to_cartesian(r: float, theta: float, z: float) -> Tuple[float, float, float]:
    """
    Convert polar coordinates to Cartesian coordinates.
    Args:
        r: Radial distance
        theta: Angle in radians
        z: Height (unchanged in conversion)
    Returns:
        Tuple of (x, y, z) in Cartesian coordinates
    """
    return (r * math.cos(theta), r * math.sin(theta), z)


def _extract_position(obj: Dict[str, Any], index: int) -> Optional[Tuple[float, float, float]]:
    """
    Extract position from object, supporting both Cartesian and polar coordinates.
    Args:
        obj: Shape configuration dictionary
        index: Index in list (for error messages)
    Returns:
        Tuple of (x, y, z) coordinates or None if no position specified
    Raises:
        ValueError: If both coordinate types specified or polar conversion fails
    """
    cartesian = obj.get("center_coords")
    polar = obj.get("center_coords_pol")
    
    if cartesian and polar: raise ValueError(f"Cannot specify both 'center_coords' and 'center_coords_pol' at index {index}")
    
    if cartesian: return cartesian
    
    if polar:
        try:
            r, theta, z = polar
            return _polar_to_cartesian(r, theta, z)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid polar coordinates at index {index}: {polar}. Error: {e}"
            )
    
    return None


def _get_rotation_angles(obj: Dict[str, Any]) -> Tuple[float, float, float]:
    """
    Extract rotation angles (roll, pitch, yaw) in degrees.
    Args:
        obj: Shape configuration dictionary
    Returns:
        Tuple of (roll, pitch, yaw) in degrees, defaults to (0, 0, 0)
    """
    return obj.get("rotation_angles", (0, 0, 0))


def _validate_shape_type(obj: Dict[str, Any], index: int) -> ShapeType:
    """
    Validate and extract shape type from configuration.
    Args:
        obj: Shape configuration dictionary
        index: Index in list (for error messages)
    Returns:
        ShapeType enum value
    Raises:
        KeyError: If obj_type is missing
        ValueError: If obj_type is unrecognized
    """
    obj_id = obj.get("obj_id", f"obj_{index}")
    
    if "obj_type" not in obj:
        raise KeyError(f"Missing 'obj_type' at index {index} (obj_id: {obj_id})")
    try:
        return ShapeType(obj["obj_type"])
    except ValueError:
        allowed = [s.value for s in ShapeType]
        raise ValueError(
            f"Unknown shape type '{obj.get('obj_type')}' at index {index} (obj_id: {obj_id}). "
            f"Allowed types: {allowed}"
        )


def _validate_required_params(obj: Dict[str, Any], shape: ShapeType, index: int) -> None:
    """
    Validate that all required parameters for a shape are present.
    Args:
        obj: Shape configuration dictionary
        shape: ShapeType enum value
        index: Index in list (for error messages)
    Raises:
        KeyError: If required parameters are missing
    """
    obj_id = obj.get("obj_id", f"obj_{index}")
    missing = REQUIRED_PARAMS[shape] - obj.keys()
    
    if missing: raise KeyError(
            f"Missing required parameters {sorted(missing)} for shape '{shape.value}' "
            f"at index {index} (obj_id: {obj_id})"
        )


def _build_box(obj: Dict[str, Any], index: int) -> cq.Workplane:
    """Build a box/rectangular prism."""
    obj_id = obj.get("obj_id", f"obj_{index}")
    length, width, height = obj["length"], obj["width"], obj["height"]
    
    if length <= 0: raise ValueError(f"Box length must be > 0 at index {index} (obj_id: {obj_id})")
    if width <= 0:  raise ValueError(f"Box width must be > 0 at index {index} (obj_id: {obj_id})")
    if height <= 0: raise ValueError(f"Box height must be > 0 at index {index} (obj_id: {obj_id})")
    
    return cq.Workplane("XY").box(length, width, height)


def _build_cylinder(obj: Dict[str, Any], index: int) -> cq.Workplane:
    """Build a cylinder."""
    obj_id = obj.get("obj_id", f"obj_{index}")
    height, radius = obj["height"], obj["radius"]
    
    if height <= 0: raise ValueError(f"Cylinder height must be > 0 at index {index} (obj_id: {obj_id})")
    if radius <= 0: raise ValueError(f"Cylinder radius must be > 0 at index {index} (obj_id: {obj_id})")
    
    return cq.Workplane("XY").cylinder(height, radius)


def _build_sphere(obj: Dict[str, Any], index: int) -> cq.Workplane:
    """Build a sphere."""
    obj_id = obj.get("obj_id", f"obj_{index}")
    radius = obj["radius"]
    
    if radius <= 0: raise ValueError(f"Sphere radius must be > 0 at index {index} (obj_id: {obj_id})")
    
    return cq.Workplane("XY").sphere(radius)


def _build_wedge(obj: Dict[str, Any], index: int) -> cq.Workplane:
    """Build a wedge."""
    obj_id = obj.get("obj_id", f"obj_{index}")
    dx, dy, dz = obj["dx"], obj["dy"], obj["dz"]
    xmin, xmax = obj["xmin"], obj["xmax"]
    zmin, zmax = obj["zmin"], obj["zmax"]
    
    if dx <= 0: raise ValueError(f"Wedge dx must be > 0 at index {index} (obj_id: {obj_id})")
    if dy <= 0: raise ValueError(f"Wedge dy must be > 0 at index {index} (obj_id: {obj_id})")
    if dz <= 0: raise ValueError(f"Wedge dz must be > 0 at index {index} (obj_id: {obj_id})")
    if xmin >= xmax:
        raise ValueError(
            f"Wedge requires xmin < xmax at index {index} (obj_id: {obj_id})."
            f"Got xmin={xmin}, xmax={xmax}"
        )
    if zmin >= zmax:
        raise ValueError(
            f"Wedge requires zmin < zmax at index {index} (obj_id: {obj_id})."
            f"Got zmin={zmin}, zmax={zmax}"
        )
    if not (0 <= xmin <= dx and 0 <= xmax <= dx):
        raise ValueError(
            f"Wedge x-parameters must be in [0, dx] at index {index} (obj_id: {obj_id})."
            f"Got dx={dx}, xmin={xmin}, xmax={xmax}"
        )
    if not (0 <= zmin <= dz and 0 <= zmax <= dz):
        raise ValueError(
            f"Wedge z-parameters must be in [0, dz] at index {index} (obj_id: {obj_id})."
            f"Got dz={dz}, zmin={zmin}, zmax={zmax}"
        )
    
    return cq.Workplane("XY").wedge(dx, dy, dz, xmin, zmin, xmax, zmax)


def _build_cylinder_closed_bottom(obj: Dict[str, Any], index: int) -> cq.Workplane:
    """
    Build a hollow cylinder with a configurable bottom head geometry.

    Parameters (in the config dict)
    --------------------------------
    height, outer_radius, wall_thickness : float  (required)
    bottom_head_type : str, optional
        'flat' | 'hemispherical' | 'ellipsoidal' | 'torispherical'
        Defaults to 'flat'.
    bottom_head_params : dict, optional
        Forwarded to the head builder:
          flat:          plate_t  (defaults to wall_thickness, or bottom_thickness for back-compat)
          ellipsoidal:   head_depth (required)
          torispherical: Rc, rk (both optional, have defaults)
          hemispherical: no extra params needed
    bottom_thickness : float, optional
        Legacy alias for bottom_head_params={'plate_t': value} when head type is 'flat'.
    """
    from components_premade.components_premade_reactor_vessel import _build_outer_head

    obj_id = obj.get("obj_id", f"obj_{index}")
    h  = obj["height"]
    ro = obj["outer_radius"]
    t  = obj["wall_thickness"]

    head_type   = obj.get("bottom_head_type", "flat")
    head_params = dict(obj.get("bottom_head_params", {}))

    # Backward compat: bottom_thickness → flat head plate_t
    if head_type == "flat" and "plate_t" not in head_params:
        head_params["plate_t"] = obj.get("bottom_thickness", t)

    if h  <= 0:
        raise ValueError(f"Cylinder_closed_bottom height must be > 0 at index {index} (obj_id: {obj_id})")
    if ro <= 0:
        raise ValueError(f"Cylinder_closed_bottom outer_radius must be > 0 at index {index} (obj_id: {obj_id})")
    if t <= 0 or t >= ro:
        raise ValueError(
            f"Cylinder_closed_bottom wall_thickness must be in (0, outer_radius) "
            f"at index {index} (obj_id: {obj_id}). Got wall_thickness={t}, outer_radius={ro}"
        )
    if head_type == "ellipsoidal" and "head_depth" not in head_params:
        raise ValueError(
            f"bottom_head_type='ellipsoidal' requires 'head_depth' in bottom_head_params "
            f"at index {index} (obj_id: {obj_id})"
        )

    ri  = ro - t
    outer_d = 2 * ro
    id_     = 2 * ri

    # ------------------------------------------------------------------
    # Outer solid: centered cylinder [-h/2, +h/2] + head below z = -h/2
    # ------------------------------------------------------------------
    outer_cyl  = cq.Workplane("XY").circle(ro).extrude(h).translate((0, 0, -h / 2))
    outer_head = _build_outer_head(outer_d, head_type, head_params).translate((0, 0, -h / 2))
    outer      = outer_cyl.union(outer_head)

    # ------------------------------------------------------------------
    # Inner bore: same cylinder with inner radius
    # For non-flat heads the inside of the head is also hollowed out.
    # ------------------------------------------------------------------
    inner_cyl = cq.Workplane("XY").circle(ri).extrude(h).translate((0, 0, -h / 2))

    if head_type == "flat":
        # The flat bottom plate stays solid; just remove the cylindrical bore.
        inner = inner_cyl

    elif head_type == "ellipsoidal":
        # Shrink head_depth by wall_t for the inner ellipsoid
        inner_params = dict(head_params)
        hd = float(head_params["head_depth"])
        inner_params["head_depth"] = max(hd - t, 0.01 * hd)   # relative floor (was 1e-3 absolute)
        inner_head = _build_outer_head(id_, head_type, inner_params).translate((0, 0, -h / 2))
        inner = inner_cyl.union(inner_head)

    else:
        # hemispherical, torispherical: use inner diameter with the same params
        inner_head = _build_outer_head(id_, head_type, head_params).translate((0, 0, -h / 2))
        inner = inner_cyl.union(inner_head)

    return outer.cut(inner).clean()


def _build_pipe(obj: Dict[str, Any], index: int) -> cq.Workplane:
    """Build a hollow cylinder (pipe), open both ends.
    
    Requires height + any two of: outer_radius, inner_radius, wall_thickness.
    The third is derived automatically.
    """
    obj_id = obj.get("obj_id", f"obj_{index}")
    h = obj["height"]

    has_ro = "outer_radius"    in obj
    has_ri = "inner_radius"    in obj
    has_t  = "wall_thickness"  in obj

    if sum([has_ro, has_ri, has_t]) < 2:
        raise ValueError(
            f"Pipe requires any two of {{outer_radius, inner_radius, wall_thickness}} "
            f"at index {index} (obj_id: {obj_id})"
        )

    if has_ro and has_ri and has_t:
        # All three given — validate consistency, prefer outer+inner.
        # This case MUST be tested first: the pair branches below would
        # otherwise swallow it and silently ignore the third value.
        ro, ri = obj["outer_radius"], obj["inner_radius"]
        t_given = obj["wall_thickness"]
        if abs((ro - ri) - t_given) > TOLERANCE:
            raise ValueError(
                f"Pipe: outer_radius - inner_radius ({ro - ri}) does not match "
                f"wall_thickness ({t_given}) at index {index} (obj_id: {obj_id})"
            )
    elif has_ro and has_ri:
        ro, ri = obj["outer_radius"], obj["inner_radius"]
    elif has_ro and has_t:
        ro = obj["outer_radius"]
        ri = ro - obj["wall_thickness"]
    else:  # has_ri and has_t
        ri = obj["inner_radius"]
        ro = ri + obj["wall_thickness"]

    if h  <= 0:        raise ValueError(f"Pipe height must be > 0 at index {index} (obj_id: {obj_id})")
    if ro <= 0:        raise ValueError(f"Pipe outer_radius must be > 0 at index {index} (obj_id: {obj_id})")
    if ri <= 0 or ri >= ro:
        raise ValueError(f"Pipe inner_radius must be in (0, outer_radius) at index {index} (obj_id: {obj_id})")

    return cq.Workplane("XY").cylinder(h, ro).cut(cq.Workplane("XY").cylinder(h, ri))






def _build_shape(obj: Dict[str, Any], shape: ShapeType, index: int) -> cq.Workplane:
    """
    Build a single 3D shape based on its type and configuration.
    Args:
        obj: Shape configuration dictionary
        shape: ShapeType enum value
        index: Index in primitives list
    Returns:
        CadQuery Workplane object
    Raises:
        ValueError: If parameters are invalid
        RuntimeError: If shape type is not recognized
    """
    builders = {
        ShapeType.BOX: _build_box,
        ShapeType.CYLINDER: _build_cylinder,
        ShapeType.SPHERE: _build_sphere,
        ShapeType.WEDGE: _build_wedge,
        ShapeType.CYLINDER_CLOSED_BOTTOM: _build_cylinder_closed_bottom,
        ShapeType.PIPE: _build_pipe,
    }
    
    if shape not in builders:  raise RuntimeError(f"Unhandled shape type: {shape}")
    
    return builders[shape](obj, index)


def _compute_intersections(
    components: List[Tuple[cq.Workplane, str]]
) -> List[Tuple[cq.Shape, str]]:
    """
    Compute intersection regions between all pairs of components.
    Args:
        components: List of (Workplane, obj_id) tuples
    Returns:
        List of (intersection_shape, name) tuples for non-empty intersections
    """
    intersections = []
    
    for i in range(len(components)):
        si = cast(cq.Shape, components[i][0].val())
        id_i = components[i][1]
        
        for j in range(i + 1, len(components)):
            sj = cast(cq.Shape, components[j][0].val())
            id_j = components[j][1]
            
            inter = si.intersect(sj)
            
            if not inter.isNull() and inter.Volume() > TOLERANCE:
                name = f"intersection_{id_i}_{id_j}"
                intersections.append((inter, name))
    
    return intersections





def build_3D_primitive(obj: Dict[str, Any]) -> cq.Workplane:
    """Build a single 3D primitive from a config dict. No positioning applied."""
    shape = _validate_shape_type(obj, 0)
    _validate_required_params(obj, shape, 0)
    return _build_shape(obj, shape, 0)













def set_components(primitives_list: List[Dict[str, Any]]) -> None:
    """
    Build and display a cq.Assembly from a list of primitive shape dicts (legacy).

    Each dict must have obj_type and shape-specific params. Optional keys:
      obj_id                — unique identifier (auto-generated if omitted)
      center_coords         — (x, y, z) translation
      center_coords_pol     — (r, theta, z) polar form
      rotation_angles       — (roll, pitch, yaw) in degrees

    Intersection regions between shapes are added in red.
    Note: Returns None (displays result). Use assemble_objects() for full workflow.
    """
    all_components: List[Tuple[cq.Workplane, str]] = []
    
    for index, obj in enumerate(primitives_list):
        obj_id = obj.get("obj_id", f"obj_{index}")
        logger.debug(f"Processing shape {index}: {obj_id}")
        
        # Validate shape type
        shape = _validate_shape_type(obj, index)
        
        # Validate required parameters
        _validate_required_params(obj, shape, index)
        
        # Build the shape
        workplane = _build_shape(obj, shape, index)
        
        # Extract and apply positioning
        pos = _extract_position(obj, index)
        roll, pitch, yaw = _get_rotation_angles(obj)
        
        workplane = rotate_rpy_about_self_global_axes(workplane, roll, pitch, yaw)
        if pos is not None:
            workplane = move_center_to(workplane, pos)
        
        center = cast(cq.Shape, workplane.val()).Center()
        logger.debug(f"  {obj_id} final position: {center}")
        
        all_components.append((workplane, obj_id))
    
    # Create assembly
    assembly_all = cq.Assembly()
    
    # Add original shapes
    for workplane, obj_id in all_components:
        assembly_all.add(workplane, name=obj_id)
    
    # Add intersection regions in red
    intersections = _compute_intersections(all_components)
    for inter_shape, name in intersections:
        assembly_all.add(inter_shape, name=name, color=cq.Color(1, 0, 0, 1.0))
    
    logger.info(f"Assembly created with {len(all_components)} components and {len(intersections)} intersections")
    
    show(assembly_all)






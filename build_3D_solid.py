"""
3D solid builder with unified interface for extrude, revolve, sweep, and primitive operations.

UNITS: All profile and geometry parameters are UNITLESS. The user must maintain
a consistent unit system throughout (e.g., all values in metres or all in millimetres).

Builds individual 3D solids from 2D profiles or 3D primitives without displaying them.
Use assemble_objects() to combine and display results.
"""

from typing import Any, Dict, Union, Callable, Tuple, Sequence, Literal, cast, Optional, List
import copy
import cadquery as cq
import uuid

from profile_built_in_2D_sketch import build_2D_sketch
from profile_from_straight_connections import create_profile_from_straight_connections
from components_3D_primitives import set_components, build_3D_primitive, get_outer_profile
from utils import extrude_profile, revolve_profile, sweep_profile, rotate_rpy_about_origin_global_axes, place_origin_at, convert_polar_to_cartesian
from components_premade import build_premade_component, PREMADE_BUILDERS




# =====================================================================
# Internal helpers for hollow profile generation
# =====================================================================

def _shrink_dict_profile(profile: Dict[str, Any], wall_thickness: float) -> Dict[str, Any]:
    """
    Return a copy of a build_2D_sketch profile dict with dimensions reduced inward
    by wall_thickness. Raises ValueError if the result would be degenerate.

    Supported obj_types and what gets shrunk:
      circle          : radius -= wall_thickness
      ellipse         : r1 -= wall_thickness, r2 -= wall_thickness
      rectangle       : width -= 2*wall_thickness, height -= 2*wall_thickness
      slot            : width -= 2*wall_thickness, height -= 2*wall_thickness
      trapezoid       : width -= 2*wall_thickness, height -= 2*wall_thickness
      regular_polygon : radius -= wall_thickness
      polygon         : uses shapely buffer (falls through to _offset_polygon_pts)
    """
    t = wall_thickness
    p = copy.deepcopy(profile)
    obj_type = p.get("obj_type", "")

    if obj_type == "circle":
        p["radius"] -= t
        if p["radius"] <= 0:
            raise ValueError(f"wall_thickness={t} >= circle radius={profile['radius']}: inner profile collapses")

    elif obj_type == "ellipse":
        p["r1"] -= t
        p["r2"] -= t
        if p["r1"] <= 0 or p["r2"] <= 0:
            raise ValueError(f"wall_thickness={t} too large for ellipse r1={profile['r1']}, r2={profile['r2']}")

    elif obj_type in ("rectangle", "slot"):
        p["width"]  -= 2 * t
        p["height"] -= 2 * t
        if p["width"] <= 0 or p["height"] <= 0:
            raise ValueError(
                f"wall_thickness={t} too large for {obj_type} "
                f"width={profile['width']}, height={profile['height']}"
            )

    elif obj_type == "trapezoid":
        p["width"]  -= 2 * t
        p["height"] -= 2 * t
        if p["width"] <= 0 or p["height"] <= 0:
            raise ValueError(
                f"wall_thickness={t} too large for trapezoid "
                f"width={profile['width']}, height={profile['height']}"
            )

    elif obj_type == "regular_polygon":
        p["radius"] -= t
        if p["radius"] <= 0:
            raise ValueError(
                f"wall_thickness={t} >= regular_polygon radius={profile['radius']}: inner profile collapses"
            )

    elif obj_type == "polygon":
        # shapely-based inward offset for arbitrary polygon point lists
        inner_pts = _offset_polygon_pts(p["pts"], t)
        p["pts"] = inner_pts

    else:
        raise ValueError(f"wall_thickness not supported for obj_type={obj_type!r}")

    return p


def _offset_polygon_pts(
    pts: List[Tuple[float, float]],
    offset: float
) -> List[Tuple[float, float]]:
    """
    Inward-offset a closed polygon by `offset` using shapely.
    Returns a list of (x, y) tuples for the inner contour.
    Raises ValueError if the offset collapses or fragments the polygon.
    """
    try:
        from shapely.geometry import Polygon
    except ImportError:
        raise ImportError(
            "shapely is required for wall_thickness on straight-connection profiles. "
            "Install it with: pip install shapely"
        )

    poly = Polygon(pts)
    if not poly.is_valid:
        raise ValueError("Polygon points form an invalid (self-intersecting) shape")

    inner = poly.buffer(-offset)

    if inner.is_empty:
        raise ValueError(
            f"wall_thickness={offset} collapses the polygon entirely — reduce wall_thickness"
        )
    if inner.geom_type != "Polygon":
        raise ValueError(
            f"wall_thickness={offset} fragments the polygon (result is {inner.geom_type}). "
            "The shape may be too thin or concave for this wall thickness."
        )

    coords = list(inner.exterior.coords)
    # shapely closes the ring by repeating the first point — drop the duplicate
    if coords[0] == coords[-1]:
        coords = coords[:-1]
    return [(float(x), float(y)) for x, y in coords]



# --- hollow bore helpers (used only by _apply_hollow) ---
def _build_inner_wp(
    profile: Union[Dict[str, Any], Sequence[Tuple[float, float]]],
    wall_thickness: float,
    plane: str,
) -> cq.Workplane:
    """Build the inner (bore) workplane for a hollow solid."""
    if isinstance(profile, dict):
        inner_profile = _shrink_dict_profile(profile, wall_thickness)
        return build_2D_sketch(inner_profile, plane)
    else:
        inner_pts = _offset_polygon_pts(list(profile), wall_thickness)  # type: ignore[arg-type]
        return create_profile_from_straight_connections(inner_pts, plane, closed=True)  # type: ignore[arg-type]

def _apply_hollow(
    outer_solid: cq.Workplane,
    profile: Union[Dict[str, Any], Sequence[Tuple[float, float]]],
    wall_thickness: float | None,                           # type: ignore
    plane: str,
    operation_fn: Callable[[cq.Workplane], cq.Workplane],
) -> cq.Workplane:
    """Cut a hollow bore from a solid if wall_thickness is set."""
    if wall_thickness is None:
        return outer_solid
    inner_wp = _build_inner_wp(profile, wall_thickness, plane)
    return outer_solid.cut(operation_fn(inner_wp))





def build_solid(
    operation: Literal["extrude", "revolve", "sweep", "primitive"],
    profile: Union[Dict[str, Any], Sequence[Tuple[float, float]]],
    height: float | None = None,                                    # type: ignore
    angle: float = 360.0,
    axis_point: Tuple[float, float, float] = (0, 0, 0),
    path: Union[cq.Wire, Callable[[float], Tuple[float, float, float]], Tuple, None] = None,
    isFrenet: bool = True,
    plane: Literal["XY", "XZ", "YZ"] = "XY",
    axis: Literal["X", "Y", "Z"] = "Z",
    center_coords: Tuple[float, float, float] | None = None,        # type: ignore
    center_coords_pol: Tuple[float, float, float] | None = None,    # type: ignore
    rotation_angles: Tuple[float, float, float] = (0, 0, 0),
    obj_id: Optional[str] = None,
    wall_thickness: float | None = None,                            # type: ignore
) -> Tuple[cq.Workplane, str]:
    """
    Build a 3D solid from a profile using the specified operation.

    Parameters
    ----------
    operation : {"extrude", "revolve", "sweep", "primitive"}
        Type of 3D operation to apply to the profile.
    profile : dict or sequence of (x, y) tuples
        Either a shape descriptor dict (e.g., {"obj_type": "circle", "radius": 5})
        or a list of points for a custom polygon.
    height : float, optional
        Height for extrude operation (required for "extrude").
    angle : float, default 360
        Rotation angle in degrees for revolve operation.
    axis_point : (x, y, z), default (0, 0, 0)
        Point on the revolve axis for revolve operation.
    path : Wire, callable, or sequence of points, optional
        Path for sweep operation. Can be a CadQuery Wire, function t -> (x,y,z),
        or list of (x,y,z) points.
    isFrenet : bool, default True
        Use Frenet frame for sweep (smoother orientation).
    plane : {"XY", "XZ", "YZ"}, default "XY"
        Plane in which to build the 2D profile.
    axis : {"X", "Y", "Z"}, default "Z"
        Revolve axis direction.
    center_coords : (x, y, z), optional
        World position of the solid's LOCAL ORIGIN — each component's
        documented datum: premades = axis ∩ base plane (e.g. pump barrel
        bottom, IHX lower-plenum cylinder bottom); raw primitives = body
        centre (CadQuery convention); profile solids = workplane origin.
    center_coords_pol : (r, theta_rad, z), optional
        Polar form of center_coords (theta in radians); converted to Cartesian.
    rotation_angles : (roll, pitch, yaw), default (0, 0, 0)
        Rotation in degrees about the LOCAL ORIGIN (global axes) — a yaw
        spins the component about its own axis.
    obj_id : str, optional
        Unique identifier. Auto-generated if not provided.
    wall_thickness : float, optional
        Create hollow shape by removing inner bore of this thickness.
        Not supported for "primitive" operation.

    Returns
    -------
    tuple of (Workplane, str)
        (3D solid, obj_id)
    """

    if obj_id is None:
        if isinstance(profile, dict) and "obj_id" in profile:
            obj_id = profile["obj_id"]
        else:
            obj_id = f"{operation}_{uuid.uuid4().hex[:8]}"

    op = operation.lower()

    if op == "extrude":
        if isinstance(profile, dict):
            wp = build_2D_sketch(profile, plane)
        else:
            wp = create_profile_from_straight_connections(profile, plane, closed=True)
        outer_solid = extrude_profile(wp, height)  # type: ignore
        solid = _apply_hollow(outer_solid, profile, wall_thickness, plane, lambda w: extrude_profile(w, height))  # type: ignore

    elif op == "revolve":
        if isinstance(profile, dict):
            wp = build_2D_sketch(profile, plane)
        else:
            wp = create_profile_from_straight_connections(profile, plane, closed=True)
        outer_solid = revolve_profile(wp, angle, axis, axis_point)
        solid = _apply_hollow(outer_solid, profile, wall_thickness, plane, lambda w: revolve_profile(w, angle, axis, axis_point))  # type: ignore

    elif op == "sweep":
        if isinstance(profile, dict):
            wp = build_2D_sketch(profile, plane)
        else:
            wp = create_profile_from_straight_connections(profile, plane, closed=True)
        outer_solid = sweep_profile(wp, path, isFrenet=isFrenet)  # type: ignore
        solid = _apply_hollow(outer_solid, profile, wall_thickness, plane, lambda w: sweep_profile(w, path, isFrenet=isFrenet))  # type: ignore

    elif op == "primitive":
        if wall_thickness is not None:
            raise NotImplementedError(
                "wall_thickness is not supported for 'primitive' operations. "
                "Use obj_type='pipe' (outer_radius, inner_radius) or "
                "obj_type='cylinder_closed_bottom' (outer_radius, wall_thickness, bottom_thickness) instead."
            )
        if isinstance(profile, dict):
            obj_type = profile.get("obj_type", "")
            if obj_type in PREMADE_BUILDERS:
                solid = build_premade_component(profile)
                # KNOWN LIMITATION (insert_into): premades have no filled
                # outer envelope, so _outer is the (hollow) solid itself.
                # insert_into then cuts the target with the WALL MATERIAL
                # only — the premade's internal cavities remain filled with
                # the target's material. Hollow PRIMITIVES (pipe, ...) do get
                # a filled envelope below, so their bores stay open. If a
                # premade ever needs correct insertion (e.g. carving void
                # regions out of a sodium pool for neutronics), give it an
                # envelope builder analogous to OUTER_PROFILE_BUILDERS.
                outer_solid = solid
            else:
                solid = build_3D_primitive(profile)
                outer_solid = build_3D_primitive(get_outer_profile(profile))  # filled envelope for hollow primitives
        elif isinstance(profile, list):
            # Legacy path: build assembly from list of primitive dicts.
            # Displays result and returns None (no further positioning applied).
            # Recommended instead: use assemble_objects(profile) for full workflow.
            solid = set_components(profile)  # type: ignore
            return solid, obj_id             # type: ignore
        else:
            raise ValueError("For 'primitive', profile must be a dict or list of dicts")
    else:
        raise ValueError(f"Unknown operation: {operation}. Use 'extrude', 'revolve', 'sweep', or 'primitive'")


    # Convert polar coordinates to Cartesian if provided
    if center_coords_pol is not None:
        r, theta, z = center_coords_pol
        center_coords = convert_polar_to_cartesian(r, theta, z)


    # Origin-based placement: rotate about the LOCAL ORIGIN (the component's
    # own axis), then place the origin at center_coords — exact by
    # construction, since every premade is built with its axis at (0,0) and
    # its documented datum plane at z = 0.
    roll, pitch, yaw = rotation_angles
    solid       = rotate_rpy_about_origin_global_axes(solid,       roll, pitch, yaw)
    outer_solid = rotate_rpy_about_origin_global_axes(outer_solid, roll, pitch, yaw)
    if center_coords is not None:
        solid       = place_origin_at(solid,       center_coords)
        outer_solid = place_origin_at(outer_solid, center_coords)

    solid._def = profile if isinstance(profile, dict) else {}  # type: ignore[attr-defined]
    solid._def["_center_coords"]   = center_coords             # type: ignore[attr-defined]
    solid._def["_rotation_angles"] = rotation_angles           # type: ignore[attr-defined]
    solid._outer = outer_solid                                  # type: ignore[attr-defined]  # used by insert_into
    return solid, obj_id  # type: ignore
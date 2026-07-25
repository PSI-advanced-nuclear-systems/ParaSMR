"""
Pre-made domain components.

Accessed through the same dict interface as build_3D_primitive(), so they
slot into assemble_objects() and build_solid() exactly like any primitive.

Adding a new component
----------------------
1. Write a create_<name>() function in a new components_premade_<name>.py module.
2. Add a _build_<name>(obj: dict) wrapper below.
3. Add one entry to PREMADE_BUILDERS.
"""

from __future__ import annotations
from typing import Any
import cadquery as cq

from .components_premade_reactor_vessel       import create_reactor_vessel
from .components_premade_top_plate            import create_top_plate
from .components_premade_ihx                  import create_ihx
from .components_premade_core                 import create_reactor_core
from .components_premade_strongback           import create_strongback
from .components_premade_primary_pump         import create_primary_pump
from .components_premade_diagrid              import create_diagrid, add_nozzle_bosses
from .components_premade_above_core_structure import create_above_core_structure
from .components_premade_redan                import create_redan


def _build_reactor_vessel(obj: dict[str, Any]) -> cq.Workplane:
    # straight_h is the ONLY key for the vessel's straight-section height —
    # no "height" alias: on a vessel with domed heads, "height" reads as the
    # TOTAL height and would silently misinterpret the user's intent.
    if "straight_h" not in obj:
        raise ValueError(
            f"Reactor vessel '{obj.get('obj_id')}' requires 'straight_h' "
            f"(height of the straight cylindrical section)."
        )
    # REMOVED feature — reject loudly rather than ignore silently:
    for legacy_key in ("top_plate_thickness", "top_plate_hole_groups"):
        if legacy_key in obj:
            raise ValueError(
                f"Reactor vessel '{obj.get('obj_id')}': '{legacy_key}' was "
                f"removed. The vessel-embedded top plate bypassed the resolver "
                f"(no auto-holes, no IHX alignment, no validation). Use a "
                f"separate obj_type='reactor_top_plate' component instead."
            )
    return create_reactor_vessel(
        inner_d               = obj.get("inner_d"),
        wall_t                = obj.get("wall_t"),
        outer_d               = obj.get("outer_d"),
        straight_h            = float(obj["straight_h"]),
        bottom_head_type      = obj.get("bottom_head_type"),
        bottom_head_params    = obj.get("bottom_head_params"),
        top_head_type         = obj.get("top_head_type"),
        top_head_params       = obj.get("top_head_params"),
    )


def _build_reactor_top_plate(obj: dict[str, Any]) -> cq.Workplane:
    z_bottom = obj.get("z_bottom", 0.0)
    return create_top_plate(
        outer_d         = obj["outer_d"],
        thickness       = obj["thickness"],
        center_coords   = (0.0, 0.0, z_bottom + obj["thickness"] / 2.0),
        hole_groups     = obj.get("hole_groups"),
    )


def _build_ihx(obj: dict[str, Any]) -> cq.Workplane:
    return create_ihx(obj)


def _build_reactor_core(obj: dict[str, Any]) -> cq.Workplane:
    return create_reactor_core(
        radius   = obj["radius"],
        height   = obj["height"],
        z_bottom = obj.get("z_bottom", 0.0),
        n_sides  = obj.get("n_sides"),
    )


def _build_strongback(obj: dict[str, Any]) -> cq.Workplane:
    return create_strongback(
        total_height            = obj["total_height"],
        flange_radius           = obj["flange_radius"],
        skirt_outer_radius      = obj["skirt_outer_radius"],
        skirt_inner_radius      = obj["skirt_inner_radius"],
        skirt_height            = obj["skirt_height"],
        taper_bottom_z          = obj["taper_bottom_z"],
        bore_radius             = obj["bore_radius"],
        small_hole_radius       = obj["small_hole_radius"],
        small_hole_count        = obj["small_hole_count"],
        small_hole_placement_r  = obj["small_hole_placement_r"],
        z_bottom                = obj.get("z_bottom", 0.0),
        profile_pts             = obj.get("profile_pts"),
    )


def _build_primary_pump(obj: dict[str, Any]) -> cq.Workplane:
    if "flange_z_top" not in obj:
        # No default: the flange position is a design choice (the old
        # fallback barrel_height - 0.5 also assumed metre-scale geometry).
        raise ValueError(
            f"Primary pump '{obj.get('obj_id')}' requires 'flange_z_top' "
            f"(top of the flange, measured from the barrel bottom)."
        )
    return create_primary_pump(
        barrel_radius  = obj["barrel_radius"],
        barrel_wall_t  = obj["barrel_wall_t"],
        barrel_height  = obj["barrel_height"],
        nozzle_r_pipe  = obj["nozzle_r_pipe"],
        nozzle_wall_t  = obj["nozzle_wall_t"],
        nozzle_L_leg   = obj["nozzle_L_leg"],
        nozzle_R_bend  = obj["nozzle_R_bend"],
        nozzle_arc_deg = obj["nozzle_arc_deg"],
        nozzle_L_inlet = obj["nozzle_L_inlet"],
        nozzle_z       = obj["nozzle_z"],
        flange_width   = obj["flange_width"],
        flange_height  = obj["flange_height"],
        flange_depth   = obj["flange_depth"],
        z_bottom       = obj.get("z_bottom",     0.0),
        flange_z_top   = obj["flange_z_top"],
    )


def _build_diagrid(obj: dict[str, Any]) -> cq.Workplane:
    wall_t        = obj.get("wall_t")
    wall_t_side   = obj.get("wall_t_side")
    wall_t_top    = obj.get("wall_t_top")
    wall_t_bottom = obj.get("wall_t_bottom")

    if wall_t_side is None:
        wall_t_side = wall_t
    if wall_t_top is None:
        wall_t_top = wall_t
    if wall_t_bottom is None:
        wall_t_bottom = wall_t

    z_bottom      = obj.get("z_bottom", 0.0)
    height        = obj["height"]
    diameter      = obj["diameter"]

    solid = create_diagrid(
        diameter      = diameter,
        height        = height,
        z_bottom      = z_bottom,
        wall_t_side   = wall_t_side,
        wall_t_top    = wall_t_top,
        wall_t_bottom = wall_t_bottom,
        wall_t        = wall_t,
    )

    if obj.get("nozzle_boss_angles_deg"):
        radius_outer    = diameter / 2.0
        radius_inner    = radius_outer - wall_t_side
        z_top           = z_bottom + height
        cavity_z_bottom = z_bottom + wall_t_bottom
        cavity_z_top    = z_top    - wall_t_top
        solid = add_nozzle_bosses(
            solid,
            radius_outer           = radius_outer,
            radius_inner           = radius_inner,
            z_bottom               = z_bottom,
            z_top                  = z_top,
            cavity_z_bottom        = cavity_z_bottom,
            cavity_z_top           = cavity_z_top,
            nozzle_boss_angles_deg = obj["nozzle_boss_angles_deg"],
            nozzle_z_abs           = obj["nozzle_z_abs"],
            nozzle_r_bore          = obj["nozzle_r_bore"],
            nozzle_r_boss          = obj["nozzle_r_boss"],
            nozzle_boss_height     = obj["nozzle_boss_height"],
        )

    return solid


def _build_above_core_structure(obj: dict[str, Any]) -> cq.Workplane:
    return create_above_core_structure(
        top_cyl_outer_r      = obj["top_cyl_outer_r"],
        top_cyl_height       = obj["top_cyl_height"],
        neck_outer_r         = obj["neck_outer_r"],
        neck_height          = obj["neck_height"],
        wall_t               = obj["wall_t"],
        cone_bottom_outer_r  = obj["cone_bottom_outer_r"],
        cone_height          = obj["cone_height"],
        bottom_ring_height   = obj["bottom_ring_height"],
        top_cyl_offset_x     = obj.get("top_cyl_offset_x", 0.0),
        top_cyl_offset_y     = obj.get("top_cyl_offset_y", 0.0),
        flow_hole_groups     = obj.get("flow_hole_groups"),
        crdl                 = obj.get("crdl"),
        bottom_plate         = obj.get("bottom_plate"),
        z_bottom             = obj.get("z_bottom", 0.0),
    )


def _apply_redan_penetrations(
    solid: cq.Workplane, obj: dict[str, Any]
) -> cq.Workplane:
    penetrations = obj.get("penetrations")
    if not penetrations:
        return solid
    profile_pts = obj.get("profile_pts")
    z_bottom = obj.get("z_bottom", 0.0)
    # z-coordinates are already absolute
    z_vals = [z for _, z in profile_pts] if profile_pts else [
        obj["z_top"], z_bottom
    ]
    # OLDER VERSION (unit-carrying over-reach): z_cut_bot = min(z_vals) - 1.0;
    # z_cut_top = max(z_vals) + 1.0
    z_span    = max(z_vals) - min(z_vals)
    z_cut_bot = min(z_vals) - 0.1 * z_span
    z_cut_top = max(z_vals) + 0.1 * z_span
    for px, py, pr in penetrations:
        cutter = (
            cq.Workplane("XY")
            .workplane(offset=z_cut_bot)
            .center(px, py)
            .circle(pr)
            .extrude(z_cut_top - z_cut_bot)
        )
        solid = solid.cut(cutter)
    return solid


def _build_redan(obj: dict[str, Any]) -> cq.Workplane:
    if "thickness" not in obj:
        raise ValueError(
            f"Redan '{obj.get('obj_id')}' requires 'thickness' "
            f"(shell wall thickness)."
        )
    # Convert absolute z-coordinates to relative (relative to z_bottom)
    z_bottom = obj.get("z_bottom", 0.0)
    z_top = obj.get("z_top")
    z_knee = obj.get("z_knee")
    z_shoulder = obj.get("z_shoulder")
    profile_pts = obj.get("profile_pts")

    # Convert absolute coords to relative
    if z_top is not None:
        z_top = z_top - z_bottom
    if z_knee is not None:
        z_knee = z_knee - z_bottom
    if z_shoulder is not None:
        z_shoulder = z_shoulder - z_bottom
    if profile_pts is not None:
        profile_pts = [(r, z - z_bottom) for r, z in profile_pts]

    solid = create_redan(
        thickness   = obj["thickness"],
        z_bottom    = z_bottom,
        r_top       = obj.get("r_top"),
        z_top       = z_top,
        r_lower     = obj.get("r_lower"),
        z_knee      = z_knee,
        z_shoulder  = z_shoulder,
        profile_pts = profile_pts,
    )
    return _apply_redan_penetrations(solid, obj)


PREMADE_BUILDERS: dict[str, Any] = {
    "reactor_vessel":       _build_reactor_vessel,
    "reactor_top_plate":    _build_reactor_top_plate,
    "ihx":                  _build_ihx,
    "reactor_core":         _build_reactor_core,
    "strongback":           _build_strongback,
    "primary_pump":         _build_primary_pump,
    "diagrid":              _build_diagrid,
    "above_core_structure": _build_above_core_structure,
    "redan":                _build_redan,
}


def build_premade_component(obj: dict[str, Any]) -> cq.Workplane:
    obj_type = obj.get("obj_type", "")
    if obj_type not in PREMADE_BUILDERS:
        raise ValueError(
            f"Unknown premade component {obj_type!r}. "
            f"Available: {sorted(PREMADE_BUILDERS)}"
        )
    return PREMADE_BUILDERS[obj_type](obj)


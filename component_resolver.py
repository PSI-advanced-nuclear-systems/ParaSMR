"""
Component placement resolver.

UNITS: All component parameters are UNITLESS. The user must choose a consistent
unit system (e.g., metres, millimetres) and apply it uniformly. The code does
not enforce, convert, or validate units.

Computes position and orientation for reactor components based on connection
rules. The resolver applies placement UNLESS the user has explicitly provided
values or opted out.

Three interaction modes:

  1. Default (paramak-style): Omit center_coords / rotation_angles; provide
     only `at_angle_deg` + `at_radius`. The resolver computes full placement.

  2. Full manual override: Provide both center_coords AND rotation_angles.
     center_coords places the component's LOCAL ORIGIN (its documented datum:
     axis ∩ base plane — e.g. pump barrel bottom, IHX lower-plenum cylinder
     bottom); rotation is about that origin. The resolver respects them but
     still uses them for downstream calculations (e.g., diagrid boss angles
     follow manually-placed pumps).

  3. Opt-out completely: Set `"manual_placement": True`. The resolver skips
     this component entirely.

Mode 1 is the default (paramak-style). Mode 2 is for users who want resolver-driven
placement on one side of a connection. Mode 3 is for edge cases the standard rules
don't cover.
"""

from __future__ import annotations
import copy
import math
import warnings
from typing import Any

import cadquery as cq

from component_anchors import (
    pump_elbow_mouth_local,
    diagrid_outer_radius,
    diagrid_z_range,
    ihx_up_bot_z_local,
    ihx_window_top_z_local,
    # ihx_bbox_center_z_local,  # OLDER VERSION: only needed to invert
    #                           # centroid-based placement (now origin-based)
)
# OLDER VERSION import — create_primary_pump was only needed by
# _build_pump_local (the centroid-measuring reference build, now commented):
# from components_premade.components_premade_primary_pump import create_primary_pump


# ════════════════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════════════════

def _find_all(dicts: list[dict], obj_type: str) -> list[dict]:
    return [d for d in dicts if d.get("obj_type") == obj_type]

def _add_interface(comp: dict, target_id: str) -> None:
    """Mark comp as intentionally touching target_id (suppresses overlap warning)."""
    existing = comp.get("interfaces_with", [])
    if target_id not in existing:
        comp["interfaces_with"] = existing + [target_id]

def _find_one(dicts: list[dict], obj_type: str) -> dict | None:
    matches = _find_all(dicts, obj_type)
    if len(matches) > 1:
        raise ValueError(
            f"Expected at most one {obj_type}, found {len(matches)}."
        )
    return matches[0] if matches else None


def _require(d: dict, key: str, why: str) -> float:
    """Read a required numeric key from a component dict, failing loudly.

    Never fall back to 0 for missing geometry keys: a misspelled or
    forgotten key must raise a clear error naming the component, not flow
    through placement arithmetic as a silent zero.
    """
    if key not in d:
        raise ValueError(
            f"'{d.get('obj_id')}' is missing required key '{key}' ({why})."
        )
    return float(d[key])


def _is_opted_out(d: dict) -> bool:
    """True if the user has explicitly removed this component from
    resolver consideration."""
    return bool(d.get("manual_placement", False))


def _has_full_manual_placement(d: dict) -> bool:
    """True if the user already provided BOTH center_coords and
    rotation_angles. The resolver doesn't override them but may still
    READ them to drive other components."""
    return ("center_coords" in d) and ("rotation_angles" in d)


# OLDER VERSION — reference-pump build, needed only to measure the centroid
# so centroid-based placement could be inverted. Origin-based placement makes
# this unnecessary (the pump origin IS its barrel axis at the barrel bottom):
# def _build_pump_local(pump: dict) -> cq.Workplane:
#     """Build a primary pump geometry centered at local origin with z_bottom=0."""
#     return create_primary_pump(
#         barrel_radius  = pump["barrel_radius"],
#         barrel_wall_t  = pump["barrel_wall_t"],
#         barrel_height  = pump["barrel_height"],
#         nozzle_r_pipe  = pump["nozzle_r_pipe"],
#         nozzle_wall_t  = pump["nozzle_wall_t"],
#         nozzle_L_leg   = pump["nozzle_L_leg"],
#         nozzle_R_bend  = pump["nozzle_R_bend"],
#         nozzle_arc_deg = pump["nozzle_arc_deg"],
#         nozzle_L_inlet = pump["nozzle_L_inlet"],
#         nozzle_z       = pump["nozzle_z"],
#         flange_width   = pump["flange_width"],
#         flange_height  = pump["flange_height"],
#         flange_depth   = pump["flange_depth"],
#         z_bottom       = 0.0,
#     )


def _pump_world_radius(p: dict) -> float:
    """Return the radial distance from the reactor axis to the pump's
    centerline. Reads from `at_radius` if given (mode 1), otherwise
    from `center_coords` XY (mode 2)."""
    if "at_radius" in p:
        return p["at_radius"]
    if "center_coords" in p:
        cc = p["center_coords"]
        return math.hypot(cc[0], cc[1])
    raise ValueError(
        f"Pump {p.get('obj_id')} needs either `at_radius` (resolver mode) "
        f"or `center_coords` (manual mode)."
    )


def _pump_world_angle_deg(p: dict) -> float:
    """Return the azimuthal angle of the pump's centerline. Reads from
    `at_angle_deg` if given (mode 1), otherwise from `center_coords`
    XY (mode 2)."""
    if "at_angle_deg" in p:
        return p["at_angle_deg"]
    if "center_coords" in p:
        cc = p["center_coords"]
        return math.degrees(math.atan2(cc[1], cc[0]))
    raise ValueError(
        f"Pump {p.get('obj_id')} needs either `at_angle_deg` or "
        f"`center_coords`."
    )


# ════════════════════════════════════════════════════════════════════════
#  Connection rule: primary_pump ↔ diagrid
# ════════════════════════════════════════════════════════════════════════

def _resolve_pump_diagrid(dicts: list[dict]) -> None:
    diagrid = _find_one(dicts, "diagrid")
    if diagrid is None or _is_opted_out(diagrid):
        return

    # Only pumps that haven't opted out are considered.
    pumps = [p for p in _find_all(dicts, "primary_pump") if not _is_opted_out(p)]
    if not pumps:
        return

    # ASSUMPTION (enforced below): all primary pumps in one assembly share
    # the same geometry. Physically they are identical units, and the diagrid
    # boss parameters (bore, boss radius, protrusion, connection height) are
    # derived ONCE from a single reference pump. Supporting heterogeneous
    # pumps would require per-boss sizing in add_nozzle_bosses — implement
    # that only if a real use case appears.
    _PUMP_GEOMETRY_KEYS = (
        "barrel_radius", "barrel_wall_t",
        "nozzle_r_pipe", "nozzle_wall_t", "nozzle_L_leg", "nozzle_R_bend",
        "nozzle_arc_deg", "nozzle_L_inlet", "nozzle_z",
    )
    ref = pumps[0]
    for p in pumps[1:]:
        for key in _PUMP_GEOMETRY_KEYS:
            if p.get(key) != ref.get(key):
                raise ValueError(
                    f"Pump '{p.get('obj_id')}' differs from pump "
                    f"'{ref.get('obj_id')}' in '{key}' "
                    f"({p.get(key)!r} vs {ref.get(key)!r}). All primary pumps "
                    f"in one assembly must share the same geometry — the "
                    f"diagrid bosses are derived from a single reference pump."
                )
    mouth_local = pump_elbow_mouth_local(ref)

    # OLDER VERSION — pre-build one pump to measure its centroid (needed when
    # assemble_objects placed solids by their centroid; now origin-based):
    # centroid_local_z = _build_pump_local(ref).val().Center().z      # type: ignore

    # Connection Z in world coordinates. User may override.
    z_bot, z_top   = diagrid_z_range(diagrid)
    nozzle_z_world = diagrid.get("nozzle_z_abs", (z_bot + z_top) / 2.0)

    # Radial distance of pumps (must all match).
    radii = {round(_pump_world_radius(p), 6) for p in pumps}
    if len(radii) > 1:
        raise ValueError(
            f"All primary_pump dicts must share a single radial distance. "
            f"Found: {sorted(radii)}."
        )
    pump_R = next(iter(radii))

    # World radius of the elbow mouth, derived from pump radius + elbow geom.
    mx_l, my_l    = mouth_local["x"], mouth_local["y"]
    wx, wy        = pump_R + my_l, -mx_l
    mouth_R_world = math.hypot(wx, wy)
    phi_deg       = abs(math.degrees(math.atan2(wy, wx)))

    # Boss protrusion → flush mate with mouth.
    diagrid_outer_r = diagrid_outer_radius(diagrid)
    boss_protrusion = mouth_R_world - diagrid_outer_r
    if boss_protrusion <= 0:
        raise ValueError(
            f"Diagrid outer radius ({diagrid_outer_r}) ≥ elbow mouth radius "
            f"({mouth_R_world:.4f}). Move pumps outward or shrink diagrid."
        )

    # Boss azimuthal angles — one pair per pump.
    boss_angles: list[float] = []
    for p in pumps:
        a = _pump_world_angle_deg(p)
        boss_angles.append(a - phi_deg)
        boss_angles.append(a + phi_deg)

    # Fill in the diagrid dict (never overwrite user-set values).
    diagrid.setdefault("nozzle_z_abs",           nozzle_z_world)
    diagrid.setdefault("nozzle_boss_angles_deg", boss_angles)
    diagrid.setdefault("nozzle_boss_height",     boss_protrusion)
    diagrid.setdefault("nozzle_r_bore",          ref["nozzle_r_pipe"])
    # nozzle_r_boss is derived from pump geometry:
    #   bore = pump nozzle outer radius (snug fit at the diagrid wall face)
    #   boss = bore + boss_wall_t
    if "nozzle_r_boss" not in diagrid:
        if "boss_wall_t" not in diagrid:
            raise ValueError(
                f"Diagrid '{diagrid.get('obj_id')}' requires 'boss_wall_t' "
                f"(wall thickness of the nozzle boss around the pump bore) "
                f"when primary pumps are present. Alternatively provide "
                f"'nozzle_r_boss' directly."
            )
        diagrid["nozzle_r_boss"] = ref["nozzle_r_pipe"] + diagrid["boss_wall_t"]

    # Place each pump (skip those the user already placed).
    #
    # OLDER VERSION (centroid-placement math):
    #   move_center_to: world_z(P) = P_local.z + (cc.z − centroid_local.z)
    #   With P = mouth, requiring world_z = nozzle_z_world:
    # cc_z = nozzle_z_world - mouth_local["z"] + centroid_local_z
    #
    # Origin-based placement: the pump origin is its barrel axis at the
    # barrel bottom, so world_z(mouth) = mouth_local.z + cc.z:
    cc_z = nozzle_z_world - mouth_local["z"]

    for p in pumps:
        if _has_full_manual_placement(p):
            continue   # user placed it; respect them

        if "at_angle_deg" not in p or "at_radius" not in p:
            raise ValueError(
                f"Pump {p.get('obj_id')} needs both `at_angle_deg` and "
                f"`at_radius` for resolver placement. Alternatively, "
                f"provide both `center_coords` and `rotation_angles`."
            )

        a   = p["at_angle_deg"]
        r   = p["at_radius"]
        rad = math.radians(a)
        p["rotation_angles"] = (0.0, 0.0, a - 90.0)
        p["center_coords"]   = (r * math.cos(rad), r * math.sin(rad), cc_z)

    # Pump elbow mouths mate with diagrid bosses — intentional contact.
    diagrid_id = diagrid.get("obj_id")
    if diagrid_id is not None:
        for p in pumps:
            _add_interface(p, diagrid_id)


# ════════════════════════════════════════════════════════════════════════
#  Connection rule: reactor_vessel → reactor_top_plate
# ════════════════════════════════════════════════════════════════════════

def _resolve_vessel_topplate(dicts: list[dict]) -> None:
    """Set top plate z_bottom to the vessel straight_h if not user-supplied."""
    top_plate = _find_one(dicts, "reactor_top_plate")
    rv        = _find_one(dicts, "reactor_vessel")
    if top_plate is None or rv is None or _is_opted_out(top_plate):
        return
    straight_h = rv.get("straight_h")
    if straight_h is not None:
        top_plate.setdefault("z_bottom", float(straight_h))


# ════════════════════════════════════════════════════════════════════════
#  Connection rule: ihx ↔ reactor_top_plate
# ════════════════════════════════════════════════════════════════════════

def _resolve_ihx_topplate(dicts: list[dict]) -> None:
    """
    Connection rule: align IHX(s) with reactor_top_plate.

    For each IHX without manual placement, computes center_coords so the
    internal upper-plenum bottom aligns with the plate bottom. Mode 2
    (user-placed IHX) is validated to ensure bundle window doesn't penetrate
    the plate. Marks IHX and pump barrels as intentionally touching the plate.
    """
    top_plate = _find_one(dicts, "reactor_top_plate")
    ihxs = [d for d in _find_all(dicts, "ihx") if not _is_opted_out(d)]
    if top_plate is None or not ihxs:
        return

    plate_z_bot = top_plate.get("z_bottom", 0.0)

    for ihx in ihxs:
        # Anchor: align the IHX internal upper-plenum bottom (z_up_bot) with the
        # reactor top plate bottom. The bundle-shell closed section + window gap
        # (bs_win_dz) then falls naturally below the plate — producing a visible
        # closed shell section before the windows start.
        z_up_bot_local = ihx_up_bot_z_local(ihx)
        # OLDER VERSION (centroid-based placement) also needed the bbox centre:
        # z_bbox_local   = ihx_bbox_center_z_local(ihx)

        if _has_full_manual_placement(ihx):
            # Mode 2: validate only — window top must be below the reactor top
            # plate. center_coords is the IHX LOCAL ORIGIN (bundle axis at the
            # lower-plenum cylinder bottom), so world z = local z + cc.z.
            cc = ihx["center_coords"]
            # OLDER VERSION: z_win_world = ihx_window_top_z_local(ihx) - z_bbox_local + cc[2]
            z_win_world = ihx_window_top_z_local(ihx) + cc[2]
            if z_win_world > plate_z_bot:
                raise ValueError(
                    f"IHX '{ihx.get('obj_id')}': bundle window top is at world "
                    f"z={z_win_world:.4g}, above reactor top plate bottom at "
                    f"z={plate_z_bot:.4g}. Lower center_coords z or reduce "
                    f"bundle_shell_window_fraction."
                )
            continue

        # Mode 1: align z_up_bot with plate_z_bot. Origin-based placement:
        # world z = local z + cc.z, so cc.z = target_world_z − anchor_local.
        if "at_angle_deg" not in ihx or "at_radius" not in ihx:
            raise ValueError(
                f"IHX '{ihx.get('obj_id')}' needs `at_angle_deg` and `at_radius` "
                f"for resolver placement."
            )
        # OLDER VERSION (centroid-based):
        # if "z_bottom" in ihx:
        #     z_min_local = -ihx["lower_plenum_dome_radius"]
        #     center_z = ihx["z_bottom"] - z_min_local + z_bbox_local
        # else:
        #     center_z = plate_z_bot - z_up_bot_local + z_bbox_local
        if "z_bottom" in ihx:
            # dome lowest point (local z = −lower_plenum_dome_radius) at z_bottom
            center_z = ihx["z_bottom"] + ihx["lower_plenum_dome_radius"]
        else:
            center_z = plate_z_bot - z_up_bot_local
        a   = ihx["at_angle_deg"]
        r   = ihx["at_radius"]
        rad = math.radians(a)
        ihx.setdefault("center_coords",   (r * math.cos(rad), r * math.sin(rad), center_z))
        ihx.setdefault("rotation_angles", (0.0, 0.0, a))

    # IHX barrels and pump barrels both pass through holes in the top plate —
    # their walls touch the hole edges by design.
    plate_id = top_plate.get("obj_id")
    if plate_id is not None:
        for ihx in ihxs:
            _add_interface(ihx, plate_id)
        for pump in _find_all(dicts, "primary_pump"):
            if not _is_opted_out(pump):
                _add_interface(pump, plate_id)


# ════════════════════════════════════════════════════════════════════════
#  Connection rule: ihx + primary_pump → redan penetrations
# ════════════════════════════════════════════════════════════════════════

def _resolve_redan_penetrations(dicts: list[dict]) -> None:
    """
    Collect the outer-envelope radius and world XY position of every IHX
    and primary pump, then store them as "penetrations": [(x, y, r), ...]
    on the redan dict.  create_redan() will cut a vertical cylinder for
    each entry, producing clean circular holes in the tapered shell wall.
    Components themselves are never touched — no duplication.
    Must run after _resolve_ihx_topplate / _resolve_pump_diagrid so that
    center_coords are already set.
    """
    redan = _find_one(dicts, "redan")
    if redan is None:
        return
    redan_id = redan.get("obj_id")   # user-assigned name, may be anything

    penetrations: list[tuple[float, float, float]] = []

    for comp in _find_all(dicts, "ihx") + _find_all(dicts, "primary_pump"):
        if _is_opted_out(comp):
            continue

        # World XY centre — prefer resolved center_coords, fall back to polar spec
        if "center_coords" in comp:
            px, py = comp["center_coords"][0], comp["center_coords"][1]
        elif "at_radius" in comp and "at_angle_deg" in comp:
            r   = comp["at_radius"]
            rad = math.radians(comp["at_angle_deg"])
            px, py = r * math.cos(rad), r * math.sin(rad)
        else:
            continue

        # Outer envelope radius used as the cutter cylinder radius
        obj_type = comp.get("obj_type")
        if obj_type == "ihx":
            pr = comp["bundle_shell_inner_radius"] + comp["bundle_shell_wall"]
        elif obj_type == "primary_pump":
            pr = comp["barrel_radius"]
        else:
            continue

        penetrations.append((px, py, pr))
        # Interface marking is independent of penetration cutting — only
        # possible when both components carry an obj_id.
        if redan_id is not None:
            _add_interface(comp, redan_id)

    if penetrations:
        redan.setdefault("penetrations", penetrations)


# ════════════════════════════════════════════════════════════════════════
#  Public entry point
# ════════════════════════════════════════════════════════════════════════

def _resolve_stacking_interfaces(dicts: list[dict]) -> None:
    """
    Mark all intentional touching interfaces arising from the vertical
    component stack and mechanical fits:
      - strongback inside reactor vessel bottom head
      - diagrid resting on strongback
      - core resting on diagrid
      - above-core structure neck fitting inside top plate central hole
    """
    def _link(type_a: str, type_b: str) -> None:
        a = _find_one(dicts, type_a)
        b = _find_one(dicts, type_b)
        if a is None or b is None:
            return
        id_a, id_b = a.get("obj_id"), b.get("obj_id")
        if id_a is not None and id_b is not None:
            _add_interface(a, id_b)

    _link("strongback",           "reactor_vessel")
    _link("diagrid",              "strongback")
    _link("reactor_core",         "diagrid")
    _link("above_core_structure", "reactor_top_plate")


def _resolve_acs_topplate(dicts: list[dict]) -> None:
    """
    Auto-compute ABOVE_CORE_STRUCTURE z_bottom so the BOTTOM of its top
    cylinder rests exactly ON the TOP of the reactor top plate.

    Formula (mirrors the code below):
      z_bottom = (top_plate_z + top_plate_thickness)
                 - bottom_ring_height - cone_height - neck_height

    i.e. z_bottom + ring + cone + neck — the top-cylinder bottom in ACS-local
    coordinates — lands at the plate top. The neck spans the plate's central
    hole and extends (neck_height - plate_thickness) below the plate bottom.
    top_plate_z = top_plate.z_bottom (usually = RV.straight_h).

    User override:
      - Set 'z_bottom' explicitly to bypass auto-computation
      - Set 'manual_placement': True to skip entirely
    """
    acs = _find_one(dicts, "above_core_structure")
    top_plate = _find_one(dicts, "reactor_top_plate")
    rv = _find_one(dicts, "reactor_vessel")

    if not (acs and top_plate and rv):
        return
    if _is_opted_out(acs):
        return
    if "z_bottom" in acs:
        return  # user provided it explicitly

    # Get dimensions from component definitions — all required, fail loudly.
    # top_plate z_bottom is normally set by _resolve_vessel_topplate (from the
    # vessel straight_h) before this rule runs; if it is still absent here,
    # the spec is genuinely incomplete.
    plate_z = _require(top_plate, "z_bottom",
                       "needed for ACS placement; set it explicitly or give "
                       "the reactor_vessel a straight_h")
    plate_t = _require(top_plate, "thickness", "needed for ACS placement")

    ring_h = _require(acs, "bottom_ring_height", "needed to auto-place the ACS")
    cone_h = _require(acs, "cone_height",        "needed to auto-place the ACS")
    neck_h = _require(acs, "neck_height",        "needed to auto-place the ACS")

    # Auto-compute z_bottom so top cylinder bottom touches top plate top
    # top_cylinder_bottom = z_bottom + ring_h + cone_h + neck_h = plate_z + plate_t
    acs["z_bottom"] = (plate_z + plate_t) - ring_h - cone_h - neck_h


def _resolve_fallback_placement(dicts: list[dict]) -> None:
    """
    Last-resort placement for any IHX or pump that still has no center_coords
    after all specific rules have run (i.e. no top plate for IHX, no diagrid
    for pump).  XY comes directly from at_radius / at_angle_deg.  Z comes from
    z_bottom if provided, otherwise the component sits with its local origin at
    world z = 0.
    """
    for comp in _find_all(dicts, "ihx") + _find_all(dicts, "primary_pump"):
        if _is_opted_out(comp) or "center_coords" in comp:
            continue
        if "at_radius" not in comp or "at_angle_deg" not in comp:
            continue

        r   = comp["at_radius"]
        a   = comp["at_angle_deg"]
        rad = math.radians(a)

        # OLDER VERSION (centroid-based):
        # if comp["obj_type"] == "ihx":
        #     z_bbox = ihx_bbox_center_z_local(comp)
        #     if "z_bottom" in comp:
        #         z_min_local = -comp["lower_plenum_dome_radius"]
        #         center_z = comp["z_bottom"] - z_min_local + z_bbox
        #     else:
        #         center_z = z_bbox   # local origin at world z = 0
        # else:
        #     # pump: approximate centroid at barrel mid-height
        #     center_z = comp.get("z_bottom", 0.0) + comp["barrel_height"] / 2.0
        if comp["obj_type"] == "ihx":
            if "z_bottom" in comp:
                # dome lowest point (local −lower_plenum_dome_radius) at z_bottom
                center_z = comp["z_bottom"] + comp["lower_plenum_dome_radius"]
            else:
                center_z = 0.0   # local origin at world z = 0
        else:
            # pump origin = barrel bottom — exact, no approximation
            center_z = comp.get("z_bottom", 0.0)

        comp.setdefault("center_coords",   (r * math.cos(rad), r * math.sin(rad), center_z))
        comp.setdefault("rotation_angles", (0.0, 0.0, a))


_CONNECTION_RULES = [
    _resolve_vessel_topplate,
    _resolve_pump_diagrid,
    _resolve_ihx_topplate,
    _resolve_acs_topplate,
    _resolve_redan_penetrations,
    _resolve_stacking_interfaces,
    _resolve_fallback_placement,
]

def resolve(user_dicts: list[dict]) -> list[dict]:
    """Apply every connection rule. Returns a new list of fully-resolved
    dicts, ready for assemble_objects."""
    resolved = [copy.deepcopy(d) for d in user_dicts]
    for rule in _CONNECTION_RULES:
        rule(resolved)
    return resolved
"""
Connection point (anchor) definitions for premade components.

UNITS: All anchor computations are UNITLESS and work with any consistent
unit system. The user is responsible for providing inputs in a single,
consistent unit (e.g., metres or millimetres everywhere).

Each premade component declares its connection points — named geometric
features that other components can mate with (e.g., pump elbow mouth,
diagrid boss-bore center).

Anchor functions are pure functions of the component dict, returning
geometric positions in the component's local frame. This allows the
resolver to compute placement parameters analytically before assembly,
avoiding circular dependencies. Placement is origin-based (build_solid
puts each component's LOCAL ORIGIN at center_coords), so local anchor
coordinates translate directly to world coordinates — no centroid
measurement or reference build is needed.
"""

from __future__ import annotations
import math
from typing import Any

from components_premade.components_premade_primary_pump import elbow_overshoot


# ════════════════════════════════════════════════════════════════════════
#  Primary pump anchors
# ════════════════════════════════════════════════════════════════════════

def pump_elbow_mouth_local(pump: dict[str, Any]) -> dict[str, float]:
    """
    Returns the LOCAL-frame position of the RIGHT-hand elbow mouth of a
    primary pump, plus the azimuthal offset `phi` between the pump's own
    centerline and that mouth (the left mouth is the mirror, at −phi).

    Coordinates returned (all in metres, all in the pump's local frame):
        x, y, z   — center of the right-hand elbow mouth
        phi_deg   — azimuthal angle of (x, y) from the +x axis, in degrees
    """
    R_bend   = pump["nozzle_R_bend"]
    arc_deg  = pump["nozzle_arc_deg"]
    L_leg    = pump["nozzle_L_leg"]
    L_inlet  = pump["nozzle_L_inlet"]
    r_barrel = pump["barrel_radius"]
    wall_t   = pump["barrel_wall_t"]
    nozzle_z = pump["nozzle_z"]

    # End of elbow centerline in the elbow's own frame:
    arc_rad = math.radians(arc_deg)
    ex = R_bend * (1.0 - math.cos(arc_rad)) + L_leg * math.sin(arc_rad)
    ey = L_inlet + R_bend * math.sin(arc_rad) + L_leg * math.cos(arc_rad)

    # create_primary_pump rotates the elbow by −90° about Z and translates
    # by (r_barrel − overshoot, 0, nozzle_z). The overshoot MUST be the same
    # value the builder uses — imported from the pump module, never restated.
    overshoot = elbow_overshoot(wall_t)
    mouth_x = ey + (r_barrel - overshoot)
    mouth_y = -ex
    mouth_z = nozzle_z

    phi_deg = abs(math.degrees(math.atan2(mouth_y, mouth_x)))

    return {"x": mouth_x, "y": mouth_y, "z": mouth_z, "phi_deg": phi_deg}


# ════════════════════════════════════════════════════════════════════════
#  Diagrid anchors
# ════════════════════════════════════════════════════════════════════════
#
# The diagrid's relevant connection is its OUTER CYLINDRICAL FACE — the
# Ø_outer surface where bosses get attached. The anchor isn't a single
# point but rather "any (theta, z) on the outer cylinder" — the resolver
# decides which (theta, z) the bosses sit at, based on what pumps are
# in the assembly.

def diagrid_outer_radius(diagrid: dict[str, Any]) -> float:
    return diagrid["diameter"] / 2.0

def diagrid_z_range(diagrid: dict[str, Any]) -> tuple[float, float]:
    z_bottom = diagrid.get("z_bottom", 0.0)
    return z_bottom, z_bottom + diagrid["height"]


# ════════════════════════════════════════════════════════════════════════
#  IHX anchors
# ════════════════════════════════════════════════════════════════════════

def ihx_up_bot_z_local(spec: dict[str, Any]) -> float:
    """Z of the IHX internal upper-plenum bottom plate in local coordinates.
    This is the natural anchor for aligning the IHX to the reactor top plate:
    placing z_up_bot_world = reactor_top_plate.z_bottom means the bundle shell
    (with its closed section + windows below) sits entirely inside the reactor."""
    return spec["lower_plenum_height"] + spec["bundle_height"]


def ihx_window_top_z_local(spec: dict[str, Any]) -> float:
    """Z of the bundle shell window top edge in IHX local coordinates.
    Local z=0 is the bottom of the lower plenum cylindrical section.
    Default gap mirrors create_ihx: gap = window height."""
    bh = spec["bundle_height"]
    if "bundle_shell_window_height" in spec:
        bs_win_h = float(spec["bundle_shell_window_height"])
    else:
        bs_win_h = bh * float(spec.get("bundle_shell_window_fraction", 0.4))
    default_dz = bs_win_h / 2.0
    return (spec["lower_plenum_height"] + bh
            - float(spec.get("bundle_shell_window_z_from_top", default_dz)))


"""
Parametric SFR strongback.

Built by revolving a closed half-section profile 360° around the Z axis,
then cutting the central bore and the small bolt/instrument holes.

profile_pts can be supplied as an advanced override for non-standard shapes.

Single public function:
    create_strongback()  — returns a single cq.Workplane solid
"""

from __future__ import annotations
import math
import cadquery as cq

from profile_from_straight_connections import create_profile_from_straight_connections
from utils import revolve_profile


def _cut_vertical_cylinder(
    solid: cq.Workplane,
    radius: float,
    z_bottom: float,
    z_top: float,
    x: float = 0.0,
    y: float = 0.0,
) -> cq.Workplane:
    """Cut a vertical cylinder through a solid."""
    h = z_top - z_bottom
    cutter = (
        cq.Workplane("XY")
        .workplane(offset=z_bottom)
        .circle(radius)
        .extrude(h)
        .translate((x, y, 0))
    )
    return solid.cut(cutter)


def create_strongback(
    total_height:       float,
    flange_radius:      float,
    skirt_outer_radius: float,
    skirt_inner_radius: float,
    skirt_height:       float,
    taper_bottom_z:     float,
    bore_radius:        float,
    small_hole_radius:  float,
    small_hole_count:   int,
    small_hole_placement_r: float,
    z_bottom: float = 0.0,
    profile_pts: list[tuple[float, float]] | None = None,
) -> cq.Workplane:
    """
    Build the strongback by revolving a half-section profile 360° around Z,
    then cutting the central bore and the small bolt/instrument holes.

    Local origin / datum: axis = local Z; z = 0 at the skirt bottom
    (then translated to z_bottom).

    All parameters are unitless and must be provided consistently.

    Supply profile_pts to override the computed cross-section; all dimension
    parameters are then ignored. Heights are derived from whichever profile is used.

    Returns:
        cq.Workplane — single solid with holes cut
    """
    if profile_pts is not None:
        pts = profile_pts
    else:
        pts = [
            (0.0,               total_height),
            (flange_radius,     total_height),
            (skirt_outer_radius, taper_bottom_z),
            (skirt_outer_radius, 0.0),
            (skirt_inner_radius, 0.0),
            (skirt_inner_radius, skirt_height),
            (0.0,               skirt_height),
        ]
    profile_z_top = max(z for _, z in pts)

    inner_z_values = [z for r, z in pts if r == 0.0 and z > 0.0]
    if not inner_z_values:
        raise ValueError(
            "Cannot derive small_hole_z_bottom from profile_pts: "
            "no points with r=0 and z>0 found."
        )
    small_hole_z_bottom = min(inner_z_values)
    if profile_pts is None:
        if taper_bottom_z <= 0 or taper_bottom_z >= total_height:
            raise ValueError(
                f"taper_bottom_z ({taper_bottom_z}) must be in range (0, total_height={total_height})."
            )
        if skirt_inner_radius >= skirt_outer_radius:
            raise ValueError(
                f"skirt_inner_radius ({skirt_inner_radius}) must be < skirt_outer_radius ({skirt_outer_radius})."
            )
        if skirt_height >= total_height:
            raise ValueError(
                f"skirt_height ({skirt_height}) must be < total_height ({total_height})."
            )
    if bore_radius <= 0:
        raise ValueError("bore_radius must be > 0")
    if small_hole_radius <= 0:
        raise ValueError("small_hole_radius must be > 0")
    if small_hole_count <= 0:
        raise ValueError("small_hole_count must be > 0")
    if small_hole_placement_r <= 0:
        raise ValueError("small_hole_placement_r must be > 0")

    # Get the outer radius from profile for bounds checking
    profile_r_max = max(r for r, _ in pts)
    if small_hole_placement_r + small_hole_radius > profile_r_max:
        raise ValueError(
            f"Small holes (placement_r={small_hole_placement_r}, radius={small_hole_radius}) "
            f"extend beyond profile outer radius ({profile_r_max})."
        )
    profile = create_profile_from_straight_connections(pts, plane="XZ", closed=True)
    solid = revolve_profile(profile, angle=360, axis="Z")
    solid = _cut_vertical_cylinder(
        solid,
        radius   = bore_radius,
        z_bottom = 0.0,
        z_top    = profile_z_top,
    )
    for i in range(small_hole_count):
        angle = 2 * math.pi * i / small_hole_count
        solid = _cut_vertical_cylinder(
            solid,
            radius   = small_hole_radius,
            z_bottom = small_hole_z_bottom,
            z_top    = profile_z_top,
            x        = small_hole_placement_r * math.cos(angle),
            y        = small_hole_placement_r * math.sin(angle),
        )
    if z_bottom != 0.0:
        solid = solid.translate((0, 0, z_bottom))

    return solid


if __name__ == "__main__":
    from ocp_vscode import show
    sb = create_strongback(
        total_height        = 1.242,
        flange_radius       = 2.684,
        skirt_outer_radius  = 3.030,
        skirt_inner_radius  = 2.243,
        skirt_height        = 0.436,
        taper_bottom_z      = 0.356,
        bore_radius             = 0.303,
        small_hole_radius       = 0.0755,
        small_hole_count        = 6,
        small_hole_placement_r  = 0.900,
    )
    show(sb)

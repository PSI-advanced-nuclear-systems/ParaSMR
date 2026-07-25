"""
Parametric diagrid.

Hollow short cylinder with thin walls closed top and bottom.

create_diagrid   — pure hollow cylinder, no pump knowledge.
add_nozzle_bosses — adds lateral bosses and bores for pump connections.
                    Called by the assembly builder when the resolver has
                    injected pump-interface parameters into the diagrid dict.
"""

from __future__ import annotations
import math
import cadquery as cq


def create_diagrid(
    diameter:      float,
    height:        float,
    z_bottom:      float,
    wall_t:        float | None = None,
    wall_t_side:   float | None = None,
    wall_t_top:    float | None = None,
    wall_t_bottom: float | None = None,
) -> cq.Workplane:
    """
    Hollow short cylinder, always closed on top and bottom.

    Local origin / datum: diagrid axis = local Z; the shell is built directly
    at absolute height, spanning z_bottom → z_bottom + height.

    All parameters are unitless and must be provided consistently.

    Parameters
    ----------
    wall_t : float, optional
        Uniform wall thickness (shortcut). Used as default for any
        wall_t_side, wall_t_top, wall_t_bottom that are not explicitly provided.
    wall_t_side, wall_t_top, wall_t_bottom : float, optional
        Individual wall thicknesses. Take precedence over wall_t if provided.
    """

    # Apply wall_t as default for unspecified thicknesses
    if wall_t_side is None:
        wall_t_side = wall_t
    if wall_t_top is None:
        wall_t_top = wall_t
    if wall_t_bottom is None:
        wall_t_bottom = wall_t

    # Validate that all thicknesses are now defined
    if wall_t_side is None or wall_t_top is None or wall_t_bottom is None:
        raise ValueError(
            "Must provide either wall_t or all three of "
            "(wall_t_side, wall_t_top, wall_t_bottom)"
        )

    if diameter <= 0 or height <= 0:
        raise ValueError("diameter and height must be > 0")
    if wall_t_side <= 0:
        raise ValueError("wall_t_side must be > 0")
    if wall_t_top < 0 or wall_t_bottom < 0:
        raise ValueError("wall_t_top and wall_t_bottom must be ≥ 0")

    radius_outer = diameter / 2.0
    radius_inner = radius_outer - wall_t_side
    if radius_inner <= 0:
        raise ValueError(
            f"wall_t_side ({wall_t_side}) is too large for diameter ({diameter})."
        )

    z_top = z_bottom + height

    cavity_z_bottom = z_bottom + wall_t_bottom
    cavity_z_top    = z_top    - wall_t_top
    cavity_height   = cavity_z_top - cavity_z_bottom
    if cavity_height <= 0:
        raise ValueError(
            f"wall_t_top + wall_t_bottom ({wall_t_top + wall_t_bottom}) "
            f"is too large for height ({height})."
        )

    shell = (cq.Workplane("XY")
             .workplane(offset=z_bottom)
             .circle(radius_outer)
             .extrude(height))

    cavity = (cq.Workplane("XY")
              .workplane(offset=cavity_z_bottom)
              .circle(radius_inner)
              .extrude(cavity_height))

    return shell.cut(cavity).clean()


def add_nozzle_bosses(
    diagrid_solid:          cq.Workplane,
    *,
    radius_outer:           float,
    radius_inner:           float,
    z_bottom:               float,
    z_top:                  float,
    cavity_z_bottom:        float,
    cavity_z_top:           float,
    nozzle_boss_angles_deg: list[float],
    nozzle_z_abs:           float,
    nozzle_r_bore:          float,
    nozzle_r_boss:          float,
    nozzle_boss_height:     float,
) -> cq.Workplane:
    """
    Add lateral nozzle bosses and bores to an existing diagrid solid.

    Each boss is a short cylinder protruding from the outer wall; each bore
    is cut through the boss and the diagrid wall into the interior cavity,
    forming the pump-to-diagrid fluid connection.

    All parameters here are derived by the resolver from pump geometry and
    diagrid dimensions — they are never set by the user directly.

    Parameters
    ----------
    diagrid_solid : cq.Workplane
        Shell returned by create_diagrid.
    radius_outer, radius_inner : float
        Outer and inner radii of the diagrid shell.
    z_bottom, z_top : float
        Absolute z bounds of the diagrid shell.
    cavity_z_bottom, cavity_z_top : float
        Absolute z bounds of the hollow interior cavity.
    nozzle_boss_angles_deg : list[float]
        Azimuthal angles (degrees) at which bosses are placed.
    nozzle_z_abs : float
        Absolute z of the boss / bore centre-line.
    nozzle_r_bore : float
        Radius of the bore (= pump nozzle outer radius).
    nozzle_r_boss : float
        Outer radius of the boss cylinder (= nozzle_r_bore + diagrid boss_wall_t).
    nozzle_boss_height : float
        Protrusion height of the boss beyond the diagrid outer wall.
    """
    if nozzle_r_boss >= radius_outer:
        raise ValueError(
            f"nozzle_r_boss ({nozzle_r_boss}) must be smaller than "
            f"diagrid outer radius ({radius_outer})."
        )
    if nozzle_r_bore >= radius_inner:
        raise ValueError(
            f"nozzle_r_bore ({nozzle_r_bore}) must be smaller than "
            f"diagrid inner radius ({radius_inner})."
        )

    bore_z_low  = nozzle_z_abs - nozzle_r_bore
    bore_z_high = nozzle_z_abs + nozzle_r_bore
    if bore_z_high > cavity_z_top:
        raise ValueError(
            f"Top plate (Z = [{cavity_z_top:.4f}, {z_top:.4f}]) "
            f"overlaps the bore (Z = [{bore_z_low:.4f}, {bore_z_high:.4f}]). "
            f"Reduce wall_t_top or move the bore down."
        )
    if bore_z_low < cavity_z_bottom:
        raise ValueError(
            f"Bottom plate (Z = [{z_bottom:.4f}, {cavity_z_bottom:.4f}]) "
            f"overlaps the bore (Z = [{bore_z_low:.4f}, {bore_z_high:.4f}]). "
            f"Reduce wall_t_bottom or move the bore up."
        )

    margin = nozzle_r_boss
    if not (z_bottom + margin < nozzle_z_abs < z_top - margin):
        raise ValueError(
            f"nozzle_z_abs={nozzle_z_abs:.4f} clips the diagrid face. "
            f"Must be in ({z_bottom + margin:.4f}, {z_top - margin:.4f})."
        )

    inset_min         = radius_outer - math.sqrt(radius_outer**2 - nozzle_r_boss**2)
    # OLDER VERSION (unit-carrying margins):
    # inset_safe  = inset_min + 0.005
    # bore_length = L_min + 0.010
    # Scale-free fusion/over-cut margin: a fraction of the side wall.
    margin            = 0.1 * (radius_outer - radius_inner)
    inset_safe        = inset_min + margin
    boss_total_height = inset_safe + nozzle_boss_height

    L_min       = (radius_outer + nozzle_boss_height) - math.sqrt(radius_inner**2 - nozzle_r_bore**2)
    bore_length = L_min + margin

    shell: cq.Workplane        = diagrid_solid
    boss_solids: list[cq.Workplane] = []

    for theta in nozzle_boss_angles_deg:
        rad = math.radians(theta)

        outward = cq.Vector( math.cos(rad),  math.sin(rad), 0.0)
        inward  = cq.Vector(-math.cos(rad), -math.sin(rad), 0.0)
        tangent = cq.Vector(-math.sin(rad),  math.cos(rad), 0.0)

        base_origin = cq.Vector(
            (radius_outer - inset_safe) * math.cos(rad),
            (radius_outer - inset_safe) * math.sin(rad),
            nozzle_z_abs,
        )
        boss = (cq.Workplane(cq.Plane(origin=base_origin, xDir=tangent, normal=outward))
                .circle(nozzle_r_boss)
                .extrude(boss_total_height))

        outer_face_origin = cq.Vector(
            (radius_outer + nozzle_boss_height) * math.cos(rad),
            (radius_outer + nozzle_boss_height) * math.sin(rad),
            nozzle_z_abs,
        )
        bore = (cq.Workplane(cq.Plane(origin=outer_face_origin, xDir=tangent, normal=inward))
                .circle(nozzle_r_bore)
                .extrude(bore_length))

        boss  = boss.cut(bore)
        shell = shell.cut(bore)
        boss_solids.append(boss.clean())

    result = shell.clean()
    for b in boss_solids:
        result = result.union(b)
    return result.clean()


if __name__ == "__main__":
    from ocp_vscode import show

    diagrid = create_diagrid(
        diameter      = 4.660,
        height        = 1.050,
        z_bottom      = -0.460,
        wall_t_side   = 0.030,
        wall_t_top    = 0.030,
        wall_t_bottom = 0.030,
    )
    show(diagrid)

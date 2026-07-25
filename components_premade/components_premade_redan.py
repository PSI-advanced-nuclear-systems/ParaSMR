"""
Parametric SFR redan (inner vessel / hot-cold pool separation shell) — ZLP.

Thin shell of revolution separating the hot and cold sodium pools.
The profile specifies the outer surface; the wall grows inward by `thickness`.

Single public function:
    create_redan()  — returns a cq.Workplane hollow shell.
"""

from __future__ import annotations

import math
import cadquery as cq

from profile_from_straight_connections import create_profile_from_straight_connections
from utils import revolve_profile


# ════════════════════════════════════════════════════════════════════════════
#  Mitred one-sided offset of an open (r, z) polyline
# ════════════════════════════════════════════════════════════════════════════

def _unit(dx: float, dz: float) -> tuple[float, float]:
    L = math.hypot(dx, dz)
    if L < 1e-12:
        raise ValueError("Degenerate (zero-length) segment in redan profile.")
    return dx / L, dz / L


def _line_intersection(
    p1: tuple[float, float], d1: tuple[float, float],
    p2: tuple[float, float], d2: tuple[float, float],
) -> tuple[float, float] | None:
    """Intersection of p1 + s*d1 and p2 + u*d2. None if parallel."""
    a, b = d1[0], -d2[0]
    c, d = d1[1], -d2[1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    rx, rz = p2[0] - p1[0], p2[1] - p1[1]
    s = (rx * d - b * rz) / det
    return (p1[0] + s * d1[0], p1[1] + s * d1[1])


def _offset_open_polyline(
    pts: list[tuple[float, float]],
    t: float,
) -> list[tuple[float, float]]:
    """Constant-distance perpendicular offset of an open (r, z) polyline with
    mitred corners. The offset lies toward the revolution axis (inward) only
    when the polyline is ordered top->bottom (descending z) — the caller
    (create_redan) normalizes the ordering to guarantee this.
    """
    n = len(pts)
    if n < 2:
        raise ValueError("redan profile needs at least 2 points.")

    dirs: list[tuple[float, float]] = []
    norms: list[tuple[float, float]] = []
    for i in range(n - 1):
        ux, uz = _unit(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        dirs.append((ux, uz))
        # Normal = walk direction rotated 90° clockwise. It points toward the
        # axis only when the segment is walked downward (descending z);
        # create_redan normalizes the point order so the offset is always inward.
        norms.append((uz, -ux))

    off: list[tuple[float, float] | None] = [None] * n
    off[0]     = (pts[0][0]     + t * norms[0][0],     pts[0][1]     + t * norms[0][1])
    off[n - 1] = (pts[n - 1][0] + t * norms[n - 2][0], pts[n - 1][1] + t * norms[n - 2][1])

    for i in range(1, n - 1):
        p_a = (pts[i][0] + t * norms[i - 1][0], pts[i][1] + t * norms[i - 1][1])
        p_b = (pts[i][0] + t * norms[i][0],     pts[i][1] + t * norms[i][1])
        inter = _line_intersection(p_a, dirs[i - 1], p_b, dirs[i])
        if inter is None:
            inter = ((p_a[0] + p_b[0]) / 2.0, (p_a[1] + p_b[1]) / 2.0)
        off[i] = inter

    return [p for p in off if p is not None]


# ════════════════════════════════════════════════════════════════════════════
#  Public API
# ════════════════════════════════════════════════════════════════════════════

def create_redan(
    thickness: float,
    z_bottom: float = 0.0,
    r_top: float | None = None,
    z_top: float | None = None,
    r_lower: float | None = None,
    z_knee: float | None = None,
    z_shoulder: float | None = None,
    profile_pts: list[tuple[float, float]] | None = None,
) -> cq.Workplane:
    """
    Build a redan (hot-cold pool separation shell) as a revolved hollow surface.

    The redan is defined by an outer profile (r, z) in the meridian plane,
    which is revolved 360° around the Z axis. The shell wall thickness is
    uniform inward from the outer surface.

    Parameters can be specified either as:
      1. Custom profile (profile_pts), OR
      2. Standard geometry (r_top, z_top, r_lower, z_knee, z_shoulder)

    The profile is built with z-coordinates relative to z=0 (redan bottom).
    The entire redan is then positioned at z_bottom in world coordinates.

    Parameters
    ----------
    thickness : float
        Wall thickness (unitless). Must be > 0.
    z_bottom : float, default 0.0
        Absolute z coordinate where the redan bottom is positioned (unitless).
    r_top : float, optional
        Outer radius of the top rim (unitless). Required if using standard geometry.
    z_top : float, optional
        Height of the top rim above redan bottom (unitless). Required if using standard geometry.
    r_lower : float, optional
        Outer radius of the lower cylinder (unitless). Required if using standard geometry.
    z_knee : float, optional
        Height where taper meets lower cylinder, from redan bottom (unitless). Required if using standard geometry.
    z_shoulder : float, optional
        Height of shoulder from redan bottom. If given, a vertical section at r_top extends from z_top down to z_shoulder.
    profile_pts : list[tuple[float, float]], optional
        Custom outer (r, z) points (unitless, z relative to redan bottom at z=0).
        If provided, overrides standard geometry. Points may be listed in either
        order (top->bottom or bottom->top): the order is normalized so the wall
        always grows inward, toward the revolution axis. The profile must have
        a net vertical extent (first and last z must differ).

    Returns a single Workplane hollow shell solid.
    """
    if thickness <= 0:
        raise ValueError("thickness must be > 0")

    # Validate: must have EITHER profile_pts OR all coordinate parameters
    if profile_pts is not None:
        outer = [(float(r), float(z)) for r, z in profile_pts]
        if len(outer) < 2:
            raise ValueError("profile_pts needs at least 2 (r, z) points.")
        # The wall must grow toward the revolution axis. For the perpendicular
        # offset in _offset_open_polyline this is equivalent to walking the
        # profile top->bottom — normalize the order so either input order works.
        if outer[0][1] == outer[-1][1]:
            raise ValueError(
                "profile_pts starts and ends at the same height — 'inward' is "
                "ambiguous for a horizontal profile. The profile must have a "
                "net vertical extent."
            )
        if outer[0][1] < outer[-1][1]:      # walked bottom->top: flip
            outer = list(reversed(outer))
    else:
        # Check that all coordinate parameters are provided
        if any(x is None for x in [r_top, z_top, r_lower, z_knee]):
            raise ValueError(
                "Must provide either profile_pts OR all of "
                "(r_top, z_top, r_lower, z_knee)"
            )

        # Type guard: at this point, all are definitely not None
        assert r_top is not None and z_top is not None and r_lower is not None and z_knee is not None

        if r_top <= 0 or r_lower <= 0:
            raise ValueError("r_top and r_lower must be > 0")
        if r_top < r_lower:
            raise ValueError(
                f"r_top ({r_top}) must be >= r_lower ({r_lower})."
            )
        if not (z_top > z_knee > 0):
            raise ValueError(
                f"Require z_top > z_knee > 0, got "
                f"{z_top} / {z_knee}."
            )
        outer = [(r_top, z_top)]
        if z_shoulder is not None:
            if not (z_top > z_shoulder > z_knee):
                raise ValueError(
                    f"Require z_top > z_shoulder > z_knee, got "
                    f"{z_top} / {z_shoulder} / {z_knee}."
                )
            outer.append((r_top, z_shoulder))
        outer.append((r_lower, z_knee))
        outer.append((r_lower, 0.0))

    inner = _offset_open_polyline(outer, thickness)

    min_r = min(r for r, _ in (outer + inner))
    if min_r <= 1e-6:
        raise ValueError(
            f"thickness={thickness} pushes the wall onto or across the axis "
            f"(min radius {min_r:.4g})."
        )

    ring = list(outer) + list(reversed(inner))
    profile = create_profile_from_straight_connections(ring, plane="XZ", closed=True)
    solid = revolve_profile(profile, angle=360, axis="Z")

    # Position the redan at z_bottom
    if z_bottom != 0.0:
        solid = solid.translate((0.0, 0.0, z_bottom))

    return solid.clean()


if __name__ == "__main__":
    from ocp_vscode import show

    redan = create_redan(
        thickness=0.025,
        z_bottom=-0.10,
        r_top=2.36,
        z_top=5.60,
        r_lower=1.50,
        z_knee=1.70,
        z_shoulder=3.10,
    )
    show(redan)

"""
Reactor vessel (RV) builder.

Constructs a hollow cylindrical vessel with a choice of bottom/top head
geometry.

The vessel shell always runs from z=0 to z=straight_h, so the top face is
exactly at z=straight_h — no bounding box lookup needed. For a top plate,
use the separate obj_type="reactor_top_plate" component (the old
vessel-embedded plate option was removed — see the note in the signature).

Example
-------
>>> vessel = create_reactor_vessel(
...     inner_d    = 4.72,
...     wall_t     = 0.04,
...     straight_h = 5.5,
...     bottom_head_type   = "ellipsoidal",
...     bottom_head_params = {"head_depth": 1.0},
... )
"""

from __future__ import annotations
from typing import Any

import cadquery as cq
import math


# ---------------------------------------------------------------------------
# Bottom head builders
# Each returns a solid with its rim in the XY plane at z=0,
# extending downward (z < 0).
# ---------------------------------------------------------------------------

def _head_flat(outer_d: float, plate_t: float, **_) -> cq.Workplane:
    """Flat circular end plate, z in [-plate_t, 0]."""
    return cq.Workplane("XY").circle(outer_d / 2).extrude(-plate_t)


def _head_hemispherical(outer_d: float, **_) -> cq.Workplane:
    """Hemispherical bottom head, z in [-outer_d/2, 0]."""
    r = outer_d / 2
    sphere = cq.Workplane("XY").sphere(r)
    cutter = cq.Workplane("XY").box(10 * outer_d, 10 * outer_d, 10 * outer_d).translate((0, 0, -5 * outer_d))
    return sphere.intersect(cutter)


def _head_ellipsoidal(outer_d: float, head_depth: float, n: int = 40, **_) -> cq.Workplane:
    """
    Ellipsoidal bottom head.
    head_depth is the dish depth (for 2:1 ellipsoidal use head_depth = outer_d/4).
    """
    r = outer_d / 2
    pts = [
        (r * math.cos(t), -head_depth * math.sin(t))
        for t in [i * (math.pi / 2) / n for i in range(n + 1)]
    ]
    prof = (
        cq.Workplane("XZ")
        .moveTo(*pts[0])
        .spline(pts[1:], includeCurrent=True)
        .lineTo(0, 0)
        .close()
    )
    return prof.revolve(360)


def _head_torispherical(
    outer_d: float,
    Rc: float | None = None,
    rk: float | None = None,
    n_crown: int = 80,
    n_knuckle: int = 40,
    **_,
) -> cq.Workplane:
    """
    Torispherical (flanged & dished) bottom head.
    Rc: crown radius (defaults to outer_d).
    rk: knuckle radius (defaults to 0.06 * outer_d).
    """
    r = outer_d / 2
    Rc = outer_d if Rc is None else Rc
    rk = 0.06 * outer_d if rk is None else rk

    if rk <= 0:          raise ValueError("rk must be > 0")
    if Rc <= r:          raise ValueError("Rc must be > outer_d/2")
    if Rc <= rk:         raise ValueError("Rc must be > rk")

    xk, zk = r - rk, 0.0
    d = Rc - rk
    rad = d * d - xk * xk
    if rad <= 0:
        raise ValueError("Infeasible Rc/rk for this outer_d (try larger Rc or smaller rk)")
    zc = math.sqrt(rad)

    dx, dz = xk - 0.0, zk - zc
    L = math.hypot(dx, dz)
    ux, uz = dx / L, dz / L
    xt = Rc * ux
    zt = zc + Rc * uz

    a0 = math.atan2(0.0 - zk, r - xk)
    a1 = math.atan2(zt - zk, xt - xk)
    if a1 > a0:
        a1 -= 2 * math.pi
    knuckle_pts = [
        (xk + rk * math.cos(a), zk + rk * math.sin(a))
        for a in [a0 + i * (a1 - a0) / n_knuckle for i in range(n_knuckle + 1)]
    ]

    b0 = math.atan2(zt - zc, xt)
    b1 = -math.pi / 2
    crown_pts = [
        (Rc * math.cos(b), zc + Rc * math.sin(b))
        for b in [b0 + i * (b1 - b0) / n_crown for i in range(1, n_crown + 1)]
    ]

    pts = knuckle_pts + crown_pts
    prof = (
        cq.Workplane("XZ")
        .moveTo(*pts[0])
        .spline(pts[1:], includeCurrent=True)
        .lineTo(0, 0)
        .close()
    )
    return prof.revolve(360)


_HEAD_BUILDERS = {
    "flat":          _head_flat,
    "hemispherical": _head_hemispherical,
    "ellipsoidal":   _head_ellipsoidal,
    "torispherical": _head_torispherical,
}


def _build_outer_head(outer_d: float, head_type: str, params: dict) -> cq.Workplane:
    """Build a bottom head solid at z=0 extending downward."""
    if head_type not in _HEAD_BUILDERS:
        raise ValueError(
            f"Unknown head type '{head_type}'. "
            f"Choose from: {list(_HEAD_BUILDERS)}"
        )
    return _HEAD_BUILDERS[head_type](outer_d, **params)


def _build_top_head(outer_d: float, head_type: str, params: dict, z0: float) -> cq.Workplane:
    """
    Build a top head whose rim lies at z=z0 and extends upward.
    Reuses the bottom head builders by mirroring about XY.
    """
    h = _build_outer_head(outer_d, head_type, params)
    return h.mirror("XY").translate((0, 0, z0))


def _resolve_dims(
    inner_d: float | None, wall_t: float | None, outer_d: float | None
) -> tuple[float, float, float]:
    """(outer_d, inner_d, wall_t) from any two of them."""
    if sum(x is not None for x in (inner_d, wall_t, outer_d)) < 2:
        raise ValueError("At least two of {inner_d, wall_t, outer_d} must be provided.")
    if outer_d is None:
        _outer_d: float = float(inner_d) + 2.0 * float(wall_t)    # type: ignore[arg-type]
        _inner_d: float = float(inner_d)                          # type: ignore[arg-type]
        _wall_t:  float = float(wall_t)                           # type: ignore[arg-type]
    elif inner_d is None:
        _wall_t  = float(wall_t)                                  # type: ignore[arg-type]
        _outer_d = float(outer_d)
        _inner_d = _outer_d - 2.0 * _wall_t
    elif wall_t is None:
        _inner_d = float(inner_d)
        _outer_d = float(outer_d)
        _wall_t  = (_outer_d - _inner_d) / 2.0
    else:
        _inner_d, _outer_d, _wall_t = float(inner_d), float(outer_d), float(wall_t)
        if abs(_outer_d - (_inner_d + 2.0 * _wall_t)) > 1e-9:
            raise ValueError(
                f"Inconsistent dimensions: outer_d ({_outer_d}) != inner_d ({_inner_d}) + 2*wall_t ({_wall_t})."
            )
    if _inner_d <= 0:        raise ValueError("inner_d must be > 0")
    if _wall_t  <= 0:        raise ValueError("wall_t must be > 0")
    if _outer_d <= _inner_d: raise ValueError("outer_d must be > inner_d")
    return _outer_d, _inner_d, _wall_t


def _head_defaults(wall_t, bottom_head_type, bottom_head_params,
                   top_head_type, top_head_params) -> tuple[dict, dict]:
    """Fill in head defaults and check the ones that have no sensible default."""
    bottom_head_params = dict(bottom_head_params or {})
    top_head_params    = dict(top_head_params    or {})
    if bottom_head_type == "flat":
        bottom_head_params.setdefault("plate_t", wall_t)
    if top_head_type == "flat":
        top_head_params.setdefault("plate_t", wall_t)
    if bottom_head_type == "ellipsoidal" and "head_depth" not in bottom_head_params:
        raise ValueError("bottom_head_type='ellipsoidal' requires head_depth in bottom_head_params")
    if top_head_type == "ellipsoidal" and "head_depth" not in top_head_params:
        raise ValueError("top_head_type='ellipsoidal' requires head_depth in top_head_params")
    return bottom_head_params, top_head_params


def _build_bore(
    inner_d: float, wall_t: float, straight_h: float,
    bottom_head_type: str | None, bottom_head_params: dict,
    top_head_type: str | None, top_head_params: dict,
) -> cq.Workplane:
    """
    The vessel's inner cavity as a SOLID — the cutter create_reactor_vessel
    removes from its outer shell to hollow it out.

    Sole definition of "inside the vessel", shared by the vessel builder and by
    anything that needs the pool envelope (the cost report bills the sodium as
    this volume minus everything standing in it). Kept as one function so the
    bore can never drift from the vessel that is actually built.
    """
    bore = cq.Workplane("XY").circle(inner_d / 2).extrude(straight_h)

    if bottom_head_type == "ellipsoidal":
        hd = float(bottom_head_params["head_depth"])
        p = dict(bottom_head_params)
        p["head_depth"] = max(hd - wall_t, 0.01 * hd)   # relative floor (was 1e-3 absolute)
        bore = bore.union(_build_outer_head(inner_d, "ellipsoidal", p))
    elif bottom_head_type not in (None, "flat"):
        bore = bore.union(_build_outer_head(inner_d, bottom_head_type, bottom_head_params))

    # The inner (cavity) dome MUST get the same lift as the outer dome.
    # Placing it lower leaves the dome crown solid: apex wall = wall_t + plate_t
    # instead of wall_t.
    if top_head_type == "ellipsoidal":
        hd = float(top_head_params["head_depth"])
        p = dict(top_head_params)
        p["head_depth"] = max(hd - wall_t, 0.01 * hd)   # relative floor (was 1e-3 absolute)
        bore = bore.union(_build_top_head(inner_d, "ellipsoidal", p, straight_h))
    elif top_head_type not in (None, "flat"):
        bore = bore.union(_build_top_head(inner_d, top_head_type, top_head_params, straight_h))

    return bore


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_reactor_vessel_bore(
    straight_h: float,
    *,
    inner_d: float | None = None,
    wall_t:  float | None = None,
    outer_d: float | None = None,
    bottom_head_type:   str | None = None,
    bottom_head_params: dict | None = None,
    top_head_type:      str | None = None,
    top_head_params:    dict | None = None,
) -> cq.Workplane:
    """
    The vessel's inner cavity as a solid — same signature as
    create_reactor_vessel, same code path, so the two always agree.

    This is the pool envelope. Everything the vessel contains stands in this
    volume; what is left over is coolant.
    """
    if straight_h <= 0: raise ValueError("straight_h must be > 0")
    _, inner_d_r, wall_t_r = _resolve_dims(inner_d, wall_t, outer_d)
    bhp, thp = _head_defaults(wall_t_r, bottom_head_type, bottom_head_params,
                              top_head_type, top_head_params)
    return _build_bore(inner_d_r, wall_t_r, straight_h,
                       bottom_head_type, bhp, top_head_type, thp)


def create_reactor_vessel(
    straight_h: float,
    *,
    inner_d: float | None = None,
    wall_t:  float | None = None,
    outer_d: float | None = None,
    bottom_head_type:   str | None = None,
    bottom_head_params: dict | None = None,
    top_head_type:      str | None = None,
    top_head_params:    dict | None = None,
    # REMOVED (older version): top_plate_thickness / top_plate_hole_groups —
    # the vessel-embedded top plate (fused into the vessel solid) was ≤V6
    # legacy, bypassed the resolver (no auto-holes, no IHX alignment, no
    # validation) and was used by nothing. Use a separate
    # obj_type="reactor_top_plate" component instead.
) -> cq.Workplane:
    """
    Build a reactor vessel with optional head geometries and top plate.

    The cylindrical shell always runs from z=0 to z=straight_h. The top face
    is therefore always exactly at z=straight_h, making top plate positioning
    exact without any bounding box calculation.

    Local origin / datum: vessel axis = local Z; z = 0 at the bottom of the
    straight shell (a bottom head, if any, extends below z = 0).

    Parameters
    ----------
    straight_h : float
        Height of the straight cylindrical section (unitless).
    inner_d : float, optional
        Inner diameter (unitless).
    wall_t : float, optional
        Wall thickness (unitless).
    outer_d : float, optional
        Outer diameter (unitless). At least two of {inner_d, wall_t, outer_d} must be supplied;
        the missing one is derived. If all three are given they must satisfy
        outer_d == inner_d + 2*wall_t.

    bottom_head_type : str, optional
        'flat' | 'hemispherical' | 'ellipsoidal' | 'torispherical'
        If None, the vessel has an open bottom.
    bottom_head_params : dict, optional
        Parameters forwarded to the bottom head builder:
          flat:          plate_t (defaults to wall_t)
          ellipsoidal:   head_depth (required)
          torispherical: Rc, rk (both optional, have defaults)
          hemispherical: no extra params needed

    top_head_type : str, optional
        Same options as bottom_head_type. If None, the vessel has an open top.
        The head rim sits at z = straight_h.
    top_head_params : dict, optional
        Same structure as bottom_head_params.

    For a top plate, use the separate obj_type="reactor_top_plate" component
    (resolver-aware: auto-holes, IHX alignment, validation). The old
    vessel-embedded plate (top_plate_thickness/top_plate_hole_groups) was
    removed — see the note in the signature.

    Returns
    -------
    cq.Workplane
        Single fused solid: shell + heads.
    """
    if straight_h <= 0: raise ValueError("straight_h must be > 0")

    outer_d, inner_d, wall_t = _resolve_dims(inner_d, wall_t, outer_d)
    bottom_head_params, top_head_params = _head_defaults(
        wall_t, bottom_head_type, bottom_head_params, top_head_type, top_head_params
    )

    # ------------------------------------------------------------------ #
    # 1.  Outer shell + heads                                             #
    # ------------------------------------------------------------------ #
    outer = cq.Workplane("XY").circle(outer_d / 2).extrude(straight_h)

    if bottom_head_type == "flat":
        t = float(bottom_head_params["plate_t"])
        outer = outer.union(cq.Workplane("XY").circle(outer_d / 2).extrude(-t))
    elif bottom_head_type is not None:
        outer = outer.union(_build_outer_head(outer_d, bottom_head_type, bottom_head_params))

    # OLDER VERSION (embedded plate lifted the head above the fused plate):
    # top_head_z = straight_h + (top_plate_thickness or 0.0)
    top_head_z = straight_h
    if top_head_type == "flat":
        t = float(top_head_params["plate_t"])
        outer = outer.union(
            cq.Workplane("XY").workplane(offset=top_head_z).circle(outer_d / 2).extrude(t)
        )
    elif top_head_type is not None:
        outer = outer.union(_build_top_head(outer_d, top_head_type, top_head_params, top_head_z))

    # ------------------------------------------------------------------ #
    # 2.  Inner bore (cutter) — shared with create_reactor_vessel_bore(),  #
    #     which is how the cost report gets the pool envelope.             #
    # ------------------------------------------------------------------ #
    inner = _build_bore(inner_d, wall_t, straight_h,
                        bottom_head_type, bottom_head_params,
                        top_head_type, top_head_params)

    vessel = outer.cut(inner).clean()

    # OCCT can leave the result as a compound of sub-shapes. Force a true
    # topological fusion so the STEP export contains exactly one solid per
    # component (required for DAGMC neutronics workflows).
    solids = vessel.solids().vals()
    fused = solids[0]
    for s in solids[1:]:
        fused = fused.fuse(s)  # type: ignore
    vessel = cq.Workplane().add(fused)

    return vessel


# ---------------------------------------------------------------------------
# Usage examples
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import cadquery as cq
    from ocp_vscode import show

    # ------------------------------------------------------------------
    # Example A: ellipsoidal bottom, open top (for a top plate use the
    # separate reactor_top_plate component)
    # ------------------------------------------------------------------
    assembly_A = create_reactor_vessel(
        inner_d    = 4.72,
        wall_t     = 0.04,
        straight_h = 5.5,
        bottom_head_type   = "ellipsoidal",
        bottom_head_params = {"head_depth": 1.0},
    )
    show(assembly_A)
    import time; time.sleep(2)
    # ------------------------------------------------------------------
    # Example B: torispherical bottom, flat top head, no top plate
    # ------------------------------------------------------------------
    assembly_B = create_reactor_vessel(
        inner_d    = 4.72,
        wall_t     = 0.04,
        straight_h = 5.5,
        bottom_head_type   = "torispherical",
        bottom_head_params = {"Rc": 4.72, "rk": 0.06 * 4.72},
        top_head_type      = "flat",
    )
    show(assembly_B)
    import time; time.sleep(2)
    # ------------------------------------------------------------------
    # Example C: ellipsoidal bottom AND ellipsoidal top head (closed vessel)
    # ------------------------------------------------------------------
    assembly_C = create_reactor_vessel(
        inner_d    = 4.72,
        wall_t     = 0.04,
        straight_h = 5.5,
        bottom_head_type   = "ellipsoidal",
        bottom_head_params = {"head_depth": 1.0},
        top_head_type      = "ellipsoidal",
        top_head_params    = {"head_depth": 1.0},
    )
    show(assembly_C)
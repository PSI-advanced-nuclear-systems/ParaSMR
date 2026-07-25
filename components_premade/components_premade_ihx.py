"""
Parametric shell-and-tube IHX builder.

Seven main components
──────────────────────────────────────────────────────
  lower_plenum_shell   bowl dome + cylindrical shell + top plate
  tube_bundle          n hollow vertical tubes
  upper_plenum_shell   bottom plate + cylindrical shell + top dome
  central_pipe         L-shaped: vert on axis (through both plenums) → arc → horiz exit
                       (bends inside upper plenum, exits +X wall)
  outlet_riser         straight vertical pipe above upper dome — independent of central_pipe
  lateral_pipe         horizontal pipe connected to outlet_riser +X wall
  bundle_shell         windowed wrapper cylinder around the tube bundle

Coordinate convention
─────────────────────
  z = 0  →  bottom face of lower plenum cylindrical section
  +z     →  upward; all horizontal exits in +X direction (y = 0 plane)
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import cadquery as cq


def create_ihx(spec: Dict[str, Any]) -> cq.Workplane:
    """
    Build a shell-and-tube IHX from spec dict. All parameters unitless and consistent.

    Components: lower plenum, upper plenum, tube bundle, central pipe, outlet riser,
    lateral pipe, bundle shell. See spec keys for geometry, dimensions, and positioning.

    Returns fully fused IHX geometry (all components unioned).
    """

    lp_ir, lp_wall = spec["lower_plenum_inner_radius"], spec["lower_plenum_wall"]
    lp_h,  lp_dr   = spec["lower_plenum_height"],       spec["lower_plenum_dome_radius"]

    up_ir, up_wall = spec["upper_plenum_inner_radius"], spec["upper_plenum_wall"]
    up_h,  up_dr   = spec["upper_plenum_height"],       spec["upper_plenum_dome_radius"]
    up_or           = up_ir + up_wall

    bh = float(spec["bundle_height"])

    # Tube rings
    tube_rings: List[Dict[str, Any]] = spec["tube_rings"]
    cp_ir       = spec["central_pipe_inner_radius"]
    cp_wall_t   = spec["central_pipe_wall"]
    cp_or       = cp_ir + cp_wall_t
    cp_bend     = spec["central_pipe_bend_radius"]
    cp_z        = spec["central_pipe_z_offset"]   # bend centre z above upper plenum bottom
    cp_horiz    = spec["central_pipe_horiz_len"]

    rs_ir   = spec["riser_inner_radius"]
    rs_wall = spec["riser_wall"]
    rs_h    = spec["riser_height"]
    rs_or   = rs_ir + rs_wall

    lat_ir   = spec["lateral_pipe_inner_radius"]
    lat_wall = spec["lateral_pipe_wall"]
    lat_or   = lat_ir + lat_wall
    lat_len  = spec["lateral_pipe_length"]
    lat_z    = spec["lateral_pipe_z_offset"]

    assert cp_z + cp_bend < up_h, (
        f"Central pipe bend exits the upper plenum top. "
        f"Need central_pipe_z_offset + central_pipe_bend_radius < upper_plenum_height "
        f"(currently {cp_z + cp_bend:.1f} >= {up_h})"
    )

    # Z layout
    z_lp_top = lp_h                 # top plate of lower plenum
    z_up_bot = z_lp_top + bh        # bottom plate of upper plenum
    z_up_top = z_up_bot + up_h      # top of upper plenum cylindrical section
    z_rs_bot = z_up_top + up_dr     # base of outlet riser (above dome tip)

    # Axial overshoot: sub-components extend this far past their nominal plate
    # boundary so they physically penetrate the plate material (volumetric
    # overlap), which OCCT fuse handles reliably. Coincident-face-only contact
    # (zero overlap) is NOT reliable in OCCT BRepAlgoAPI_Fuse.
    _overshoot   = min(lp_wall, up_wall) / 2   # axial (Z) penetration depth
    _r_overshoot = min(lp_wall, up_wall) * 0.02  # radial penetration for dome bore

    z_cp_bend   = z_up_bot + cp_z
    z_cp_horiz  = z_cp_bend + cp_bend
    z_cp_bot    = z_lp_top - _overshoot    # extends into lower tube-sheet plate

    # Primitive helpers

    def _annular_cyl(ir, wall, h, z_bot):
        cz = z_bot + h / 2
        return (cq.Workplane("XY").workplane(offset=cz).cylinder(h, ir + wall)
                .cut(cq.Workplane("XY").workplane(offset=cz).cylinder(h, ir)).val())

    def _solid_disc(r, h, z_bot):
        cz = z_bot + h / 2
        return cq.Workplane("XY").workplane(offset=cz).cylinder(h, r).val()

    def _dome_shell(dome_r, wall, z_eq, keep_upper):
        outer = cq.Workplane("XY").workplane(offset=z_eq).sphere(dome_r)
        inner = cq.Workplane("XY").workplane(offset=z_eq).sphere(dome_r - wall)
        shell = outer.cut(inner)
        b = dome_r * 4
        cut = (cq.Workplane("XY").workplane(offset=z_eq - dome_r).box(b, b, dome_r * 2)
               if keep_upper else
               cq.Workplane("XY").workplane(offset=z_eq + dome_r).box(b, b, dome_r * 2))
        return shell.cut(cut).val()

    def _fuse(*shapes):
        result = shapes[0]
        for s in shapes[1:]:
            result = result.fuse(s)
        return result

    components: Dict[str, Any] = {}

    def _ring_xy(ring: Dict[str, Any]) -> List[Tuple[float, float]]:
        """Tube ring positions: use pre-computed or generate from n, pitch_radius, angle."""
        if "_xy_pos" in ring:
            return ring["_xy_pos"]
        n = int(ring["n"])
        r = float(ring["pitch_radius"])
        a0_deg = float(ring.get("start_angle_deg", 0.0))
        return [(r * math.cos(math.radians(a0_deg + 360.0 * i / n)),
                 r * math.sin(math.radians(a0_deg + 360.0 * i / n)))
                for i in range(n)]

    # Tubes must clear the central pipe: they can neither intersect it nor
    # sit inside it. Fail loudly — a ring inside the pipe would otherwise be
    # silently destroyed by the central-pipe bore cut at the end of the build.
    for i, ring in enumerate(tube_rings):
        r_or_t  = float(ring["inner_radius"]) + float(ring["wall"])
        closest = min(math.hypot(tx, ty) for tx, ty in _ring_xy(ring)) - r_or_t
        if closest < cp_or:
            raise ValueError(
                f"tube_rings[{i}]: tube surfaces reach within {closest:.4g} of "
                f"the IHX axis, but the central pipe extends to radius "
                f"{cp_or:.4g}. Tubes must clear the central pipe (closest "
                f"approach >= {cp_or:.4g}) — move the ring outward or remove it."
            )

    # 1. LOWER PLENUM SHELL
    lp_sh = _fuse(
        _dome_shell(lp_dr, lp_wall, z_eq=0.0, keep_upper=False),
        _annular_cyl(lp_ir, lp_wall, lp_h, z_bot=0.0),
        _solid_disc(lp_ir, lp_wall, z_bot=z_lp_top - lp_wall),
    )
    components["lower_plenum_shell"] = lp_sh

    # 2. TUBE BUNDLE
    _bh_ext = bh + 2 * _overshoot
    _cz_ext = z_lp_top + bh / 2

    tube_solids = []
    for ring in tube_rings:
        r_ir = float(ring["inner_radius"])
        r_or = r_ir + float(ring["wall"])
        for tx, ty in _ring_xy(ring):
            tube_solids.append(
                cq.Workplane("XY").workplane(offset=_cz_ext).center(tx, ty).cylinder(_bh_ext, r_or)
                .cut(cq.Workplane("XY").workplane(offset=_cz_ext).center(tx, ty).cylinder(_bh_ext, r_ir))
                .val()
            )
    # 3. BUNDLE SHELL (wrapper cylinder with windows)
    bs_wall   = float(spec["bundle_shell_wall"])
    bs_ir     = float(spec["bundle_shell_inner_radius"])
    bs_or     = bs_ir + bs_wall
    bs_n_bars = int(spec["bundle_shell_n_bars"])
    bs_bar_w  = float(spec["bundle_shell_bar_width"])    # arc length at inner surface
    if "bundle_shell_window_height" in spec:
        bs_win_h = float(spec["bundle_shell_window_height"])
    else:
        fraction = float(spec.get("bundle_shell_window_fraction", 0.4))
        bs_win_h = bh * fraction
    # Default gap = half the window height below the upper plenum bottom plate.
    bs_win_dz       = float(spec.get("bundle_shell_window_z_from_top",    bs_win_h / 2.0))
    # Lower row inherits the upper gap unless explicitly overridden.
    bs_win_dz_lower = float(spec.get("bundle_shell_window_z_from_bottom", bs_win_dz))

    assert bs_n_bars >= 1, "bundle_shell_n_bars must be >= 1"
    bar_half_angle = bs_bar_w / (2.0 * bs_ir)          # radians
    win_half_angle = math.pi / bs_n_bars - bar_half_angle
    assert win_half_angle > 0, (
        f"bundle_shell_bar_width ({bs_bar_w}) leaves no room for windows. "
        "Reduce bar_width or increase n_bars."
    )

    # Shell extends by _overshoot into both plates for fusion connectivity
    bs_sh = _annular_cyl(bs_ir, bs_wall, bh + 2 * _overshoot, z_bot=z_lp_top - _overshoot)

    cutter_h = bs_win_h * 1.05
    chord    = 2.0 * (bs_or + bs_wall * 0.2) * math.sin(win_half_angle)
    depth    = bs_wall * 3.0
    x_cen    = bs_ir + bs_wall / 2.0   # radial centre of wall

    # Upper windows: top-anchored at z_up_bot − bs_win_dz.
    # 5 % overshoot goes downward only → never intrudes into upper plenum plate.
    z_win_top      = z_up_bot - bs_win_dz
    cutter_cen_top = z_win_top - cutter_h / 2.0

    for i in range(bs_n_bars):
        theta_deg = 360.0 * i / bs_n_bars
        cutter = (
            cq.Workplane("XY")
            .box(depth, chord, cutter_h)
            .translate((x_cen, 0.0, cutter_cen_top))
            .rotate((0, 0, 0), (0, 0, 1), theta_deg)
            .val()
        )
        bs_sh = bs_sh.cut(cutter)       # type: ignore

    # Lower windows: anchored at z_lp_top + bs_win_dz_lower. By default
    # bs_win_dz_lower == bs_win_dz (symmetric with the upper row); supply
    # bundle_shell_window_z_from_bottom in the spec to shift this row alone.
    # 5 % overshoot goes upward only → never intrudes into lower plenum plate.
    z_bot_win_bot  = z_lp_top + bs_win_dz_lower
    cutter_cen_bot = z_bot_win_bot + cutter_h / 2.0

    for i in range(bs_n_bars):
        theta_deg = 360.0 * i / bs_n_bars
        cutter = (
            cq.Workplane("XY")
            .box(depth, chord, cutter_h)
            .translate((x_cen, 0.0, cutter_cen_bot))
            .rotate((0, 0, 0), (0, 0, 1), theta_deg)
            .val()
        )
        bs_sh = bs_sh.cut(cutter)       # type: ignore

    components["bundle_shell"] = bs_sh

    # 
    # 4. CENTRAL PIPE  (vert on axis → 90° arc inside upper plenum → horiz exit)
    # 
    # Path: starts at lower plenum top, rises through bundle, bends 90° inside
    # upper plenum at (0, z_cp_bend), exits horizontally at (up_or + cp_horiz, z_cp_horiz)

    x_cp_far = up_or + cp_horiz   # far end; cp_horiz measured from the outer wall

    cp_path = (
        cq.Workplane("XZ")
        .moveTo(0, z_cp_bot)
        .lineTo(0, z_cp_bend)
        .radiusArc((cp_bend, z_cp_horiz), cp_bend)
        .lineTo(x_cp_far, z_cp_horiz)
        .wire().val()
    )

    cp_pipe = (
        cq.Workplane("XY").workplane(offset=z_cp_bot)
        .circle(cp_or).circle(cp_ir)
        .sweep(cq.Workplane("XY").newObject([cp_path]), isFrenet=True)
    )
    components["central_pipe"] = cp_pipe.val()

    # 
    # 5. UPPER PLENUM SHELL
    # 
    up_sh = _fuse(
        _solid_disc(up_ir, up_wall, z_bot=z_up_bot),
        _annular_cyl(up_ir, up_wall, up_h, z_bot=z_up_bot),
        _dome_shell(up_dr, up_wall, z_eq=z_up_top, keep_upper=True),
    )
    # Riser dome bore: cut slightly smaller than riser outer radius so the
    # riser wall (outer = rs_or) has _r_overshoot radial overlap with the dome
    # material → volumetric overlap → guaranteed OCCT fusion.
    # OLDER VERSION (unit-carrying constants — the "-1" reached below the
    # upper-plenum bottom plate at metre scale and punched a hole through it):
    # up_sh = up_sh.cut(_solid_disc(rs_or - _r_overshoot, up_dr * 2 + 2, z_bot=z_up_top - 1))
    # Geometry-derived bounds: start a wall-fraction below the dome base
    # (_overshoot), cut up past the dome tip (2*up_dr) — scale-free, and the
    # cutter can never reach the bottom plate.
    up_sh = up_sh.cut(_solid_disc(rs_or - _r_overshoot, 2 * up_dr, z_bot=z_up_top - _overshoot))
    # No holes pre-cut for the central pipe or tubes. The central pipe
    # (z_cp_bot inside the lower plate, horizontal sweep through the +X wall)
    # and all tubes (_overshoot puts them inside the bottom plate) will
    # volumetrically overlap with the solid plate and shell wall → OCCT fusion.
    components["upper_plenum_shell"] = up_sh

    # 
    # 6. OUTLET RISER  (closed-top vertical pipe sitting flush on the dome)
    # 
    # Geometry: closed top cap, annular wall, flush at dome surface.
    # For a hemispherical dome of radius up_dr centred at z_up_top, a vertical
    # cylinder of radius rs_or intersects the dome surface at height
    #   z_clip = z_up_top + sqrt(up_dr² - rs_or²)
    # That is where the riser bottom sits — the riser's outer cylinder is
    # tangent to the dome's truncated rim.
    #
    # The dome shell is then cut by the same rs_or cylinder, from z_up_top - 1
    # up to z_clip + 1 — opening the dome at its apex with a circular hole
    # exactly the size of the riser bore + wall. Fluid in the dome rises
    # through this hole straight into the riser bore.
    #
    if up_dr <= rs_or:
        raise ValueError(
            f"Upper plenum dome radius ({up_dr}) must be > riser outer radius "
            f"({rs_or}); otherwise the dome cannot fully contain the riser passage."
        )
    z_clip   = z_up_top + math.sqrt(up_dr * up_dr - rs_or * rs_or)
    z_rs_low = z_clip - _overshoot          # extend into dome bore for fusion
    rs_h_tot = rs_h + (z_rs_bot - z_rs_low)
    cz_rs    = z_rs_low + rs_h_tot / 2

    rs_wp = (
        cq.Workplane("XY").workplane(offset=cz_rs).cylinder(rs_h_tot, rs_or)
        .cut(cq.Workplane("XY").workplane(offset=cz_rs).cylinder(rs_h_tot, rs_ir))
    )

    z_cap_top = z_rs_low + rs_h_tot
    cap_cz    = z_cap_top - rs_wall / 2.0
    rs_wp = rs_wp.union(
        cq.Workplane("XY").workplane(offset=cap_cz).cylinder(rs_wall, rs_or)
    )

    # Lateral bore — punches the +X wall AND the curved inner wall.
    # The cutter starts at x=0 (inside the riser bore, where there is no material)
    # so it penetrates the curved inner wall (r=rs_ir) and creates a proper 2D
    # curved opening between the riser bore and the lateral pipe bore.
    # Starting at x=rs_ir (the inner surface) would only produce a tangent-line
    # contact — zero area, no real passage.
    rs_wp = rs_wp.cut(
        cq.Workplane("YZ").workplane(offset=0)
        .center(0, z_rs_bot + lat_z)
        .circle(lat_or)
        .extrude(rs_or + lat_or)   # one lateral radius past the riser wall (was +1.0 absolute)
    )
    components["outlet_riser"] = rs_wp.val()

    # 
    # 7. LATERAL PIPE
    # 
    #
    # The lateral pipe wall starts at the riser's INNER radius (offset=rs_ir),
    # not at the axis and not at the outer radius. This way:
    #   • the wall material from rs_ir to rs_or is fully embedded in the
    #     riser's +X wall — no intrusion into the riser bore, no gap,
    #   • the bore of the lateral opens cleanly into the riser bore on one
    #     side and extends lat_len beyond the riser outer wall on the other.
    # The visible exterior length (from riser outer wall outward) is still
    # lat_len, so existing assembly callers don't need to change anything.
    z_lat_cen   = z_rs_bot + lat_z
    lat_total_l = rs_or - rs_ir + lat_len   # from inside surface of riser wall
    components["lateral_pipe"] = (
        cq.Workplane("YZ").workplane(offset=rs_ir)
        .center(0, z_lat_cen).circle(lat_or).extrude(lat_total_l)
        .cut(
            cq.Workplane("YZ").workplane(offset=rs_ir)
            .center(0, z_lat_cen).circle(lat_ir).extrude(lat_total_l)
        ).val()
    )

    workplanes = [
        s if isinstance(s, cq.Workplane) else cq.Workplane().newObject([s])
        for s in components.values()
    ]
    fused = workplanes[0]
    for wp in workplanes[1:]:
        fused = fused.union(wp)
    # Fuse each tube individually so OCCT processes one coincident-face connection
    # at a time. Fusing a 120-solid compound in a single call is unreliable —
    # not all shared cylindrical faces with both tube-sheet plates are detected.
    for ts in tube_solids:
        fused = fused.union(cq.Workplane().newObject([ts]))

    # ── Open the fluid passages (post-fusion bore cutters) ──────────────
    # Fusion guarantees METAL continuity only: the solid tube-sheet plates
    # and the plenum wall fill every bore where a tube or the central pipe
    # crosses them. Cut the bores back open (same pattern as the pump's
    # bore punches). All margins are _overshoot-relative — scale-free.
    #
    # 1. Tube bores through BOTH tube-sheet plates (two slab cuts per tube;
    #    the bore inside the tube's own length is already open).
    _slabs = [(z_lp_top - lp_wall - _overshoot, z_lp_top + _overshoot),
              (z_up_bot - _overshoot,           z_up_bot + up_wall + _overshoot)]
    tube_bores = []
    for ring in tube_rings:
        r_ir = float(ring["inner_radius"])
        for tx, ty in _ring_xy(ring):
            for z0, z1 in _slabs:
                tube_bores.append(
                    cq.Workplane("XY").workplane(offset=(z0 + z1) / 2)
                    .center(tx, ty).cylinder(z1 - z0, r_ir).val())
    fused = fused.cut(
        cq.Workplane().newObject([cq.Compound.makeCompound(tube_bores)]))
    #
    # 2. Central-pipe bore: swept along the SAME centerline, extended
    #    downward through the lower tube sheet (mouth opens into the lower
    #    plenum) and past the far end. Cutting it re-opens the crossings
    #    through the upper-plenum bottom plate and the +X wall, while the
    #    pipe's own wall stays intact — pipe and plenum never communicate.
    z_bore_bot = z_lp_top - lp_wall - _overshoot
    cp_bore_path = (
        cq.Workplane("XZ")
        .moveTo(0, z_bore_bot)
        .lineTo(0, z_cp_bend)
        .radiusArc((cp_bend, z_cp_horiz), cp_bend)
        .lineTo(x_cp_far + _overshoot, z_cp_horiz)
        .wire().val()
    )
    cp_bore = (
        cq.Workplane("XY").workplane(offset=z_bore_bot)
        .circle(cp_ir)
        .sweep(cq.Workplane("XY").newObject([cp_bore_path]), isFrenet=True)
    )
    fused = fused.cut(cp_bore)

    return fused.clean()


# ─── Demo ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo_spec = {
        # Lower plenum
        "lower_plenum_inner_radius": 300.0,
        "lower_plenum_wall":          20.0,
        "lower_plenum_height":        200.0,
        "lower_plenum_dome_radius":   320.0,
        # Upper plenum
        "upper_plenum_inner_radius": 300.0,
        "upper_plenum_wall":          20.0,
        "upper_plenum_height":        300.0,
        "upper_plenum_dome_radius":   320.0,
        # Tube bundle — multiple circumferential rings
        "bundle_height": 2000.0,
        "tube_rings": [
            #dict(n=6,  inner_radius=12.0, wall=2.0, pitch_radius= 80.0),
            dict(n=12, inner_radius=12.0, wall=2.0, pitch_radius=150.0),
            dict(n=18, inner_radius=10.0, wall=2.0, pitch_radius=220.0),
            dict(n=18, inner_radius=10.0, wall=2.0, pitch_radius=260.0),
        ],
        # Central pipe — on axis, bends inside upper plenum, exits +X wall
        "central_pipe_inner_radius":  60.0,
        "central_pipe_wall":          10.0,
        "central_pipe_bend_radius":   80.0,
        "central_pipe_z_offset":     100.0,  # 100 + 80 = 180 < 300 (up_h) ✓
        "central_pipe_horiz_len":    400.0,
        # Outlet riser — independent, above upper dome
        "riser_inner_radius": 80.0,
        "riser_wall":         10.0,
        "riser_height":      300.0,
        # Lateral pipe
        "lateral_pipe_inner_radius":  40.0,
        "lateral_pipe_wall":           8.0,
        "lateral_pipe_length":        300.0,
        "lateral_pipe_z_offset":      150.0,
        # Bundle shell — wrapper cylinder with windowed upper section
        "bundle_shell_inner_radius":    285.0,   # > outermost tube edge (260+10=270)
        "bundle_shell_wall":            15.0,
        "bundle_shell_n_bars":           8,
        "bundle_shell_bar_width":        20.0,
        "bundle_shell_window_fraction":   0.2,  # 20 % of bundle_height (400 mm)
    }

    print("Building simple IHX ...")
    assembly = create_ihx(demo_spec)
    print("Done — showing in ocp_vscode ...")
    from ocp_vscode import show
    show(assembly)

"""
Parametric SFR above-core structure (ACS).

Axially-stacked assembly: bottom ring + tapered cone + neck + top cylinder,
all revolved about the local Z axis.

Geometry:
  • Lower shell (z=0 to z=bottom_ring_height+cone_height+neck_height)
    - Bottom ring, cone, neck revolved about Z axis (hollow, uniform wall_t)
  • Top cylinder (above the neck)
    - Solid cylinder of radius top_cyl_outer_r and height top_cyl_height
    - Can be offset from the Z axis via top_cyl_offset_x/y

The lower shell stays centered on the Z axis so it aligns with the reactor
core via center_coords. The top cylinder offset allows clearance around
nearby components (IHX, pumps).

Axial dimensions (all unitless):
  • bottom_ring_height      — height of the bottom ring
  • cone_height             — height of the cone
  • neck_height             — height of the straight neck section
  • top_cyl_height          — height of the top cylinder
  Total height = sum of the above four parameters

Single public function:  create_above_core_structure()
"""

from __future__ import annotations
import math
import cadquery as cq

from profile_from_straight_connections import create_profile_from_straight_connections
from utils import revolve_profile


def _dedup(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    EPS = 1e-9
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > EPS or abs(p[1] - out[-1][1]) > EPS:
            out.append(p)
    return out


def _revolve_closed(pts: list[tuple[float, float]]) -> cq.Workplane:
    profile = create_profile_from_straight_connections(_dedup(pts), plane="XZ", closed=True)
    return revolve_profile(profile, angle=360, axis="Z")


def create_above_core_structure(
    top_cyl_outer_r: float,
    top_cyl_height:  float,
    neck_outer_r: float,
    neck_height:  float,
    wall_t: float,
    cone_bottom_outer_r: float,
    cone_height:         float,
    bottom_ring_height:  float,
    # The lower shell (cone + neck) sits on the local origin. The top
    # cylinder is translated by this offset. Set to (0, 0) for a coaxial
    # component; nonzero to displace the top cylinder sideways (e.g. to
    # clear pumps / IHX nozzles in the assembly).
    top_cyl_offset_x: float = 0.0,
    top_cyl_offset_y: float = 0.0,
    flow_hole_groups: list[dict] | None = None,
    # dict with keys:
    #   "through_d":          inner bore diameter                  (required)
    #   "pitch":              center-to-center hex ring spacing    (required)
    #   "pipe_wall_t":        tube wall thickness                  (default 0.0)
    #   "pipe_extend_bottom": protrusion below z=0                 (default 0.0)
    #   "pipe_extend_top":    protrusion above top cylinder        (default 0.0)
    crdl: dict | None = None,
    # dict with keys:
    #   "thickness": plate thickness
    # The plate spans z = 0 → thickness (upward, into the bore), so its
    # bottom face is coincident with the shell's bottom face at z=0. Outer
    # radius is cone_bottom_outer_r - wall_t (the shell's inner radius at the
    # base), so the plate sits inside the hollow lower shell with its rim
    # flush against the inner wall. For a flush fit keep
    # thickness <= bottom_ring_height (so the plate stays within the straight
    # bore before the cone tapers inward). Holes are punched at each CRDL
    # centre, sized to the pipe outer radius, so the CRDL tubes pass through.
    bottom_plate: dict | None = None,
    z_bottom: float = 0.0,

) -> cq.Workplane:
    """
    Build the above-core structure as a fused Workplane of two solids:

      1. ``lower_shell`` [0 → z3] — bottom ring + cone + neck.
      2. ``top_cyl``     [z3 → z4] — a single solid cylinder (the former
         closing plate is merged into this cylinder).

    Boolean ops (flow holes, bottom holes) are applied to each part before
    the final union. The straight section above the cone is a single neck at
    ``neck_outer_r``; there is no separate collar band, and the top cylinder
    is a single body with no separate closing plate.
    """
    checks = [
        (neck_outer_r > wall_t,              "neck_outer_r > wall_t"),
        (cone_bottom_outer_r > neck_outer_r, "cone_bottom_outer_r > neck_outer_r"),
    ]
    for ok, msg in checks:
        if not ok:
            raise ValueError(f"Validation failed: {msg}")
    for name, val in [
        ("top_cyl_height", top_cyl_height),
        ("top_cyl_outer_r", top_cyl_outer_r),
        ("neck_height", neck_height),
        ("cone_height", cone_height), ("bottom_ring_height", bottom_ring_height),
        ("wall_t", wall_t),
    ]:
        if val <= 0:
            raise ValueError(f"{name} must be > 0")
    z1 = bottom_ring_height
    z2 = z1 + cone_height        # cone top = neck bottom
    z3 = z2 + neck_height        # ← axis split (neck top = cylinder bottom)
    z4 = z3 + top_cyl_height
    # The lower shell sits on the LOCAL ORIGIN. The top cylinder + closing
    # plate are the ones that carry top_cyl_offset_x/y. This way the cone /
    # cone-axis hole pattern stay on the assembly's central axis (and so can
    # be aligned with the reactor core), while the top cylinder gets
    # displaced sideways.
    lower_pts = [
        # outer face (upward)
        (cone_bottom_outer_r,          0),
        (cone_bottom_outer_r,          z1),
        (neck_outer_r,                 z2),
        (neck_outer_r,                 z3),
        # inner face (downward) — uniform wall thickness wall_t
        (neck_outer_r - wall_t,        z3),
        (neck_outer_r - wall_t,        z2),
        (cone_bottom_outer_r - wall_t, z1),
        (cone_bottom_outer_r - wall_t, 0),
    ]
    lower_solid = _revolve_closed(lower_pts)
    # One plain solid cylinder spanning [z3 → z4], translated to the
    # top-cylinder offset. This replaces the former separate closing plate
    # and upper cylinder (which were coaxial and the same radius, so their
    # union was always a single cylinder).
    top_cyl = (
        cq.Workplane("XY")
        .workplane(offset=z3)
        .circle(top_cyl_outer_r)
        .extrude(top_cyl_height)
    )
    if top_cyl_offset_x != 0.0 or top_cyl_offset_y != 0.0:
        top_cyl = top_cyl.translate((top_cyl_offset_x, top_cyl_offset_y, 0))
    # Cutters are drilled radially (horizontal axis pointing toward the cone
    # centre) so they appear as circles on the cone surface, not rectangles.
    if flow_hole_groups:
        for group in flow_hole_groups:
            hole_r  = float(group["hole_r"])
            z_c     = float(group["z_center"])
            n       = int(group["n_holes"])
            start_a = float(group.get("start_angle_deg", 0.0))
            if z_c < 0 or z_c > z3:
                raise ValueError(f"z_center={z_c} outside [0, {z3:.4f}] (lower shell range)")
            if z_c <= z1:
                r_out = cone_bottom_outer_r
            elif z_c <= z2:
                frac  = (z_c - z1) / (z2 - z1)
                r_out = cone_bottom_outer_r + frac * (neck_outer_r - cone_bottom_outer_r)
            else:
                r_out = neck_outer_r
            # OLDER VERSION (absolute): EPS_h = 1e-4 (used as over = hole_r + EPS_h)
            # Drill each hole ALONG THE LOCAL SURFACE NORMAL so the opening is a
            # true circle on the wall, not the ellipse a horizontal drill leaves
            # on a slanted surface. Local meridian slope of the outer surface:
            #   bottom ring & neck → vertical wall (slope 0, normal horizontal)
            #   cone               → tapered, so the normal tilts off horizontal
            if z1 < z_c <= z2:
                dr_dz = (neck_outer_r - cone_bottom_outer_r) / (z2 - z1)
            else:
                dr_dz = 0.0
            n_len = math.hypot(1.0, dr_dz)
            n_r   = 1.0 / n_len            # radial part of the outward normal
            n_z   = -dr_dz / n_len         # axial part (tilts up on the cone)
            # Reach a full hole_r beyond each wall face, so the hole opens
            # cleanly through the wall and into the hollow cavity (you can see
            # in). The overshoot only passes into the empty interior.
            over  = 1.001 * hole_r     # relative over-reach (was hole_r + 1e-4)
            depth = wall_t + 2 * over
            for i in range(n):
                a     = math.radians(start_a + 360.0 * i / n)
                cos_a = math.cos(a)
                sin_a = math.sin(a)
                # 3D outward normal at this angle (unit), and a start point set
                # back outside the wall along +N.
                nx, ny, nz = n_r * cos_a, n_r * sin_a, n_z
                origin = (r_out * cos_a + over * nx,
                          r_out * sin_a + over * ny,
                          z_c + over * nz)
                # Plane normal = -N, so the extrusion drills inward along the
                # surface normal; xDir is the (perpendicular) circumferential dir.
                plane = cq.Plane(
                    origin=origin,
                    xDir=(-sin_a, cos_a, 0.0),
                    normal=(-nx, -ny, -nz),
                )
                cutter = (
                    cq.Workplane(plane)
                    .circle(hole_r)
                    .extrude(depth)
                )
                lower_solid = lower_solid.cut(cutter)
    # through_d = inner bore; pipe_wall_t = tube wall; extend_bottom/top
    # control how far the tubes protrude beyond the structure faces.
    if crdl:
        if "pitch" not in crdl:
            raise ValueError(
                "crdl requires 'pitch' (center-to-center hex ring spacing)"
            )
        through_d          = float(crdl["through_d"])
        pitch              = float(crdl["pitch"])
        pipe_wall_t        = float(crdl.get("pipe_wall_t", 0.0))
        pipe_extend_bottom = float(crdl.get("pipe_extend_bottom", 0.0))
        pipe_extend_top    = float(crdl.get("pipe_extend_top",    0.0))

        if through_d <= 0:
            raise ValueError("through_d must be > 0")

        through_r    = through_d / 2.0
        pipe_outer_r = through_r + pipe_wall_t
        pipe_z0      = -pipe_extend_bottom          # pipe bottom (≤ 0)
        pipe_z1      = z4 + pipe_extend_top         # pipe top   (≥ z4)
        pipe_h       = pipe_z1 - pipe_z0

        centers = [(0.0, 0.0)]
        for i in range(6):
            a = math.radians(60.0 * i)
            centers.append((pitch * math.cos(a), pitch * math.sin(a)))

        EPS = 1e-3 * pipe_h   # relative cutter over-length (was 1e-4 absolute)
        for hx, hy in centers:
            bore_cutter = (
                cq.Workplane("XY")
                .workplane(offset=pipe_z0 - EPS)
                .circle(through_r)
                .extrude(pipe_h + 2 * EPS)
                .translate((hx, hy, 0))
            )
            if pipe_wall_t > 0:
                pipe_outer_cyl = (
                    cq.Workplane("XY")
                    .workplane(offset=pipe_z0)
                    .circle(pipe_outer_r)
                    .extrude(pipe_h)
                    .translate((hx, hy, 0))
                )
                lower_solid = lower_solid.union(pipe_outer_cyl)
            lower_solid = lower_solid.cut(bore_cutter)
            top_cyl     = top_cyl.cut(bore_cutter)
    # The perforated plate nests INSIDE the hollow lower shell with its
    # bottom face coincident with the shell's bottom face at z=0. It spans
    # [0 → plate_t] (upward, into the bore), so its cylindrical rim is flush
    # against the shell's inner wall over the full plate thickness. Outer
    # radius = cone_bottom_outer_r - wall_t (the shell's inner radius at the
    # base). For a flush fit keep plate_t <= bottom_ring_height, so the plate
    # stays within the straight bore before the cone tapers inward.
    if bottom_plate:
        plate_t = float(bottom_plate["thickness"])
        plate_r = cone_bottom_outer_r - wall_t

        plate = (
            cq.Workplane("XY")
            .workplane(offset=0)
            .circle(plate_r)
            .extrude(plate_t)
        )

        if crdl:
            p_bore_r = float(crdl["through_d"]) / 2.0 + float(crdl.get("pipe_wall_t", 0.0))
            p_pitch  = float(crdl["pitch"])
            p_centers = [(0.0, 0.0)]
            for i in range(6):
                a = math.radians(60.0 * i)
                p_centers.append((p_pitch * math.cos(a), p_pitch * math.sin(a)))

            EPS = 1e-3 * plate_t   # relative cutter over-length (was 1e-4 absolute)
            for hx, hy in p_centers:
                hole = (
                    cq.Workplane("XY")
                    .workplane(offset=-EPS)
                    .circle(p_bore_r)
                    .extrude(plate_t + 2 * EPS)
                    .translate((hx, hy, 0))
                )
                plate = plate.cut(hole)

        lower_solid = lower_solid.union(plate)
    if z_bottom != 0.0:
        lower_solid = lower_solid.translate((0, 0, z_bottom))
        top_cyl     = top_cyl.translate((0, 0, z_bottom))
    return lower_solid.union(top_cyl).clean()


if __name__ == "__main__":
    from ocp_vscode import show

    assy = create_above_core_structure(
        top_cyl_outer_r      = 1.843,
        top_cyl_height       = 1.008,
        neck_outer_r         = 1.1085,
        neck_height          = 0.661,   # = old collar_height (0.092) + neck_height (0.569)
        wall_t               = 0.025,
        cone_height          = 2.429,
        cone_bottom_outer_r  = 1.403,
        bottom_ring_height   = 0.498,
        top_cyl_offset_x     = 0.6056,
        top_cyl_offset_y     = 0.0,
        crdl = {
            "through_d":          0.080,
            "pitch":              0.300,
            "pipe_wall_t":        0.005,
            "pipe_extend_bottom": 0.300,
            "pipe_extend_top":    0.300,
        },
        bottom_plate = {
            "thickness": 0.050,
        },
    )
    show(assy)




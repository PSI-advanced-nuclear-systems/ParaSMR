"""
SEALER-55 (Blykalla, Sweden) — envelope-level CAD input for ZeroLevelProduct.

Sources (referenced inline with short tags [catalogue] / [paper] / [PLACEHOLDER])
--------------------------------------------------------------------------------
[catalogue]   IAEA SMR Catalogue 2024, pp. 227-230 (SEALER-55 datasheet).
[paper]       IAEA-CN245-431, Wallenius et al. 2017 (older 3-10 MWe SEALER,
              architectural information only — dimensions are NOT transferable).
[image]       SEALER-55 cutaway (Blykalla / IAEA docs).
[PLACEHOLDER] Engineering estimate — swap in real values once available.

Units: metres throughout.

Reactor overview
----------------
Lead-cooled fast SMR, 140 MWt / 55 MWe, non-pressurised, forced circulation.
Core sits on a diagrid at the bottom of the RV. A central hollow chimney
[image] above the core encloses the 12 CRDs (2 B4C control + 10 WB2/B4C
shutdown [catalogue]). The chimney is CLOSED at the top by a thin cap;
the CRDs are ENTIRELY ENCLOSED inside the chimney — their tops sit just
below the cap. Modelled here as inserted to the CORE MID-PLANE (half
insertion), the CRDs reach halfway down into the core from the core top.
In the annulus between the chimney and the vessel wall are 8 primary pumps
(upper region) and 8 spiral-tube SGs (lower region) [paper].

Convention for this file
------------------------
The variables at the top block are ONLY those used in more than one
component dict, plus the ones the loops iterate on. Single-use values are
inlined in their dict with an in-line source tag.
"""

from assemble import assemble_objects
import math


# ═══════════════════════════════════════════════════════════════════════
# Shared / looped parameters (multi-use only — single-use values are inlined)
# ═══════════════════════════════════════════════════════════════════════

# --- Vessel + top plate (shared dimensions) -----------------------------
OUTER_D     = 4.8    # [catalogue] RV outer diameter (also = top plate outer_d)
STRAIGHT_H  = 4.3    # [catalogue] RV cyl height (also = top plate z_bottom)
TOP_PLATE_T = 0.15   # [PLACEHOLDER] top plate thickness (also needed for chimney z_top)

# --- Core (shared with chimney interface + CRD Z) -----------------------
CORE_Z_BOTTOM = 0.55            # [PLACEHOLDER] top of diagrid
CORE_HEIGHT   = 1.3             # [catalogue]   active height
CORE_Z_TOP    = CORE_Z_BOTTOM + CORE_HEIGHT   # = 1.85, chimney sits here

# --- Chimney (shared with top plate hole + cap) -------------------------
CHIMNEY_OUTER_R = 0.70                             # [PLACEHOLDER] ~1.4 m OD (from cutaway ratio)
CHIMNEY_WALL_T  = 0.02                             # [PLACEHOLDER] shell wall + top cap thickness
# CHIMNEY_Z_TOP is defined below, after the pump block — linked to pump top.

# --- Pump loop (8 in outer ring) ----------------------------------------
N_PUMPS               = 8       # [paper]
PUMP_RING_R           = 1.85    # [PLACEHOLDER]
PUMP_RADIUS           = 0.25    # [PLACEHOLDER]
PUMP_Z_BOTTOM         = 2.5     # [PLACEHOLDER]
PUMP_HEIGHT           = 3.0     # [PLACEHOLDER]
PUMP_ANGLE_OFFSET_DEG = 0.0

# --- Chimney height (linked to pump top) --------------------------------
CHIMNEY_Z_TOP = PUMP_Z_BOTTOM + PUMP_HEIGHT   # matches pump top

# --- SG loop (8 interleaved with pumps) ---------------------------------
N_SGS               = 8         # [catalogue]
SG_RING_R           = 1.85      # [PLACEHOLDER]
SG_RADIUS           = 0.30      # [PLACEHOLDER]
SG_Z_BOTTOM         = 0.55      # [PLACEHOLDER]
SG_HEIGHT           = 4.05      # [PLACEHOLDER]
SG_ANGLE_OFFSET_DEG = 22.5

# --- CRD loop (12 inside chimney, inserted to core mid-plane) -----------
N_CRDS               = 12                                # [catalogue]  2 control + 10 shutdown
CRD_RING_R           = 0.40                              # [PLACEHOLDER] must satisfy r + CRD_RADIUS < chimney bore
CRD_RADIUS           = 0.04                              # [PLACEHOLDER]
CRD_Z_BOTTOM         = CORE_Z_BOTTOM + CORE_HEIGHT / 2   # halfway inserted into core
CRD_ANGLE_OFFSET_DEG = 0.0

# Zero-clearance pierce-holes (component OD = hole ID). Raise for a visible gap.
CLEARANCE = 0.0


# ═══════════════════════════════════════════════════════════════════════
# Component specs — everything single-use is inlined with a source tag
# ═══════════════════════════════════════════════════════════════════════

object_specs = [

    # ─── Reactor vessel (non-pressurised) ─────────────────────────────
    # Bottom head: ellipsoidal 2:1 → depth = outer_d/4 = 1.2 m.
    # Total shell height = 4.3 + 1.2 = 5.5 m, matching catalogue 5.5/4.8.
    {
        "obj_type": "reactor_vessel",
        "obj_id":   "sealer55_rv",
        "outer_d":            OUTER_D,
        "wall_t":             0.04,               # [catalogue] SS316+AFA wall
        "straight_h":         STRAIGHT_H,
        "bottom_head_type":   "ellipsoidal",
        "bottom_head_params": {"head_depth": 1.2},   # 2:1 → outer_d/4
        # top left open; closed by reactor_top_plate below
        "color": (0.55, 0.60, 0.65, 1.0),         # opaque grey; drop alpha to 0.35 for see-through
    },

    # ─── Top plate (closure with penetrations) ─────────────────────────
    {
        "obj_type": "reactor_top_plate",
        "obj_id":   "sealer55_top_plate",
        "outer_d":   OUTER_D,
        "thickness": TOP_PLATE_T,
        "z_bottom":  STRAIGHT_H,
        "hole_groups": [
            # 1 central hole for the chimney — the 12 CRDs pass through
            # the chimney's own bore, so no separate CRD holes are needed.
            {
                "hole_diameter":    2 * CHIMNEY_OUTER_R + CLEARANCE,
                "layout":           "explicit_positions",
                "positions":        [(0.0, 0.0)],
            },
            # 8 pump holes
            {
                "hole_diameter":    2 * PUMP_RADIUS + CLEARANCE,
                "layout":           "symmetric",
                "count":            N_PUMPS,
                "placement_radius": PUMP_RING_R,
                "start_angle_deg":  PUMP_ANGLE_OFFSET_DEG,
            },
            # 8 SG holes (interleaved with pumps)
            {
                "hole_diameter":    2 * SG_RADIUS + CLEARANCE,
                "layout":           "symmetric",
                "count":            N_SGS,
                "placement_radius": SG_RING_R,
                "start_angle_deg":  SG_ANGLE_OFFSET_DEG,
            },
        ],
        "color": (0.60, 0.60, 0.65, 1.0),
    },

    # ─── Diagrid (core support) ────────────────────────────────────────
    {
        "obj_type": "diagrid",
        "obj_id":   "sealer55_diagrid",
        "diameter": 2.2,     # [PLACEHOLDER]  slightly larger than core envelope
        "height":   0.5,     # [PLACEHOLDER]
        "z_bottom": 0.05,    # [PLACEHOLDER]  just above bottom head knuckle
        "wall_t":   0.03,    # [PLACEHOLDER]
        "color":    (0.45, 0.50, 0.55, 1.0),
    },

    # ─── Core (hex prism, 6 sides) ─────────────────────────────────────
    # Circumscribed radius 1.0 m from 162 hex positions × 8 rings × 0.12 m
    # assembly pitch (typical LFR). 84 fuel + 66 ZrO2 reflector + 12 CRD.
    {
        "obj_type": "reactor_core",
        "obj_id":   "sealer55_core",
        "radius":   1.0,             # [PLACEHOLDER]  from 8 rings × 0.12 pitch
        "height":   CORE_HEIGHT,
        "z_bottom": CORE_Z_BOTTOM,
        "n_sides":  6,               # [catalogue]  hex-can lattice
        "color":    (0.85, 0.35, 0.20, 1.0),
    },

    # ─── Central chimney: hollow wall + top cap with CRD penetrations ──
    # [image] shows the chimney closed at the top; the wall + cap combo
    # produces a closed shroud with 12 holes for the CRD housings.
    {
        "operation":       "extrude",
        "obj_id":          "sealer55_chimney_wall",
        "profile":         {"obj_type": "circle", "radius": CHIMNEY_OUTER_R},
        "height":          CHIMNEY_Z_TOP - CORE_Z_TOP - CHIMNEY_WALL_T,   # leaves cap on top
        "wall_thickness":  CHIMNEY_WALL_T,
        "center_coords":   (0.0, 0.0, CORE_Z_TOP),
        "color":           (0.90, 0.55, 0.20, 1.0),   # orange, matching image
        "interfaces_with": ["sealer55_top_plate", "sealer55_core"],
    },
    {
        "operation":       "extrude",
        "obj_id":          "sealer55_chimney_cap",
        "profile":         {"obj_type": "circle", "radius": CHIMNEY_OUTER_R},
        "height":          CHIMNEY_WALL_T,
        "center_coords":   (0.0, 0.0, CHIMNEY_Z_TOP - CHIMNEY_WALL_T),
        "color":           (0.90, 0.55, 0.20, 1.0),   # same orange as wall
        # Solid disc — closes the top of the shroud entirely; nothing pierces it.
        "interfaces_with": ["sealer55_chimney_wall"],
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Repeat components: 8 pumps, 8 SGs, 12 CRDs (uniform arrays)
# ═══════════════════════════════════════════════════════════════════════

def _ring_position(ring_r, angle_deg, z_bottom):
    a = math.radians(angle_deg)
    return (ring_r * math.cos(a), ring_r * math.sin(a), z_bottom)


# --- 8 primary pump envelopes -------------------------------------------
for i in range(N_PUMPS):
    angle = PUMP_ANGLE_OFFSET_DEG + 360.0 * i / N_PUMPS
    object_specs.append({
        "operation":       "extrude",
        "obj_id":          f"sealer55_pump_{i+1}",
        "profile":         {"obj_type": "circle", "radius": PUMP_RADIUS},
        "height":          PUMP_HEIGHT,
        "center_coords":   _ring_position(PUMP_RING_R, angle, PUMP_Z_BOTTOM),
        "color":           (0.30, 0.55, 0.80, 1.0),
        "interfaces_with": ["sealer55_top_plate"],
    })

# --- 8 steam generator envelopes ----------------------------------------
for i in range(N_SGS):
    angle = SG_ANGLE_OFFSET_DEG + 360.0 * i / N_SGS
    object_specs.append({
        "operation":       "extrude",
        "obj_id":          f"sealer55_sg_{i+1}",
        "profile":         {"obj_type": "circle", "radius": SG_RADIUS},
        "height":          SG_HEIGHT,
        "center_coords":   _ring_position(SG_RING_R, angle, SG_Z_BOTTOM),
        "color":           (0.85, 0.65, 0.20, 1.0),
        "interfaces_with": ["sealer55_top_plate"],
    })

# --- 12 CRD housings — ENTIRELY ENCLOSED by the chimney ---------------
# Rods extend from the core mid-plane (half-insertion) up to just below
# the chimney cap (5 cm gap). They no longer pierce the top plate or the
# cap — the chimney's closed shroud fully encloses them.
for i in range(N_CRDS):
    angle = CRD_ANGLE_OFFSET_DEG + 360.0 * i / N_CRDS
    is_control = i < 2
    role = "control_rod" if is_control else "shutdown_rod"
    idx  = (i + 1) if is_control else (i - 1)   # 1..2 for control, 1..10 for shutdown
    object_specs.append({
        "operation":       "extrude",
        "obj_id":          f"sealer55_{role}_{idx}",
        "profile":         {"obj_type": "circle", "radius": CRD_RADIUS},
        "height":          CHIMNEY_Z_TOP - CHIMNEY_WALL_T - 0.05 - CRD_Z_BOTTOM,   # 5 cm gap under cap
        "center_coords":   _ring_position(CRD_RING_R, angle, CRD_Z_BOTTOM),
        "color":           (0.75, 0.20, 0.20, 1.0) if is_control
                           else (0.40, 0.20, 0.55, 1.0),
        "interfaces_with": ["sealer55_core"],   # only touches upper-half core
    })


# ═══════════════════════════════════════════════════════════════════════
# Build
# ═══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from ocp_vscode import show
    print(f"SEALER-55 assembly: {len(object_specs)} components")
    assembly = assemble_objects(
        object_specs,
        export_path="sealer55_detailed.step",
        units="m",
    )
    show(assembly)
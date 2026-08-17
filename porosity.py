"""
Per-component porosity, measured off the CAD.

Porosity here is the THERMAL-HYDRAULIC one — the fraction of a component's own
equivalent cylinder that is open to the PRIMARY coolant::

        porosity = V_primary_coolant / V_envelope

Two numbers are reported, because they answer different questions:

  porosity        volume assigned to a primary-coolant material, over the
                  envelope. This is the TRACE number: it is what the primary
                  flow can actually occupy.

  open_fraction   1 - V_solid / V_envelope. Circuit-BLIND — everything that is
                  not steel. An upper bound on porosity, and equal to it for any
                  component that only ever sees primary sodium.

The two differ exactly where a component holds fluid belonging to another
circuit. The IHX is the case that matters: its tube-side sodium is secondary, so
to the primary side it is blockage, not open volume. Counting it as open puts the
IHX at 0.91 where the reference TRACE region is 0.56; counting it as blockage
puts it at 0.55.

Nothing new is measured, and no new information is declared. The zone volumes
come from ``zone_model()`` — the same call the homogeniser and the cost report
make — and which circuit a zone belongs to is read from the spec's own
``materials`` block via ``_assignment()``, which already binds every zone to a
material. So a component's porosity and its homogenised number densities
describe the SAME cell, from the SAME declarations, by construction.

WHEN to compute it
──────────────────
After the resolver, NOT after the assembly:

  raw dicts                        too early. resolve() injects real geometry
                                   (the diagrid's pump-nozzle bosses and bores);
                                   measured here the component is the wrong solid.

  resolve() + auto_generate_       the moment used here. Both passes are
  topplate_holes()                 idempotent, so running them again when
                                   assemble_objects() already has costs a few
                                   milliseconds of dict work and no geometry.

  assemble_objects()               unnecessary. Placement rotates about the local
                                   origin and translates (utils.place_origin_at);
                                   porosity is a RATIO and is invariant under
                                   that. Which is exactly why every zone function
                                   works in the component's local frame.

The one pass that does matter is ``insert_into``: it is the only step that moves
material BETWEEN components (utils.insert_into cuts the insert out of the base,
then unions it in). Under it a per-spec measurement counts the insert's steel
twice — once in the base's uncut solid, once in the insert's own — so this module
refuses to measure such a spec list rather than return two wrong numbers.

UNITS: unit-agnostic, like everything else here. Volumes come out in the model's
own unit cubed; porosity is dimensionless.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from homogenise_solid import FILLER_KEY, _assignment, cylinder_volume, zone_model

# Materials that are the PRIMARY coolant. A zone bound to one of these is open to
# the primary flow; anything else — steel, or another circuit's sodium — is not.
# Override per call; this default matches materials.py.
PRIMARY_COOLANTS = ("na_primary",)

# Components the assembly-level homogeniser does not give a cylinder to
# (homogenise._TREATMENT). Their porosity is still measurable, but it is not a
# thermal-hydraulic cell — flagged in the row rather than silently reported.
_NOT_A_CELL = {
    "redan":             "smeared into the pool — has no cell of its own",
    "reactor_vessel":    "pool boundary, not a fluid cell",
    "reactor_top_plate": "modelled natively as a slab minus penetrations",
}


def prepare(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Run the two volume-changing pre-passes the CAD assembly runs, and return the
    resolved spec list. Idempotent: safe on specs assemble_objects() already saw.

    Only premades go through the resolver — same routing as assemble_objects(),
    because resolve() deep-copies and copy.deepcopy silently downcasts a live
    OCCT shape, which would break a profile-based spec's sweep path.
    """
    from assemble import auto_generate_topplate_holes
    from component_resolver import resolve
    from components_premade import PREMADE_BUILDERS

    is_premade = [d.get("obj_type") in PREMADE_BUILDERS for d in specs]
    if any(is_premade):
        resolved = iter(resolve([d for d, p in zip(specs, is_premade) if p]))
        specs = [next(resolved) if p else d for d, p in zip(specs, is_premade)]
    auto_generate_topplate_holes(specs)
    return specs


def enclosed_volume(model: Dict[str, Any]) -> Any:
    """
    The volume the component OCCUPIES — steel plus the void inside it — or None
    when the geometry does not define one. Preferred over a bounding cylinder as
    a porosity denominator, because it is intrinsic to the part.

    Two ways to get it, in order of authority:

      1. DECLARED. The zone functions already state what a component holds (the
         IHX's tube and shell sides, the diagrid's cavity), so the sum over all
         zones IS the occupied volume. Used whenever the zones say more than the
         steel does.

      2. TOPOLOGICAL. A component with a genuinely CLOSED internal cavity has
         more than one boundary shell; the outer one bounds the occupied volume.
         The above-core structure is the case in this model.

    Most components have neither. A pump barrel open at both ends, a bundle
    shell with flow windows, a cone open top and bottom — each is ONE shell, so
    its enclosed volume is just its steel and the ratio degenerates to zero.
    Their free volume is not a property of the solid at all: it is decided by
    where you cap the openings, which is precisely the judgement a bounding
    cylinder (or spec["hom_cylinder"]) makes explicit. Hence None, and the
    caller falls back to the envelope.

    CAVEAT on the topological route — it EXCLUDES THROUGH-HOLES. A bore that
    opens at both ends has its surface on the OUTER shell, so its volume is not
    inside the enclosure at all. The above-core structure's seven control-rod
    guide tubes are bored right through it: 1.83e5 of open volume, 1.1% of its
    cavity, invisible to this measure. Tolerable there, NOT tolerable on a
    perforated plate or a tube sheet, where the holes are the point. This is why
    the reported porosity is taken over the envelope and this figure is only a
    diagnostic: 1 - steel/region needs no topology and misses no hole.

    Returns ``(volume, how)`` with how in {"declared", "topological"}, or
    ``(None, None)``.
    """
    zones = model["zones"]
    v_solid = sum(z.volume for z in zones if z.role != "fluid")

    v_declared = sum(z.volume for z in zones)
    if v_declared > v_solid * (1.0 + 1e-9):
        return v_declared, "declared"

    solids = model.get("solids") or {}
    solid = next((solids[z.name] for z in zones
                  if z.role != "fluid" and z.name in solids), None)
    if solid is None:
        return None, None
    try:
        import cadquery as cq
        shells = solid.Shells()
        if len(shells) > 1:
            return max(cq.Solid.makeSolid(s).Volume() for s in shells), "topological"
    except Exception:
        pass          # topology not usable — fall back to the envelope
    return None, None


def _bind(spec: Dict[str, Any], declared: set) -> Dict[str, Any]:
    """
    zone -> material, tolerant of BOTH assignment styles the assembly accepts.

    ``_assignment()`` is the authority and is tried first, but it accepts the
    single-material ``"material"`` key only when the sole zone is the generic
    path's "solid". The vessel, top plate and redan declare a registered zone
    under another name and carry a bare ``"material"`` — homogenise.py resolves
    those through _single_material() instead, never through _assignment(). This
    reproduces that second route rather than rejecting the spec.
    """
    try:
        return _assignment(spec, declared)
    except KeyError:
        if "material" in spec and len(declared) == 1:
            out = {next(iter(declared)): spec["material"]}
            if spec.get("filler") is not None:
                out[FILLER_KEY] = spec["filler"]
            return out
        raise


def porosity_of(
    spec: Dict[str, Any],
    primary_coolants: Any = PRIMARY_COOLANTS,
) -> Dict[str, Any]:
    """
    Porosity of ONE already-resolved component dict.

    The envelope is the component's own equivalent cylinder: whatever
    ``zone_model()`` declares, overridden by ``spec["hom_cylinder"]`` exactly as
    homogenise_solid() overrides it — so the cell measured here is the cell the
    homogeniser fills with atoms.

    The envelope is generally larger than the part (a bounding cylinder over
    nozzles and domes). That slack is pool sodium, so it counts towards the
    primary volume whenever the spec's ``_filler`` is a primary coolant — which
    is the same closure rule homogenise_solid() applies to the atoms.

    Returns v_envelope / v_solid / v_primary / porosity / open_fraction, the
    per-zone breakdown, and ``note`` (empty unless the component is not a cell).
    """
    primary = set(primary_coolants)

    model = zone_model(spec)
    zones = model["zones"]

    cyl = dict(model["cylinder"])
    if spec.get("hom_cylinder"):
        cyl.update(spec["hom_cylinder"])
    v_env = cylinder_volume(cyl)

    # Only zones EXPLICITLY marked fluid are open at all — same rule the cost
    # report bills by. Anything else counts as structure.
    v_solid = sum(z.volume for z in zones if z.role != "fluid")

    if v_solid > v_env * (1.0 + 1e-6):
        raise ValueError(
            f"{spec.get('obj_id', spec.get('obj_type'))}: measured solid "
            f"({v_solid:.6g}) exceeds its equivalent cylinder ({v_env:.6g}), so "
            f"porosity would be negative. Enlarge the envelope with "
            f"spec['hom_cylinder'] — the same fix homogenise_solid() asks for."
        )

    # Which circuit each fluid zone belongs to, read from the spec's own
    # zone -> material binding. No new declaration: this is the very dict the
    # homogeniser resolves to give each zone its nuclides.
    assign = _bind(spec, {z.name for z in zones})
    filler_mat = assign.pop(FILLER_KEY, None)

    v_primary = sum(z.volume for z in zones
                    if z.role == "fluid" and assign.get(z.name) in primary)
    v_slack = max(v_env - sum(z.volume for z in zones), 0.0)
    if filler_mat in primary:
        v_primary += v_slack

    v_zoned = sum(z.volume for z in zones
                  if z.role == "fluid" and assign.get(z.name) in primary)

    # Intrinsic denominator, where the geometry defines one. Reported as a
    # DIAGNOSTIC, not as the headline: it is defined for only a minority of
    # components, it is not composable across a mesh cell, and its topological
    # route silently drops through-holes (see enclosed_volume). The headline
    # stays on the envelope so every row means the same thing.
    v_enc, how = enclosed_volume(model)
    if v_enc:
        # Declared: the primary zones ARE the primary part of the occupied
        # volume. Topological: the closed void takes the filler's material.
        v_open = v_zoned if how == "declared" else (
            (v_enc - v_solid) if filler_mat in primary else 0.0)
        por_enc = v_open / v_enc
    else:
        how, por_enc = None, None

    return {
        "obj_id":         spec.get("obj_id", spec.get("obj_type")),
        "obj_type":       spec.get("obj_type"),
        # HEADLINE: primary coolant over the equivalent cylinder. Defined for
        # every component and composable — the envelope is where this component
        # sits in the vessel, so these carve into a mesh the way homogenise.py
        # already carves them out of the pool.
        "porosity":       v_primary / v_env if v_env > 0 else 0.0,
        "v_envelope":     v_env,
        "v_solid":        v_solid,
        "v_primary":      v_primary,
        # DIAGNOSTIC: the same fraction over the component's intrinsic occupied
        # volume, where the geometry defines one. None otherwise. "basis" says
        # how it was obtained — "declared" (zone functions) or "topological"
        # (closed cavity, through-holes excluded).
        "porosity_enclosed": por_enc,
        "basis":             how,
        "v_enclosed":        v_enc,
        # Declared primary fluid only — the envelope slack left out. Lower bound,
        # and the figure that compares like-for-like with a reference region
        # whose cell bounds the component alone instead of boxing it in.
        "porosity_zones": v_zoned / v_env if v_env > 0 else 0.0,
        # Circuit-blind: everything that is not steel. Upper bound.
        "open_fraction":  max(v_env - v_solid, 0.0) / v_env if v_env > 0 else 0.0,
        # How much of the envelope is neither declared zone nor steel — i.e. how
        # loose the bounding cylinder is. Large here means the porosity is being
        # set by the envelope rather than by the geometry; tighten it with
        # spec["hom_cylinder"] and the three figures above converge.
        "slack_fraction": v_slack / v_env if v_env > 0 else 0.0,
        "zones":          {z.name: (z.role, z.volume, assign.get(z.name)) for z in zones},
        "filler":         (filler_mat, v_slack),
        "cylinder":       cyl,
        "note":           _NOT_A_CELL.get(spec.get("obj_type"), ""),
    }


def porosities(
    specs: List[Dict[str, Any]],
    primary_coolants: Any = PRIMARY_COOLANTS,
    skip: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    One porosity row per input dict, measured after the resolver.

    ``skip`` drops components by obj_id. Components carrying
    ``neutronics_treatment: "skip"`` are dropped too, matching the homogeniser.
    """
    for d in specs:
        if d.get("insert_into"):
            raise ValueError(
                f"{d.get('obj_id')}: this spec is inserted into another component. "
                f"insert_into carves the insert out of its base and unions it in, "
                f"so measuring the two separately counts the insert's steel twice "
                f"and both porosities are wrong. Measure the fused solid instead."
            )

    skip = skip or set()
    rows = []
    for spec in prepare(specs):
        if spec.get("obj_id") in skip or spec.get("neutronics_treatment") == "skip":
            continue
        rows.append(porosity_of(spec, primary_coolants))
    return rows


def print_table(rows: List[Dict[str, Any]]) -> None:
    """Human-readable summary, in the model's own volume unit."""
    print(f"\n{'component':22s} {'obj_type':21s} {'V_solid':>11s} {'V_env':>11s} "
          f"{'porosity':>9s} {'enclosed':>9s} {'basis':>12s}")
    print("─" * 100)
    for r in rows:
        enc = "        -" if r["porosity_enclosed"] is None else f"{r['porosity_enclosed']:9.3f}"
        print(f"{str(r['obj_id']):22s} {str(r['obj_type']):21s} "
              f"{r['v_solid']:11.4g} {r['v_envelope']:11.4g} "
              f"{r['porosity']:9.4f} {enc} {str(r['basis'] or '-'):>12s}"
              + (f"   ({r['note']})" if r["note"] else ""))
    print("\n  porosity = primary coolant over the equivalent cylinder. Defined for")
    print("             every component and composable into a mesh cell — use this.")
    print("  enclosed = diagnostic. Same fraction over the component's intrinsic")
    print("             occupied volume, where the geometry defines one. The")
    print("             topological basis excludes through-holes; see the module.")

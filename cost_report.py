"""
Bill of materials + cost report for a spec list.

Two ways in:

    assemble_objects(SPECS, units="m", costs_report=True)  # named after your script
    write_cost_report(SPECS, units="m")                    # same thing, standalone

Takes the very same spec list assemble_objects() / homogenise_assembly() take,
measures every material zone through the existing zone model
(component_material_zones.MATERIAL_ZONES, falling back to
homogenise.generic_zones), turns volume into MASS, and prices the mass. Two
sheets:

    "By material"   material | volume (unit3) | density (g/cm3) | mass (kg) |
                    cost per kg (CUR/kg) | total cost (CUR) | total cost (M CUR)
    "By component"  component | type | zone | material | volume (unit3) |
                    mass (kg) | cost (CUR) | cost (M CUR)

A material with no entry in COSTS is not silently dropped: its cost cells read
UNPRICED, its mass still counts towards the mass total, and the TOTAL cost is
flagged as covering the priced materials only, with the unpriced ones named in
a note under the table. A blank would have been indistinguishable from zero.

Every column header carries its unit — the volume ones stamped with whichever
``units`` you passed, the money ones with CURRENCY. Cost appears twice, in
units and in millions: reactor bills of materials run to eight and nine
figures, where the raw number is unreadable and the millions one is what ends
up in the write-up.

PRICED PER KILOGRAM, because that is how metals and fuel are actually quoted.
Density is not extra data you have to supply: it comes out of materials.py,
either read straight off a "mass_density" entry or derived from a
"number_density" one as  rho = SUM n_i * A_i * 1e24 / N_A.

UNITS: this is the one place the tool is NOT unit-agnostic. Volumes are in the
model's own length unit cubed, densities are in g/cm3, so turning one into the
other needs to know what a model unit IS — hence the required ``units``
argument, the same one assemble_objects() already takes for the STEP header.
Nothing is rescaled; the unit is used only to convert volume to mass.

WHAT THE COMPONENTS ARE MADE OF, not what they hold. Only zones the zone
functions call "solid" are billed: this is a list of parts to buy. The fluid a
component contains is skipped, and so is the coolant standing around everything
— in a pool reactor that coolant is most of the volume in the vessel and would
swamp a column meant to tell you about hardware. Costing the sodium is a
separate problem (it is a consumable inventory, not a part) and is deliberately
out of scope here.

NOTHING IN THIS MODULE KNOWS WHAT A REACTOR IS. It never asks a spec for its
obj_type. Which zones a component has, and how big each one is, is declared by
the zone functions in component_material_zones.py alongside every other
component-specific fact; a new component is a one-function change there and no
change here.

NO EQUIVALENT CYLINDERS take part. They are a neutronics construct — a
deliberately generous envelope drawn round each component — and the gap between
a component and its envelope is not a quantity anyone can buy. A spec's
"_filler" key is therefore ignored here entirely: the volume it implies to the
homogeniser is not billed.
"""

from __future__ import annotations

import datetime
import inspect
import os
import re
import warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

# The currency COSTS is denominated in. Nothing converts — this is a LABEL, so
# that no column in the report is a bare number whose unit you have to guess.
CURRENCY = "EUR"

# What a cost cell says when the material has no entry in COSTS. Deliberately a
# word and not a blank: a blank cell reads as zero to anyone summing a column.
UNPRICED = "UNPRICED"

# Currency per KILOGRAM (placeholders — replace with your own figures).
# Fuel is normally quoted per kg of HEAVY METAL, whereas the mass computed here
# is the whole compound (core_smear is ~88 % heavy metal, the rest oxygen), so
# scale a kgHM price up by that fraction before putting it here.
# No coolant entry: fluids are never billed, so a price for one would be dead.
COSTS: Dict[str, float] = {
    "ss316":            8.0,
    "ss304":            5.0,
    "core_smear":  10_000.0,
}

# Centimetres per model length unit — the only unit knowledge in this module,
# used solely to turn a model volume into grams via a g/cm3 density. Keys match
# assemble._STEP_UNITS so a spec's `units=` means the same thing in both.
_CM_PER_UNIT: Dict[str, float] = {
    "m": 100.0, "mm": 0.1, "cm": 1.0, "um": 1e-4, "km": 1e5,
    "inch": 2.54, "ft": 30.48,
}


def material_density(mat: Dict[str, Any]) -> float:
    """
    Mass density in g/cm3, from either form the material library uses.

    "mass_density" entries state it outright. "number_density" entries give
    atoms/b.cm per nuclide, which converts as

        rho = SUM_i  n_i * 1e24 [atoms/cm3 per atom/b.cm]  *  A_i / N_A

    with A_i, the mass number, read off the nuclide's own name (Fe56 -> 56).
    A is the molar mass to within the mass defect (~0.1 %), which is orders of
    magnitude finer than any price list — and it saves the library from having
    to carry molar masses it does not otherwise need.
    """
    from homogenise import N_A

    if mat.get("kind", "number_density") == "mass_density":
        return float(mat["density"])

    total = 0.0
    for nuc, n in mat["nuclides"].items():
        a = re.search(r"(\d+)", nuc)
        if a is None:
            raise ValueError(
                f"cannot read a mass number off nuclide name {nuc!r}, so its "
                f"density cannot be derived — give this material as "
                f"'mass_density' instead."
            )
        total += float(n) * float(a.group(1))
    return total * 1e24 / N_A


def caller_report_path(skip: Sequence[str] = ()) -> str:
    """
    Auto-name a report after the SCRIPT THAT ASKED FOR IT::

        <dir of that script>/costs_reports/<stem>_costs_reports_<YYYYmmdd_HHMMSS>.xlsx

    The stack is walked outwards past this module (and past anything named in
    ``skip`` — assemble.py passes its own ``__file__``) to find the first frame
    that belongs to user code; that frame's file gives both the stem and the
    directory. Anchoring to the script's own directory rather than the cwd means
    the report lands in the same place whether the example is run from the
    project root or from examples_reactor/.
    """
    ignore = {os.path.abspath(f) for f in (__file__, *skip)}
    frame = next((f for f in inspect.stack()[1:]
                  if os.path.abspath(f.filename) not in ignore), None)
    src = frame.filename if frame is not None else ""
    if os.path.isfile(src):                      # a real script
        stem = os.path.splitext(os.path.basename(src))[0]
        root = os.path.dirname(os.path.abspath(src))
    else:                                        # REPL / notebook / exec()
        stem, root = "assembly", os.getcwd()
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(root, "costs_reports", f"{stem}_costs_reports_{ts}.xlsx")


def _zone_materials(spec: Dict[str, Any], declared: set) -> Dict[str, str]:
    """{zone: material} — both spellings accepted.

        "materials": {"structure": "ss316", "_filler": "na_primary"}   # multi-zone
        "material": "ss316"                                            # single zone

    The filler is dropped rather than returned: it is not a zone, it has no CAD
    volume of its own, and what it stands for — the slop between a component and
    its equivalent cylinder — is a neutronics construct nobody buys.

    Deliberately looser than homogenise._assignment: a one-zone component may
    use the single-material key whatever its zone is CALLED ("structure",
    "core", ...), because pricing does not care about the zone-name contract
    the homogeniser enforces.
    """
    from homogenise import FILLER_KEY

    if "materials" in spec:
        assign = dict(spec["materials"])
        assign.pop(FILLER_KEY, None)
        return assign
    if "material" in spec:
        if len(declared) != 1:
            raise KeyError(
                f"{spec.get('obj_id', spec.get('obj_type'))}: declares zones "
                f"{sorted(declared)}, so it needs a 'materials' block; the single "
                f"'material' key is only valid for one-zone components."
            )
        return {next(iter(declared)): spec["material"]}
    raise KeyError(
        f"{spec.get('obj_id', spec.get('obj_type'))}: no material assignment. "
        f"Give 'material' (single-material component) or 'materials' (zone -> material)."
    )


def material_volumes(
    specs: List[Dict[str, Any]],
) -> List[Tuple[str, str, str, str, float]]:
    """
    [(obj_id, obj_type, zone, material, volume), ...] — one row per SOLID zone.

    Zones the zone functions marked role "fluid" (an IHX's tube and shell sides,
    a diagrid's cavity) are what the components CONTAIN, not what they are made
    of, and a bill of materials is a list of parts to buy — so they are left
    out, along with the pool coolant standing around everything.

    Only zones EXPLICITLY marked "fluid" are dropped. A zone with any other role
    is billed, because silently omitting something from a bill of materials is
    worse than listing something you did not want.

    NOTHING IS EVER MEASURED OFF AN UNRESOLVED SPEC. resolve() and
    auto_generate_topplate_holes() run here unconditionally, even when the
    caller has already run them (assemble_objects has), because both are
    idempotent — they assign through setdefault, and the hole pass re-reads its
    own previous output as user holes and adds nothing. Running them twice
    costs a few milliseconds of dict work and no geometry; NOT running them
    once silently prices a component at its pre-resolver dimensions, which is
    the sort of error a bill of materials cannot afford to make quietly.

    That, plus every zone function building through the assembly's own builder,
    is what guarantees the resolver's injected parameters — the diagrid's pump
    nozzle bosses and bores, the top plate's auto-holes, resolved placement —
    are in the measured volumes rather than missing from them.

    NOTE this rebuilds each component (zone functions measure their own solids),
    so a report costs roughly one extra assembly build.
    """
    from homogenise import zone_model
    from component_resolver import resolve
    from components_premade import PREMADE_BUILDERS
    from assemble import auto_generate_topplate_holes

    # Only premades go through the resolver — same routing as assemble_objects
    # (resolve() deep-copies, which would downcast live OCCT shapes in
    # profile-based specs). The copy also keeps this pass from writing resolved
    # keys back into the caller's own dicts.
    is_premade = [d.get("obj_type") in PREMADE_BUILDERS for d in specs]
    if any(is_premade):
        resolved = iter(resolve([d for d, p in zip(specs, is_premade) if p]))
        specs = [next(resolved) if p else d for d, p in zip(specs, is_premade)]
    # Without this the top plate is measured as an unperforated slab and its
    # steel is over-counted by the penetrations.
    auto_generate_topplate_holes(specs)

    rows: List[Tuple[str, str, str, str, float]] = []
    for spec in specs:
        name = spec.get("obj_id", spec.get("obj_type"))
        zones = zone_model(spec)["zones"]
        assign = _zone_materials(spec, {z.name for z in zones})
        for z in zones:
            # The material assignment is checked for EVERY zone, billed or not,
            # so that a spec list which is complete for the homogeniser cannot
            # be quietly half-checked here.
            if z.name not in assign:
                raise KeyError(
                    f"{name}: zone {z.name!r} has no material assigned. "
                    f"Assigned: {sorted(assign)}."
                )
            if z.role == "fluid":
                continue                  # what it holds, not what it is made of
            rows.append((spec.get("obj_id", "?"), spec.get("obj_type", "?"),
                         z.name, assign[z.name], z.volume))
    return rows


def write_cost_report(
    specs: List[Dict[str, Any]],
    units: str,
    costs: Optional[Dict[str, float]] = None,
    materials: Optional[Dict[str, Dict[str, Any]]] = None,
    currency: str = CURRENCY,
    out_path: Optional[str] = None,
) -> str:
    """
    Write the two-sheet .xlsx described in the module docstring; return its path.

    Takes RAW or already-resolved specs indifferently: material_volumes() runs
    the resolver either way, so the report always measures final dimensions.

    units    : what one model length unit IS ("m", "mm", "cm", ...). Required —
               mass, and therefore cost, cannot be had without it.
    costs    : material -> currency per kilogram. Defaults to COSTS above.
    materials: composition library the densities come from; defaults to
               materials.MATERIALS.
    currency : label for the cost columns' headers. Purely cosmetic — no
               conversion is done, so it must match whatever COSTS is in.
    out_path : defaults to caller_report_path() — named after the script that
               called in, timestamped, under that script's costs_reports/.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font

    unit_key = str(units).lower()
    if unit_key not in _CM_PER_UNIT:
        raise ValueError(
            f"cost report: unknown units {units!r}. Accepted: "
            + ", ".join(sorted(_CM_PER_UNIT)) + "."
        )
    # model volume -> kilograms: (cm/unit)³ cm³ per unit³, g/cm³, then g -> kg
    kg_per_unit3 = _CM_PER_UNIT[unit_key] ** 3 / 1000.0

    if materials is None:
        from materials import MATERIALS as materials
    if out_path is None:
        out_path = caller_report_path()
    costs = COSTS if costs is None else costs
    rows = material_volumes(specs)

    used = sorted({m for *_, m, _ in rows})
    missing = [m for m in used if m not in materials]
    if missing:
        raise KeyError(
            f"material(s) {missing} are used by the geometry but absent from the "
            f"material library, so their density is unknown."
        )
    unpriced = [m for m in used if m not in costs]
    if unpriced:
        warnings.warn(f"no price given for material(s): {', '.join(unpriced)} — "
                      f"their cost cells read {UNPRICED} and they are excluded "
                      f"from the TOTAL", stacklevel=2)

    density = {m: material_density(materials[m]) for m in used}   # g/cm³

    def mass_of(mat: str, vol: float) -> float:                   # kg
        return vol * kg_per_unit3 * density[mat]

    def cost_of(mat: str, vol: float) -> Optional[float]:
        return None if mat not in costs else costs[mat] * mass_of(mat, vol)

    # None means "no price on file", which in a spreadsheet must not be written
    # as a blank — a blank reads as zero and quietly shrinks the bill.
    def cost_cell(cost: Optional[float]):
        return UNPRICED if cost is None else cost

    def millions(cost: Optional[float]):
        return UNPRICED if cost is None else cost / 1e6

    wb = Workbook()

    # ── Sheet 1: totals per material ───────────────────────────────────────
    ws = wb.active
    ws.title = "By material"                                                        #type: ignore
    ws.append(["Material", f"Total volume ({unit_key}³)", "Density (g/cm³)",        #type: ignore
               "Total mass (kg)", f"Cost per kg ({currency}/kg)",
               f"Total cost ({currency})", f"Total cost (M {currency})"])
    totals: Dict[str, float] = defaultdict(float)
    for *_, mat, vol in rows:
        totals[mat] += vol
    for mat in sorted(totals):
        cost = cost_of(mat, totals[mat])
        ws.append([mat, totals[mat], density[mat], mass_of(mat, totals[mat]),       #type: ignore
                   cost_cell(costs.get(mat)), cost_cell(cost), millions(cost)])
    # Priced materials only — an unpriced one contributes no cost, and saying so
    # in the label is what keeps the number from being read as the whole bill.
    # The mass total, by contrast, covers everything: mass is never unknown.
    grand_total = sum(c for c in (cost_of(m, v) for m, v in totals.items())
                      if c is not None)
    ws.append([f"TOTAL (excl. {UNPRICED})" if unpriced else "TOTAL",                #type: ignore
               sum(totals.values()), None,
               sum(mass_of(m, v) for m, v in totals.items()), None,
               grand_total, millions(grand_total)])
    if unpriced:
        ws.append([])                                                               #type: ignore
        ws.append([f"{UNPRICED} — no entry in COSTS, excluded from TOTAL: "         #type: ignore
                   + ", ".join(unpriced)])
    # What this sheet COVERS, stated on the sheet. A reader who opens the file
    # cold cannot otherwise tell whether a missing coolant line means the model
    # has none or means the report left it out.
    ws.append([])                                                                   #type: ignore
    ws.append(["Scope: what the components are made of. Fluid zones and "           #type: ignore
               "coolant are NOT included."])

    # ── Sheet 2: one row per component zone ────────────────────────────────
    ws2 = wb.create_sheet("By component")
    ws2.append(["Component", "Type", "Zone", "Material",
                f"Volume ({unit_key}³)", "Mass (kg)", f"Cost ({currency})",
                f"Cost (M {currency})"])
    for obj_id, obj_type, zone, mat, vol in rows:
        cost = cost_of(mat, vol)
        ws2.append([obj_id, obj_type, zone, mat, vol,
                    mass_of(mat, vol), cost_cell(cost), millions(cost)])

    for sheet in (ws, ws2):
        for header in sheet[1]:                                                         #type: ignore
            header.font = Font(bold=True)
        for col in sheet.columns:                                                       #type: ignore
            width = max(len(str(c.value if c.value is not None else "")) for c in col)
            # Capped: the UNPRICED footnote is one long cell in column A and
            # would otherwise stretch the material column across the screen.
            sheet.column_dimensions[col[0].column_letter].width = min(width + 3, 40)    #type: ignore

    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    wb.save(out_path)
    print(f"Cost report written to: {out_path}")
    return out_path


if __name__ == "__main__":
    # Self-test (pure python — no CadQuery), in the style of homogenise.py.
    # Turning volume into mass is the only new physics in this module, so that
    # is what is checked; the report itself is exercised by running any example
    # with assemble_objects(..., costs_report=True).
    from materials import MATERIALS

    for name, expect in (("ss316", 7.83), ("ss304", 7.72),
                         ("core_smear", 10.48), ("na_primary", 0.83)):
        rho = material_density(MATERIALS[name])
        print(f"  {name:14s} {rho:6.3f} g/cm³")
        assert abs(rho - expect) < 0.01, name

    # A cubic metre of steel must weigh exactly what the 1e9 cubic millimetres
    # describing the very same block weigh — the length unit has to cancel.
    rho = material_density(MATERIALS["ss316"])
    kg = lambda v, u: v * _CM_PER_UNIT[u] ** 3 / 1000.0 * rho
    print(f"\n1 m³ = {kg(1.0, 'm'):,.1f} kg    1e9 mm³ = {kg(1e9, 'mm'):,.1f} kg")
    assert abs(kg(1.0, "m") - kg(1e9, "mm")) < 1e-6 * kg(1.0, "m")
    print("ok")

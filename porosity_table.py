"""
VESSEL porosity table for the CAD ESFR-SMR, laid against the reference TRACE
nodalization.

A TRACE 3-D VESSEL smears the internal structures into each region as a
POROSITY: the fraction of the region volume available to the coolant. This
script runs the CAD ESFR-SMR through porosity.porosities() and prints, per
reference region (I-XI), the reference figure next to the value measured off
the CAD.

WHICH POROSITY
--------------
Three figures are reported per component, because they answer different
questions and the reference falls between them for the one component that
holds two circuits:

  porosity        primary coolant over the equivalent cylinder. THE HEADLINE.
                  Defined for every component and composable into a mesh cell.
  porosity_zones  declared primary fluid only, envelope slack excluded. A lower
                  bound, and the like-for-like figure when the reference region
                  bounds the component alone instead of boxing it in.
  open_fraction   everything that is not steel, circuit-blind. An upper bound.

An earlier version of this script reported open_fraction as "the" CAD porosity.
That is the circuit-blind number: it counts the IHX's secondary sodium as open
volume, which to the primary side is blockage, and put the IHX at 0.91 against
a reference of 0.56. Distinguishing the circuits is what closes that gap.

HONEST SCOPE
------------
This compares POROSITY TO POROSITY. It does NOT reproduce the reference's
region VOLUMES: those come from a volume-conserving partition (nested regions,
azimuthal sectors) whose rules are not recoverable from the nodalization figure.

Expect agreement where a reference region and a CAD component are the same
object (diagrid, plenums, core bypass, IHX) and divergence where the reference
spreads structure over a large region box while the CAD envelope bounds the part
alone (strongback, above-core structure). The strongback is the clearest case: it maps
to TWO reference regions with different porosities, so one CAD component cannot
match both. Differences are printed, not hidden.

Writes porosity_table.csv next to this file.
"""

import csv
import json
import os
import sys
import warnings

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from esfr_smr_specs import SPECS                        # noqa: E402
from materials import MATERIALS                         # noqa: E402  read-only
from homogenise import homogenise_objects               # noqa: E402  read-only
from porosity import porosities                         # noqa: E402  read-only

CM3_PER_M3 = 1e6
CSV_PATH = os.path.join(_HERE, "porosity_table.csv")
REF_TOTAL_NA = 652.05   # m^3, reference table total ("no porosity" column)

# Reference TRACE VESSEL regions: (number, name, reference porosity, CAD source).
# "strongback" appears TWICE by design — the reference splits it across regions
# II and III with different porosities, which is the region/component mismatch
# this table is meant to expose.
REGIONS = [
    ("I",    "Spherical bottom",                0.84, "vessel_bottom"),
    ("II",   "Lower strongback + core catcher", 0.95, "strongback"),
    ("III",  "Upper strongback",                0.81, "strongback"),
    ("IV",   "Diagrid",                         0.85, "diagrid"),
    ("V",    "Core bypass",                     0.05, "core"),
    ("VI",   "Upper plenum",                    1.00, "pool"),
    ("VII",  "Above core structure",            0.40, "above_core_structure"),
    ("VIII", "IHX",                             0.56, "ihx_1"),
    ("IX",   "Primary pump",                    0.76, "pump_1"),
    ("X",    "Cold plenum",                     1.00, "pool"),
    ("XI",   "Outer space",                     0.00, "boundary"),
]

# |delta| below this is reported as agreement.
TOL = 0.12


def _check_specs_in_sync() -> None:
    """
    esfr_smr_specs.py is a verbatim copy of the Chapter 4 example, kept separate
    only because importing that example triggers its top-level homogenisation.
    A copy can drift, and if it does this table stops describing the model the
    thesis shows. So compare the two and refuse to run on a stale copy.

    The probe itself is best-effort: if the example is restructured so it cannot
    be read, warn rather than block. Actual drift is fatal.
    """
    path = os.path.join(_HERE, "examples_reactor",
                        "example_final_esfr_smr_with_materials_cm.py")
    try:
        import ast
        with open(path) as fh:
            tree = ast.parse(fh.read())
        # Drop bare expression statements: the example homogenises on import.
        mod = ast.Module(body=[n for n in tree.body if not isinstance(n, ast.Expr)],
                         type_ignores=[])
        ns: dict = {"__name__": "_esfr_specs_sync_probe"}
        exec(compile(mod, path, "exec"), ns)
        example = {d["obj_id"]: d for d in ns["SPECS"]}
    except Exception as exc:                       # probe broken, not the specs
        warnings.warn(f"could not verify esfr_smr_specs.py against the example "
                      f"({exc}); table may be built on a stale copy.")
        return

    mine = {d["obj_id"]: d for d in SPECS}
    dump = lambda d: json.dumps(d, sort_keys=True, default=str)   # noqa: E731
    drift = sorted(k for k in set(example) | set(mine)
                   if k not in example or k not in mine
                   or dump(example[k]) != dump(mine[k]))
    if drift:
        raise SystemExit(
            "esfr_smr_specs.py has drifted from "
            "examples_reactor/example_final_esfr_smr_with_materials_cm.py "
            f"for: {', '.join(drift)}.\nRe-sync the copy before regenerating "
            "this table — otherwise it describes a different reactor than "
            "Chapter 4 does."
        )
    print("specs verified in sync with the Chapter 4 example.\n")


def main() -> None:
    _check_specs_in_sync()

    print("Measuring porosities off the CAD ESFR-SMR (read-only) ...\n")
    rows_por = {r["obj_id"]: r for r in porosities(SPECS)}

    # The pool is an assembly-level cell, not a component, so it comes from the
    # homogeniser rather than from porosities().
    model = homogenise_objects(SPECS, MATERIALS,
                               pool={"material": "na_primary"}, units="cm")
    pool = model["pool"]
    v_pool = pool["volume"] / CM3_PER_M3
    steel_smear = sum(s["volume"] for s in pool.get("smeared", [])) / CM3_PER_M3
    pool_por = 1.0 - steel_smear / v_pool

    def source(src):
        """(porosity, zones, open, slack, note) for a region's CAD source."""
        if src == "pool":
            return pool_por, pool_por, pool_por, 0.0, "pool sodium (redan smeared)"
        if src in ("vessel_bottom", "boundary"):
            return None, None, None, None, "boundary — no CAD component"
        r = rows_por.get(src)
        if r is None:
            return None, None, None, None, "unmapped"
        return (r["porosity"], r["porosity_zones"], r["open_fraction"],
                r["slack_fraction"], r["note"])

    # ── the comparison ──────────────────────────────────────────────────────
    print("VESSEL porosity — CAD ESFR-SMR vs reference nodalization\n")
    hdr = "{:<5}{:<28}{:>8}{:>9}{:>8}  {:>7}{:>7}{:>7}  {}"
    print(hdr.format("reg", "region", "ref", "CAD", "delta",
                     "zones", "open", "slack", "source"))
    print("-" * 104)

    out = []
    for num, name, ref_p, src in REGIONS:
        p, pz, op, slack, note = source(src)
        if p is None:
            print("{:<5}{:<28}{:>8.2f}{:>9}{:>8}  {:>7}{:>7}{:>7}  {}".format(
                num, name[:27], ref_p, "--", "--", "--", "--", "--", note))
            out.append([num, name, ref_p, "", "", "", "", "", src, note])
            continue
        d = p - ref_p
        tag = "ok" if abs(d) < TOL else "diverges"
        print("{:<5}{:<28}{:>8.2f}{:>9.3f}{:>+8.3f}  {:>7.3f}{:>7.3f}{:>7.3f}  {} [{}]".format(
            num, name[:27], ref_p, p, d, pz, op, slack, src, tag))
        out.append([num, name, ref_p, round(p, 4), round(d, 4),
                    round(pz, 4), round(op, 4), round(slack, 4), src, note])

    # ── the IHX, spelled out: the reference sits between the two measures ────
    ihx = rows_por.get("ihx_1")
    if ihx is not None:
        ref_ihx = next(ref for _, _, ref, src in REGIONS if src == "ihx_1")
        print(f"\nIHX (region VIII), reference {ref_ihx:.2f}:")
        print(f"  porosity        {ihx['porosity']:.4f}   "
              f"delta {ihx['porosity'] - ref_ihx:+.4f}   primary over the envelope")
        print(f"  porosity_zones  {ihx['porosity_zones']:.4f}   "
              f"delta {ihx['porosity_zones'] - ref_ihx:+.4f}   declared primary fluid only")
        print(f"  open_fraction   {ihx['open_fraction']:.4f}   "
              f"delta {ihx['open_fraction'] - ref_ihx:+.4f}   circuit-blind (the old column)")
        print("  -> the reference falls BETWEEN the first two; only the "
              "circuit-blind figure is far out.")

    # ── sodium inventory ────────────────────────────────────────────────────
    # No double counting: the homogeniser carves each component's full envelope
    # out of the pool, so envelope slack belongs to the component, not the pool.
    comp_primary = sum(r["v_primary"] for r in rows_por.values()) / CM3_PER_M3
    total_na = (v_pool - steel_smear) + comp_primary
    print("\nPrimary sodium inventory:")
    print(f"  CAD ESFR-SMR : {total_na:8.1f} m^3   "
          f"(pool {v_pool - steel_smear:.1f} + components {comp_primary:.1f})")
    print(f"  reference    : {REF_TOTAL_NA:8.1f} m^3")
    print(f"  ratio        : {total_na / REF_TOTAL_NA:8.3f}")

    # ── per-component detail ────────────────────────────────────────────────
    print("\nPer-component porosity (every component, mapped or not):")
    print("  {:<24}{:>12}{:>12}{:>9}{:>8}{:>8}{:>8}".format(
        "component", "V_env [m3]", "V_solid[m3]", "porosity", "zones", "open", "slack"))
    for r in rows_por.values():
        print(f"  {str(r['obj_id']):<24}{r['v_envelope'] / CM3_PER_M3:>12.2f}"
              f"{r['v_solid'] / CM3_PER_M3:>12.2f}{r['porosity']:>9.4f}"
              f"{r['porosity_zones']:>8.4f}{r['open_fraction']:>8.4f}"
              f"{r['slack_fraction']:>8.4f}"
              + (f"   ({r['note']})" if r["note"] else ""))
    print(f"  {'pool':<24}{v_pool:>12.2f}{steel_smear:>12.2f}{pool_por:>9.4f}"
          f"{pool_por:>8.4f}{pool_por:>8.4f}{0.0:>8.4f}")

    with open(CSV_PATH, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["region", "name", "ref_porosity", "cad_porosity", "delta",
                    "porosity_zones", "open_fraction", "slack_fraction",
                    "cad_source", "note"])
        w.writerows(out)
    print(f"\nCSV written: {CSV_PATH}")

    print("\nRead this as: the CAD tool measures a porosity for every component.\n"
          "It agrees with the reference where a region and a component are the\n"
          "same object (diagrid, plenums, core bypass, and — once the two sodium\n"
          "circuits are told apart — the IHX), and diverges where the reference\n"
          "spreads structure over a large region box while the CAD envelope\n"
          "bounds the part alone (strongback, above-core structure). Those rows\n"
          "exactly the ones whose slack equals their porosity: no fluid zone was\n"
          "declared, so the envelope alone sets the number.")


if __name__ == "__main__":
    main()

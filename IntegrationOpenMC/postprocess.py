"""
postprocess.py
==============
Extract the IHX Na-23 (n,gamma) reaction rates from the Step-2 statepoint,
convert to secondary-loop (tube-side) Na-24 production, and normalise per unit
core power.

The IHXs are modelled with a single blended sodium (primary + secondary
indistinguishable in transport), so the tally scores TOTAL Na-23 capture in
each IHX; multiplying by the secondary/(primary+secondary) volume fraction
gives the secondary-loop share that drives secondary Na-24 activity.

Usage:
    python postprocess.py homogenised_model_cm20260725_194805.json
"""

import re
import sys
import glob

import openmc

import build_model


def latest_statepoint(pattern):
    """Newest statepoint by BATCH NUMBER (avoids the lexicographic trap where
    'statepoint.5.h5' sorts after 'statepoint.30.h5')."""
    paths = glob.glob(pattern, recursive=True)
    if not paths:
        raise FileNotFoundError(pattern)
    return max(paths, key=lambda p: int(re.search(r'statepoint\.(\d+)\.h5', p).group(1)))

CORE_POWER_W = 360.0e6   # W (ESFR-SMR core thermal power)


def main(json_path):
    b = build_model.build(json_path)
    sec = b['sec_frac']

    sp_path = latest_statepoint('step2/**/statepoint.*.h5')
    print(f"Reading {sp_path}")
    with openmc.StatePoint(sp_path) as sp:
        print(f"\nSecondary Na fraction per IHX: {sec:.4f}\n")
        print(f"{'IHX':<10}{'Na23 (n,g) [/src]':>24}{'secondary share':>20}")
        for name in b['ihx_names']:
            t = sp.get_tally(name=f'{name}_na23_ngamma')
            val = float(t.mean.ravel()[0])
            unc = float(t.std_dev.ravel()[0])
            print(f"{name:<10}{val:>15.6e} +/- {unc:>7.1e}"
                  f"{val * sec:>20.6e}")

        tot = sp.get_tally(name='total_na23_ngamma')
        print(f"\nsanity: total Na23 (n,gamma) = "
              f"{float(tot.mean.ravel()[0]):.6e} (must be > 0)")

    print("\nNote: values are per source neutron. Multiply by the core source "
          "rate S = P / (w_fission) to get absolute reactions/s, then by the "
          "Na-24 decay constant for an equilibrium activity (Bq).")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f'usage: python {sys.argv[0]} <homogenised_model_cm*.json>')
    main(sys.argv[1])

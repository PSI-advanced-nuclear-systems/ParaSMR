"""
step1_eigenvalue.py
===================
Step 1 of the IHX activation calculation: a k-eigenvalue run of the combined
core+pool model whose sole purpose is to produce a CONVERGED FISSION SOURCE for
the Step-2 fixed-source MAGIC run (step2_magic.py).

Writes materials.xml / geometry.xml / tallies.xml (shared with Step 2) and the
converged source statepoint into step1/.

Usage:
    python step1_eigenvalue.py homogenised_model_cm20260725_194805.json
"""

import os
import sys
import glob
import math

import openmc

import build_model


def run_step1(json_path, batches=100, inactive=50, particles=2_000_000,
              threads=None):
    b = build_model.build(json_path)

    # shared XML (Step 2 reuses these verbatim)
    b['materials'].export_to_xml()
    b['geometry'].export_to_xml()
    b['tallies'].export_to_xml()

    os.makedirs('step1', exist_ok=True)

    z0, z1 = b['core_active_z']            # shifted active-fuel z-range
    src = openmc.IndependentSource()
    src.space = openmc.stats.Box((-190.0, -190.0, z0), (190.0, 190.0, z1))
    src.constraints = {'fissionable': True}
    src.energy = openmc.stats.Watt(a=988.0e3, b=2.249e-6)   # fast fission (eV)

    # Shannon entropy over the active core: the deliverable here is the
    # converged fission SOURCE, so the source shape - not k_eff, which can look
    # settled while the distribution is still drifting - is what must be shown
    # to have converged before the inactive batches end.
    ent = openmc.RegularMesh()
    ent.lower_left = (-190.0, -190.0, z0)
    ent.upper_right = (190.0, 190.0, z1)
    ent.dimension = (10, 10, 10)

    s = openmc.Settings()
    s.run_mode = 'eigenvalue'
    s.batches = batches
    s.inactive = inactive
    s.particles = particles
    s.source = [src]
    s.entropy_mesh = ent
    s.temperature = {'method': 'interpolation', 'default': 900.0,
                     'tolerance': 700.0, 'range': (250.0, 1600.0)}
    s.output = {'path': 'step1/'}
    s.export_to_xml()

    openmc.run(threads=threads, output=True)

    sp = sorted(glob.glob('step1/statepoint.*.h5'))[-1]
    print(f"Step 1 complete - source statepoint: {sp}")
    return sp


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f'usage: python {sys.argv[0]} <homogenised_model_cm*.json>')
    _threads = int(os.environ.get('OMP_NUM_THREADS', 0)) or None
    # cheap shakedown override: ESFR_PARTICLES / ESFR_BATCHES / ESFR_INACTIVE
    run_step1(
        sys.argv[1],
        batches=int(os.environ.get('ESFR_BATCHES', 100)),
        inactive=int(os.environ.get('ESFR_INACTIVE', 50)),
        particles=int(os.environ.get('ESFR_PARTICLES', 2_000_000)),
        threads=_threads,
    )

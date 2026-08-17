"""
step2_magic.py
==============
Step 2 of the IHX activation calculation: a FIXED-SOURCE run seeded by Step 1's
converged fission source, generating mesh-based weight windows via OpenMC's
MAGIC method so that neutrons reach the IHXs in the pool, and scoring the
Na-23 (n,gamma) activation tally there.

Reuses the materials.xml / geometry.xml / tallies.xml written by Step 1, so the
geometry and tallies are guaranteed identical. Runs inside step2/ so it does
not clobber Step 1's files.

Usage (after step1_eigenvalue.py has run):
    python step2_magic.py homogenised_model_cm20260725_194805.json
"""

import os
import re
import sys
import glob
import shutil

import numpy as np
import openmc

import build_model


def latest_statepoint(pattern):
    """Newest statepoint by BATCH NUMBER (not lexicographic filename order,
    which would rank 'statepoint.5.h5' after 'statepoint.100.h5')."""
    paths = glob.glob(pattern, recursive=True)
    if not paths:
        raise FileNotFoundError(pattern)
    return max(paths, key=lambda p: int(re.search(r'statepoint\.(\d+)\.h5', p).group(1)))


def run_step2(json_path, batches=30, particles=1_000_000, dr_ww=20.0,
              num_axial_div=6, threads=None):
    b = build_model.build(json_path)
    r_max, z_bot, z_top = b['ihx_extent']

    sp_s1 = os.path.abspath(latest_statepoint('step1/statepoint.*.h5'))
    shared = [os.path.abspath(f) for f in
              ('materials.xml', 'geometry.xml', 'tallies.xml')]

    # cylindrical MAGIC mesh: core axis origin, single azimuthal bin, reaching
    # past the IHX outer edge (r_max) and spanning the IHX height.
    mesh = openmc.CylindricalMesh(
        r_grid=np.arange(0.0, r_max + dr_ww, dr_ww),
        z_grid=np.linspace(z_bot, z_top, num_axial_div + 1),
        origin=(0.0, 0.0, 0.0),
        name='ww_mesh',
    )
    wwg = openmc.WeightWindowGenerator(mesh=mesh, particle_type='neutron',
                                       method='magic', update_interval=1)

    s = openmc.Settings()
    s.run_mode = 'fixed source'
    s.batches = batches
    s.inactive = 0
    s.particles = particles
    # The core is supercritical in the reflecting pool (k~1.08). Treat fission
    # as pure absorption so the neutron bank cannot multiply without bound: the
    # Step-1 eigenvalue source already encodes the full steady-state fission
    # source, so Step 2 only transports it outward to the IHXs (re-multiplying
    # would double-count the multiplication already baked into the source).
    s.create_fission_neutrons = False
    s.source = [openmc.FileSource(path=sp_s1)]
    s.weight_window_generators = [wwg]
    s.temperature = {'method': 'interpolation', 'default': 900.0,
                     'tolerance': 700.0, 'range': (250.0, 1600.0)}

    run_dir = os.path.join('step2', f'dr_{dr_ww}_nax_{num_axial_div}')
    os.makedirs(run_dir, exist_ok=True)
    orig = os.getcwd()
    try:
        os.chdir(run_dir)
        for f in shared:
            shutil.copy(f, '.')
        s.export_to_xml()
        openmc.run(threads=threads, output=True)
    finally:
        os.chdir(orig)

    print(f"Step 2 complete (run_dir={run_dir})")
    print(f"  weight windows -> {os.path.join(run_dir, 'weight_windows.h5')}")
    return run_dir


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f'usage: python {sys.argv[0]} <homogenised_model_cm*.json>')
    _threads = int(os.environ.get('OMP_NUM_THREADS', 0)) or None
    run_step2(
        sys.argv[1],
        batches=int(os.environ.get('ESFR_BATCHES', 30)),
        particles=int(os.environ.get('ESFR_PARTICLES', 1_000_000)),
        threads=_threads,
    )

# OpenMC integration

Two-step MAGIC sodium-activation calculation for the IHXs of a pool-type SFR,
driven by the homogenised JSON model that `homogenise_objects()` writes.

```
python3 step1_eigenvalue.py <model.json>   # converged fission source
python3 step2_magic.py      <model.json>   # transport to the IHXs + tally
python3 postprocess.py      <model.json>   # results table
```

`build_model.py <model.json>` builds the geometry alone and writes two
material plots, which is worth doing before submitting a long run.

## Missing dependency

`main_no_ihx_serpent_2.py` is **not** included in this repository. It is a
translation of a Serpent input for the detailed ESFR-SMR core and is not
cleared for public release. Every script here imports it through
`build_model.py`, so the calculation cannot be run from a clean clone.

To use this directory you need to supply that module yourself. It must expose:

| Name | Meaning |
|---|---|
| `build_core(outer_fill, bound_r)` | returns `(universe, materials)` for the detailed core |
| `Z_CORE_LO`, `Z_CORE_HI` | axial extent of the core in its own frame |
| `Z_FEB`, `Z_UGP` | active-fuel bottom and top, used for the source box |

Any core model satisfying that interface will work; nothing else in the
directory depends on the ESFR-SMR core specifically.

## Requirements

- OpenMC 0.15.2, with the `openmc` executable on the path
- A cross-section library, located via `OPENMC_CROSS_SECTIONS`
  (JEFF-3.3 in HDF5 was used here, matching the library the core model was
  validated against)

# ParaSMR

Parametric 3D CAD library for pool-type liquid-metal-cooled fast small modular reactors, developed as part of an MSc thesis at ETH Zürich – EPF Lausanne by Pilar Suárez Gerona, carried out at the Laboratory for Simulation and Modelling (PSI) in collaboration with 92 Research – Nuclear Analysis.

Built on [CadQuery](https://cadquery.readthedocs.io/), ParaSMR describes reactor geometry as plain Python dictionaries: each component is given its main geometric parameters, and the tool turns those numbers into a positioned, validated 3D assembly. Change a parameter and the model is rebuilt rather than redrawn.

The same dictionaries also feed the physics codes. One description produces three outputs:

| Entry point | Module | Output |
|---|---|---|
| `assemble_objects()` | `assemble.py` | heterogeneous CAD assembly + STEP file |
| `homogenise_objects()` | `homogenise.py` | atom-conserving equivalent cylinders, as JSON, for Monte Carlo codes |
| `porosities()` | `porosity.py` | per-component porosities for system codes such as TRACE |

All three take the same list of dictionaries and run the same resolver, so a component occupies the same position in all three.

---

## Project structure

Modules are grouped by the architectural layer they implement. Layers 1–3 build one object, layer 4 assembles many, and layer 5 exports the same description to the physics codes.

```
ParaSMR/
├── assemble.py                            # L4  Orchestrator: build, validate, export
├── component_resolver.py                  # L4  Placement from connection rules
├── component_anchors.py                   # L4  Analytical connection points
│
├── build_3D_solid.py                      # L2  Solid builder dispatcher
├── components_3D_primitives.py            # L2  box, cylinder, sphere, wedge, pipe, ...
├── utils.py                               # L2  Operations, transforms, export
├── profile_built_in_2D_sketch.py          # L1  CadQuery 2D sketches from a dict
├── profile_from_straight_connections.py   # L1  2D profiles from point lists
│
├── components_premade/                    # L3  Catalogue of parametric components
│   ├── __init__.py                        #     Builder registry + dispatcher
│   ├── components_premade_reactor_vessel.py
│   ├── components_premade_top_plate.py
│   ├── components_premade_ihx.py
│   ├── components_premade_core.py
│   ├── components_premade_diagrid.py
│   ├── components_premade_strongback.py
│   ├── components_premade_primary_pump.py
│   ├── components_premade_redan.py
│   └── components_premade_above_core_structure.py
│
├── materials.py                           # L5  Central material library
├── component_material_zones.py            # L5  Material zones per component type
├── homogenise_solid.py                    # L5  Component -> equivalent cylinder
├── homogenise.py                          # L5  Whole assembly -> homogenised model
├── porosity.py                            # L5  Per-component porosity for TRACE
├── esfr_smr_specs.py                      # L5  ESFR-SMR specs, importable copy
├── porosity_table.py                      # L5  Porosity vs reference nodalization
│
├── IntegrationOpenMC/                     # OpenMC sodium-activation calculation
│   └── README.md                          #     (see note on the core model)
│
├── examples/                              # One script per operation and component
└── examples_reactor/                      # Full reactor models (ESFR-SMR, SEALER)
```

`output/` is created on first export and holds generated STEP / STL / JSON files.

---

## Available premade components

| Key | Description |
|---|---|
| `reactor_vessel` | Cylindrical vessel with flat, ellipsoidal, hemispherical or torispherical heads |
| `reactor_top_plate` | Flat top plate with symmetric, custom-angle or explicit hole groups |
| `ihx` | Intermediate heat exchanger (plenums, windowed bundle shell, tube rings, central pipe, riser) |
| `reactor_core` | Cylindrical or n-sided prismatic core |
| `strongback` | Flanged strongback support structure |
| `primary_pump` | Primary sodium pump with mirror-symmetric elbow nozzles and top flange |
| `diagrid` | Hollow diagrid with lateral pump-nozzle bosses |
| `redan` | Inner vessel separating the hot and cold pools |
| `above_core_structure` | Above-core structure with flow holes, CRDL and bottom plate |

Components not in this list still work: anything built from a 2D profile or a CadQuery primitive goes through the same pipeline, and is homogenised generically as one zone of one material.

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

Editable mode registers the package so every module can be imported by name, and source changes take effect without reinstalling.

---

## Usage

### Build and assemble a reactor

```python
from assemble import assemble_objects

specs = [
    {
        "obj_type": "reactor_vessel",
        "obj_id": "rv",
        "inner_d": 4.72,
        "wall_t": 0.04,
        "straight_h": 5.5,
        "bottom_head_type": "hemispherical",
    },
    {
        "obj_type": "diagrid",
        "obj_id": "diagrid",
        "diameter": 2.4,
        "height": 0.3,
        "wall_t": 0.030,
        "z_bottom": 0.0,
    },
]

assembly = assemble_objects(specs, export_path="output/reactor.step", units="m")
```

Geometry is unit-agnostic: choose one unit and use it consistently. `units=`
is optional and only declares what the numbers mean, so the STEP header is
correct; nothing is rescaled. Omitting it assumes metres and warns.

### Build a single solid

```python
from build_3D_solid import build_solid

solid, obj_id = build_solid(
    operation="extrude",
    profile={"obj_type": "circle", "radius": 2.0},
    height=1.0,
)
```

### Homogenise for Monte Carlo

Add a material assignment to each spec — `material` for a single-material
component, or `materials` binding each declared zone, with the reserved
`_filler` key naming what surrounds the component in the pool.

```python
from homogenise import homogenise_objects, build_cad

model = homogenise_objects(
    specs,
    pool={"material": "na_primary"},
    units="cm",                       # OpenMC works in centimetres
    out_path="output/homogenised_model_cm.json",
)

assembly = build_cad(model)           # rebuild as CAD to check it by eye
```

Each cell's composition is an atom-for-atom average of the CAD solid it
replaces, so the model holds the same amount of every nuclide as the design.

### Measure porosities for a system code

```python
from porosity import porosities, print_table

print_table(porosities(specs))
```

`porosity` is the primary coolant over each component's equivalent cylinder.
Check `slack_fraction` alongside it: when the two are equal, no fluid zone was
measured and the number is set by the bounding cylinder rather than by the
geometry. `python porosity_table.py` lays the measured values against the
reference ESFR-SMR nodalization.

---

## OpenMC integration

`IntegrationOpenMC/` runs a two-step MAGIC sodium-activation calculation on the
homogenised JSON model. The detailed core model it embeds is **not** included in
this repository; see [IntegrationOpenMC/README.md](IntegrationOpenMC/README.md)
for the interface a substitute must expose.

---

## Dependencies

| Package | Purpose |
|---|---|
| `cadquery` | 3D solid modelling kernel (via OCCT) |
| `ocp_vscode` | In-editor 3D viewer |
| `Shapely` | 2D polygon offsetting for hollow profiles |
| `numpy` | Numerical utilities |
| `openmc` | Optional — only for `IntegrationOpenMC/` |

---

## License

MIT — see [LICENSE](LICENSE).

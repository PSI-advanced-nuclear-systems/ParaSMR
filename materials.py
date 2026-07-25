"""
Central material library.

Every component spec references these by name in its ``materials`` block; this
file includes what each material is. There are two accepted forms per material:

    "number_density"  ->  nuclide: atoms/b·cm           (the simple, preferred form)
    "mass_density"    ->  density (g/cm³) + nuclide: {ao: atom_frac, M: molar_mass}

"""

MATERIALS = {
    # Structural steel (placeholder densities — replace with your own)
    "ss316": {
        "kind": "number_density",
        "nuclides": {
            "Fe56": 5.90e-2,
            "Cr52": 1.60e-2,
            "Ni58": 8.00e-3,
            "Mo98": 1.20e-3,
        },
    },
    "ss304": {
        "kind": "number_density",
        "nuclides": {
            "Fe56": 6.00e-2,
            "Cr52": 1.70e-2,
            "Ni58": 7.00e-3,
        },
    },

    # Homogenised SFR core from main_no_ihx.py (D3.1 design).
    # Blends fissile MOX + fertile UO2 across active fuel zones (95 cm total):
    # - 65 cm fissile (zones 3, 5: 25 + 40 cm)
    # - 30 cm fertile (zones 2, 4: 10 + 20 cm blanket + plate)
    # Weight: 68.4% MOX + 31.6% UO2, computed from ESFR-SIMPLE deliverable D3.1.
    "core_smear": {
        "kind": "number_density",
        "nuclides": {
            "O16":   4.6418e-2,
            "U235":  4.89e-5,
            "U238":  1.923e-2,
            "Pu238": 1.47e-4,
            "Pu239": 1.945e-3,
            "Pu240": 1.212e-3,
            "Pu241": 3.35e-4,
            "Pu242": 4.20e-4,
            "Am241": 3.17e-5,
        },
    },

    # Coolants by mass density + atom fractions
    "na_primary": {
        "kind": "mass_density",
        "density": 0.83,  # g/cm³ at the primary-side temperature
        "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}},
    },
    "na_secondary": {
        "kind": "mass_density",
        "density": 0.85,  # g/cm³ at the secondary-side temperature
        "nuclides": {"Na23": {"ao": 1.0, "M": 22.99}},
    },
}
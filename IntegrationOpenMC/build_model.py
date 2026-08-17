"""
build_model.py
==============
Combine the validated detailed ESFR-SMR core (main_no_ihx_serpent_2.py) with
the homogenised primary-pool layout (homogenised_model_cm*.json) into a single
OpenMC model, for the two-step MAGIC IHX sodium-activation calculation.

This is the single source of truth for geometry + materials + tallies; both
step1_eigenvalue.py and step2_magic.py import `build()` from here so they can
never drift apart (same pattern as ym_MAGIC_test's main.py / ww_generation.py).

Usage (standalone: just export the shared XML + a plot):
    python build_model.py homogenised_model_cm20260725_194805.json
"""

import sys
import json

import openmc

import main_no_ihx_serpent_2 as core_mod

# ----------------------------------------------------------------------
# Placement of the detailed core inside the pool
# ----------------------------------------------------------------------
CORE_Z_SHIFT = 59.0     # cm — JSON `core` z_bottom; detailed core is internal z=0..393.5
CORE_BOUND_R = 200.0    # cm — transmission cylinder bounding the embedded core


def _mat_from_nd(name, number_densities):
    """OpenMC Material from a {nuclide: atoms/b-cm} dict (atom-fraction form)."""
    m = openmc.Material(name=name)
    total = 0.0
    for nuc, nd in number_densities.items():
        m.add_nuclide(nuc, nd, 'ao')
        total += nd
    m.set_density('atom/b-cm', total)
    return m


def build(json_path):
    """Build the combined core+pool model.

    Returns
    -------
    dict with keys:
      geometry   : openmc.Geometry
      materials  : openmc.Materials
      tallies    : openmc.Tallies
      ihx_names  : list[str]           names of the IHX materials (for post-proc)
      ihx_extent : (r_max, z_bot, z_top)   for sizing the Step-2 MAGIC mesh (cm)
      core_active_z : (z0, z1)         shifted active-fuel z-range (source box)
      sec_frac   : float               secondary/(primary+secondary) Na in an IHX
    """
    with open(json_path) as fh:
        model = json.load(fh)
    assert model.get('unit') == 'cm', f"expected unit 'cm', got {model.get('unit')!r}"

    mats = {}          # name -> openmc.Material
    cells = []
    occ = None         # running union of priority solids (core + components)

    def _add_occ(region):
        nonlocal occ
        occ = region if occ is None else (occ | region)

    # -- pool sodium material (needed as the core's outer fill) -------------
    pool = model['pool']
    m_pool = _mat_from_nd('pool', pool['number_densities'])
    mats['pool'] = m_pool

    # -- embedded detailed core --------------------------------------------
    core_univ, core_materials = core_mod.build_core(outer_fill=m_pool,
                                                     bound_r=CORE_BOUND_R)
    for m in core_materials:
        if m.name not in mats:
            mats[m.name] = m

    core_z0 = CORE_Z_SHIFT
    core_z1 = CORE_Z_SHIFT + (core_mod.Z_CORE_HI - core_mod.Z_CORE_LO)
    s_core_cyl = openmc.ZCylinder(r=CORE_BOUND_R)
    s_core_zlo = openmc.ZPlane(z0=core_z0)
    s_core_zhi = openmc.ZPlane(z0=core_z1)
    core_region = -s_core_cyl & +s_core_zlo & -s_core_zhi
    core_cell = openmc.Cell(name='core_embedded', fill=core_univ,
                            region=core_region)
    core_cell.translation = (0.0, 0.0, CORE_Z_SHIFT)
    cells.append(core_cell)
    _add_occ(core_region)

    # shifted active-fuel z-range (Serpent FEB..UGP = 152.318..245.318) -> +shift
    core_active_z = (core_mod.Z_FEB + CORE_Z_SHIFT, core_mod.Z_UGP + CORE_Z_SHIFT)

    # -- homogenised components (skip the JSON placeholder core) ------------
    ihx_names = []
    r_comp_max = CORE_BOUND_R
    z_comp_lo, z_comp_hi = core_z0, core_z1
    for comp in model['components']:
        if comp['obj_type'] == 'reactor_core':
            continue                      # replaced by the detailed core
        name = comp['name']
        m = _mat_from_nd(name, comp['number_densities'])
        mats[name] = m
        cyl = comp['cylinder']
        z_bot = cyl['z_bottom']
        z_top = cyl['z_bottom'] + cyl['height']
        s_cyl = openmc.ZCylinder(x0=cyl['x'], y0=cyl['y'], r=cyl['radius'])
        s_lo = openmc.ZPlane(z0=z_bot)
        s_hi = openmc.ZPlane(z0=z_top)
        reg = -s_cyl & +s_lo & -s_hi
        cells.append(openmc.Cell(name=name, fill=m, region=reg))
        _add_occ(reg)
        r_comp_max = max(r_comp_max, (cyl['x']**2 + cyl['y']**2) ** 0.5 + cyl['radius'])
        z_comp_lo = min(z_comp_lo, z_bot)
        z_comp_hi = max(z_comp_hi, z_top)
        if comp['obj_type'] == 'ihx':
            ihx_names.append(name)

    # -- vessel wall (annulus) ---------------------------------------------
    v = model['vessel']
    m_vessel = _mat_from_nd('vessel', v['number_densities'])
    mats['vessel'] = m_vessel
    r_in, r_out = v['r_inner'], v['r_outer']
    z_v_lo, z_v_hi = v['z_bottom'], v['z_top']
    t_bot = v.get('bottom_plate_thickness', 0.0)

    # -- top plate ---------------------------------------------------------
    plate = model.get('plate')
    if plate:
        m_plate = _mat_from_nd('plate', plate['number_densities'])
        mats['plate'] = m_plate

    # -- outer (vacuum) domain --------------------------------------------
    r_sys = max(r_out, plate['radius'] if plate else 0.0, r_comp_max) + 1.0
    z_sys_lo = min(z_v_lo - t_bot, z_comp_lo) - 1.0
    z_sys_hi = max((plate['z_top'] if plate else z_v_hi), z_comp_hi) + 1.0

    s_out = openmc.ZCylinder(r=r_sys, boundary_type='vacuum')
    s_sys_lo = openmc.ZPlane(z0=z_sys_lo, boundary_type='vacuum')
    s_sys_hi = openmc.ZPlane(z0=z_sys_hi, boundary_type='vacuum')
    domain = -s_out & +s_sys_lo & -s_sys_hi

    s_v_out = openmc.ZCylinder(r=r_out)
    s_v_in = openmc.ZCylinder(r=r_in)
    s_v_zlo = openmc.ZPlane(z0=z_v_lo)
    s_v_zhi = openmc.ZPlane(z0=z_v_hi)

    vessel_box = -s_v_out & +s_v_in & +s_v_zlo & -s_v_zhi
    cells.append(openmc.Cell(name='vessel', fill=m_vessel,
                             region=vessel_box & ~occ))

    boxes = [vessel_box]

    # bottom plate (full disk closing the vessel, minus any components)
    if t_bot > 0:
        s_bot = openmc.ZPlane(z0=z_v_lo - t_bot)
        bottom_box = -s_v_out & +s_bot & -s_v_zlo
        cells.append(openmc.Cell(name='vessel_bottom_plate', fill=m_vessel,
                                 region=bottom_box & ~occ))
        boxes.append(bottom_box)

    # top plate (disk; components penetrate it and take priority)
    if plate:
        s_p_cyl = openmc.ZCylinder(r=plate['radius'])
        s_p_lo = openmc.ZPlane(z0=plate['z_bottom'])
        s_p_hi = openmc.ZPlane(z0=plate['z_top'])
        plate_box = -s_p_cyl & +s_p_lo & -s_p_hi
        cells.append(openmc.Cell(name='plate', fill=m_plate,
                                 region=plate_box & ~occ))
        boxes.append(plate_box)

    # -- pool (fills the vessel bore, minus core + components) --------------
    pool_box = -s_v_in & +s_v_zlo & -s_v_zhi
    cells.append(openmc.Cell(name='pool', fill=m_pool, region=pool_box & ~occ))
    boxes.append(pool_box)

    # -- void catch-all (cover gas / outside vessel; everything not filled) -
    filled = occ
    for b in boxes:
        filled = filled | b
    cells.append(openmc.Cell(name='void', fill=None, region=domain & ~filled))

    geometry = openmc.Geometry(openmc.Universe(name='root', cells=cells))
    materials = openmc.Materials(list(mats.values()))
    for m in materials:
        m.temperature = getattr(m, 'temperature', None) or 900.0

    # -- tallies: Na-23 (n,gamma) per IHX + a total sanity tally -----------
    tallies = openmc.Tallies()
    for name in ihx_names:
        t = openmc.Tally(name=f'{name}_na23_ngamma')
        t.filters = [openmc.MaterialFilter([mats[name]])]
        t.nuclides = ['Na23']
        t.scores = ['(n,gamma)']
        tallies.append(t)
    t_tot = openmc.Tally(name='total_na23_ngamma')   # sanity: must be non-zero
    t_tot.nuclides = ['Na23']
    t_tot.scores = ['(n,gamma)']
    tallies.append(t_tot)

    # Secondary Na share within an IHX, taken from the JSON atom contents.
    #
    # The IHX is one blended sodium, so the tally returns the TOTAL Na-23
    # capture rate in the cell. Every Na-23 nucleus in it sees the same flux and
    # the same cross section, so the secondary share of the rate is the
    # secondary share of the Na-23 ATOMS, not of the volume:
    #
    #     R_sec / R_tot  =  V_sec n_sec / (V_sec n_sec + V_pri n_pri)
    #
    # Volume fractions only coincide with this when both sodiums have the same
    # number density. Here they do not (0.83 vs 0.85 g/cm3), and weighting by
    # volume understates the secondary share by about 1.6 %.
    ihx0 = next(c for c in model['components'] if c['obj_type'] == 'ihx')
    at = ihx0['qa']['by_material_atoms']
    a_sec = at['na_secondary']['Na23']
    a_pri = at['na_primary']['Na23']
    sec_frac = a_sec / (a_sec + a_pri)

    return dict(geometry=geometry, materials=materials, tallies=tallies,
                ihx_names=ihx_names,
                ihx_extent=(r_comp_max, z_comp_lo, z_comp_hi),
                core_active_z=core_active_z, sec_frac=sec_frac)


def setup_xml(json_path):
    """Export the shared materials.xml / geometry.xml / tallies.xml."""
    b = build(json_path)
    b['materials'].export_to_xml()
    b['geometry'].export_to_xml()
    b['tallies'].export_to_xml()
    return b


def plot_geometry(b, prefix='combined'):
    """Colour-by-material XY (through the IHXs) and XZ verification plots."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    r_max, z_bot, z_top = b['ihx_extent']
    root = b['geometry'].root_universe
    w = 2.1 * r_max

    root.plot(origin=(0.0, 0.0, 250.0), width=(w, w), pixels=(2000, 2000),
              basis='xy', color_by='material')
    plt.title('Core + pool + IHX - XY (z = 250 cm)')
    plt.savefig(f'{prefix}_xy.png', dpi=150, bbox_inches='tight')
    plt.close()

    h = 1.05 * (z_top - z_bot) + 400.0
    root.plot(origin=(0.0, 0.0, (z_bot + z_top) / 2.0), width=(w, h),
              pixels=(1500, 1500), basis='xz', color_by='material')
    plt.title('Core + pool + IHX - XZ (y = 0)')
    plt.savefig(f'{prefix}_xz.png', dpi=150, bbox_inches='tight')
    plt.close()
    print(f"wrote {prefix}_xy.png, {prefix}_xz.png")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f'usage: python {sys.argv[0]} <homogenised_model_cm*.json>')
    b = build(sys.argv[1])
    print(f"materials : {len(b['materials'])}")
    print(f"cells     : {len(b['geometry'].root_universe.cells)}")
    print(f"IHX tallies: {b['ihx_names']}")
    print(f"IHX extent (r_max, z_bot, z_top): {b['ihx_extent']}")
    print(f"core active z (shifted): {b['core_active_z']}")
    print(f"secondary Na fraction: {b['sec_frac']:.4f}")
    b['materials'].export_to_xml()
    b['geometry'].export_to_xml()
    b['tallies'].export_to_xml()
    print("Exported materials.xml, geometry.xml, tallies.xml")
    plot_geometry(b)

import math
import datetime
from assemble import assemble_objects
from ocp_vscode import show


_OUTER_D    = 4.8
_STRAIGHT_H = 4.3

_CORE_Z_BOTTOM = 0.55
_CORE_HEIGHT   = 1.3
_CORE_Z_TOP    = _CORE_Z_BOTTOM + _CORE_HEIGHT

_PUMP_RING_R   = 1.85
_PUMP_RADIUS   = 0.25
_PUMP_Z_BOTTOM = 2.5
_PUMP_HEIGHT   = 3.0

_SG_RING_R = 1.85
_SG_RADIUS = 0.30

_CHIMNEY_OUTER_R = 0.70
_CHIMNEY_WALL_T  = 0.02
_CHIMNEY_Z_TOP   = _PUMP_Z_BOTTOM + _PUMP_HEIGHT

_CRD_Z_BOTTOM = _CORE_Z_BOTTOM + _CORE_HEIGHT / 2

_CONTROL_COLOR = (0.75, 0.20, 0.20, 1.0)
_CR_COLOR      = (0.40, 0.20, 0.55, 1.0)


def _ring_position(ring_r, angle_deg, z_bottom):
    a = math.radians(angle_deg)
    return (ring_r * math.cos(a), ring_r * math.sin(a), z_bottom)


RV = {
    "obj_type":           "reactor_vessel",
    "obj_id":             "sealer55_rv",
    "outer_d":            _OUTER_D,
    "wall_t":             0.04,
    "straight_h":         _STRAIGHT_H,
    "bottom_head_type":   "ellipsoidal",
    "bottom_head_params": {"head_depth": 1.2},
    "color":              (0.55, 0.60, 0.65, 1.0),
}

TOP_PLATE = {
    "obj_type":  "reactor_top_plate",
    "obj_id":    "sealer55_top_plate",
    "outer_d":   _OUTER_D,
    "thickness": 0.15,
    "z_bottom":  _STRAIGHT_H,
    "hole_groups": [
        {
            "hole_diameter":    2 * _CHIMNEY_OUTER_R,
            "layout":           "explicit_positions",
            "positions":        [(0.0, 0.0)],
        },
        {
            "hole_diameter":    2 * _PUMP_RADIUS,
            "layout":           "symmetric",
            "count":            8,
            "placement_radius": _PUMP_RING_R,
            "start_angle_deg":  0.0,
        },
        {
            "hole_diameter":    2 * _SG_RADIUS,
            "layout":           "symmetric",
            "count":            8,
            "placement_radius": _SG_RING_R,
            "start_angle_deg":  22.5,
        },
    ],
    "color": (0.60, 0.60, 0.65, 1.0),
}

DIAGRID = {
    "obj_type": "diagrid",
    "obj_id":   "sealer55_diagrid",
    "diameter": 2.2,
    "height":   0.5,
    "z_bottom": 0.05,
    "wall_t":   0.03,
    "color":    (0.45, 0.50, 0.55, 1.0),
}

CORE = {
    "obj_type": "reactor_core",
    "obj_id":   "sealer55_core",
    "radius":   1.0,
    "height":   _CORE_HEIGHT,
    "z_bottom": _CORE_Z_BOTTOM,
    "n_sides":  6,
    "color":    (0.85, 0.35, 0.20, 1.0),
}

CHIMNEY_WALL = {
    "operation":       "extrude",
    "obj_id":          "sealer55_chimney_wall",
    "profile":         {"obj_type": "circle", "radius": _CHIMNEY_OUTER_R},
    "height":          _CHIMNEY_Z_TOP - _CORE_Z_TOP - _CHIMNEY_WALL_T,
    "wall_thickness":  _CHIMNEY_WALL_T,
    "center_coords":   (0.0, 0.0, _CORE_Z_TOP),
    "color":           (0.90, 0.55, 0.20, 1.0),
    "interfaces_with": ["sealer55_top_plate", "sealer55_core"],
}

CHIMNEY_CAP = {
    "operation":       "extrude",
    "obj_id":          "sealer55_chimney_cap",
    "profile":         {"obj_type": "circle", "radius": _CHIMNEY_OUTER_R},
    "height":          _CHIMNEY_WALL_T,
    "center_coords":   (0.0, 0.0, _CHIMNEY_Z_TOP - _CHIMNEY_WALL_T),
    "color":           (0.90, 0.55, 0.20, 1.0),
    "interfaces_with": ["sealer55_chimney_wall"],
}


def _make_pump(obj_id, angle_deg):
    return {
        "operation":       "extrude",
        "obj_id":          obj_id,
        "profile":         {"obj_type": "circle", "radius": _PUMP_RADIUS},
        "height":          _PUMP_HEIGHT,
        "center_coords":   _ring_position(_PUMP_RING_R, angle_deg,
                                          _PUMP_Z_BOTTOM),
        "color":           (0.30, 0.55, 0.80, 1.0),
        "interfaces_with": ["sealer55_top_plate"],
    }
PUMP1 = _make_pump("sealer55_pump_1",   0.0)
PUMP2 = _make_pump("sealer55_pump_2",  45.0)
PUMP3 = _make_pump("sealer55_pump_3",  90.0)
PUMP4 = _make_pump("sealer55_pump_4", 135.0)
PUMP5 = _make_pump("sealer55_pump_5", 180.0)
PUMP6 = _make_pump("sealer55_pump_6", 225.0)
PUMP7 = _make_pump("sealer55_pump_7", 270.0)
PUMP8 = _make_pump("sealer55_pump_8", 315.0)


def _make_sg(obj_id, angle_deg):
    return {
        "operation":       "extrude",
        "obj_id":          obj_id,
        "profile":         {"obj_type": "circle", "radius": _SG_RADIUS},
        "height":          4.05,
        "center_coords":   _ring_position(_SG_RING_R, angle_deg, 0.55),
        "color":           (0.85, 0.65, 0.20, 1.0),
        "interfaces_with": ["sealer55_top_plate"],
    }
SG1 = _make_sg("sealer55_sg_1",  22.5)
SG2 = _make_sg("sealer55_sg_2",  67.5)
SG3 = _make_sg("sealer55_sg_3", 112.5)
SG4 = _make_sg("sealer55_sg_4", 157.5)
SG5 = _make_sg("sealer55_sg_5", 202.5)
SG6 = _make_sg("sealer55_sg_6", 247.5)
SG7 = _make_sg("sealer55_sg_7", 292.5)
SG8 = _make_sg("sealer55_sg_8", 337.5)


def _make_rod(obj_id, angle_deg, color):
    return {
        "operation":       "extrude",
        "obj_id":          obj_id,
        "profile":         {"obj_type": "circle", "radius": 0.04},
        "height": _CHIMNEY_Z_TOP - _CHIMNEY_WALL_T - 0.05 - _CRD_Z_BOTTOM,
        "center_coords":   _ring_position(0.40, angle_deg, _CRD_Z_BOTTOM),
        "color":           color,
        "interfaces_with": ["sealer55_core"],
    }
CONTROL1 = _make_rod("sealer55_control_rod_1",  0.0, _CONTROL_COLOR)
CONTROL2 = _make_rod("sealer55_control_rod_2", 30.0, _CONTROL_COLOR)

CR1  = _make_rod("sealer55_shutdown_rod_1",   60.0, _CR_COLOR)
CR2  = _make_rod("sealer55_shutdown_rod_2",   90.0, _CR_COLOR)
CR3  = _make_rod("sealer55_shutdown_rod_3",  120.0, _CR_COLOR)
CR4  = _make_rod("sealer55_shutdown_rod_4",  150.0, _CR_COLOR)
CR5  = _make_rod("sealer55_shutdown_rod_5",  180.0, _CR_COLOR)
CR6  = _make_rod("sealer55_shutdown_rod_6",  210.0, _CR_COLOR)
CR7  = _make_rod("sealer55_shutdown_rod_7",  240.0, _CR_COLOR)
CR8  = _make_rod("sealer55_shutdown_rod_8",  270.0, _CR_COLOR)
CR9  = _make_rod("sealer55_shutdown_rod_9",  300.0, _CR_COLOR)
CR10 = _make_rod("sealer55_shutdown_rod_10", 330.0, _CR_COLOR)


_TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
show(assemble_objects(
    [RV, TOP_PLATE, DIAGRID, CORE, CHIMNEY_WALL, CHIMNEY_CAP,
     PUMP1, PUMP2, PUMP3, PUMP4, PUMP5, PUMP6, PUMP7, PUMP8,
     SG1, SG2, SG3, SG4, SG5, SG6, SG7, SG8,
     CONTROL1, CONTROL2,
     CR1, CR2, CR3, CR4, CR5, CR6, CR7, CR8, CR9, CR10],
    export_path=f"output/sealer55_full_reactor_{_TS}.step",
    units="m",))

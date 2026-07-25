"""
Built-in 2D sketch profiles.

Provides a dictionary-driven interface to create common 2D shapes
(rectangles, circles, ellipses, trapezoids, slots, regular polygons,
and arbitrary polygons) as CadQuery Workplanes.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Tuple, Union
import math
import cadquery as cq
from ocp_vscode import show

class ShapeType(Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    TRAPEZOID = "trapezoid"
    SLOT = "slot"
    REGULAR_POLYGON = "regular_polygon"
    POLYGON = "polygon"


def build_2D_sketch(obj: Dict[str, Any], sketch_plane: str = "XY") -> cq.Workplane:
    """
    Build and return a 2D CadQuery Sketch from a shape descriptor dict.

    Supported obj_type values and their required keys:
      rectangle     : width, height, [angle]
      circle        : radius
      ellipse       : r1 (major), r2 (minor), [angle]
      trapezoid     : width, height, a1, [angle]
      slot          : width, height, [angle]
      regular_polygon: radius, nmb_of_sides, [angle]
      polygon       : pts (list of (x,y), >= 3 points), [angle]

    Optional keys (all shapes):
      angle : float = 0       — rotation in degrees
      mode  : str   = 'a'     — CadQuery sketch mode ('a','s','i','c','r')
      tag   : str   = None    — CadQuery sketch tag
    """
    try:
        shape = ShapeType(obj["obj_type"])
    except Exception as e:
        raise ValueError(f"Unknown obj_type={obj.get('obj_type')!r}") from e

    angle = float(obj.get("angle", 0.0))
    mode  = obj.get("mode", 'a')
    tag   = obj.get("tag", None)

    if shape == ShapeType.RECTANGLE:
        if obj["width"] <= 0:  raise ValueError("rectangle width must be > 0")
        if obj["height"] <= 0: raise ValueError("rectangle height must be > 0")
        sketch = cq.Sketch().rect(obj["width"], obj["height"], angle=angle, mode=mode, tag=tag)

    elif shape == ShapeType.CIRCLE:
        if obj["radius"] <= 0: raise ValueError("circle radius must be > 0")
        sketch = cq.Sketch().circle(obj["radius"], mode=mode, tag=tag)

    elif shape == ShapeType.ELLIPSE:
        if obj["r1"] <= 0: raise ValueError("ellipse r1 must be > 0")
        if obj["r2"] <= 0: raise ValueError("ellipse r2 must be > 0")
        sketch = cq.Sketch().ellipse(obj["r1"], obj["r2"], angle=angle, mode=mode, tag=tag)

    elif shape == ShapeType.TRAPEZOID:
        if obj["width"] <= 0:  raise ValueError("trapezoid width must be > 0")
        if obj["height"] <= 0: raise ValueError("trapezoid height must be > 0")
        sketch = cq.Sketch().trapezoid(obj["width"], obj["height"], obj["a1"], angle=angle, mode=mode, tag=tag)

    elif shape == ShapeType.SLOT:
        if obj["width"] <= 0:  raise ValueError("slot width must be > 0")
        if obj["height"] <= 0: raise ValueError("slot height must be > 0")
        sketch = cq.Sketch().slot(obj["width"], obj["height"], angle=angle, mode=mode, tag=tag)

    elif shape == ShapeType.REGULAR_POLYGON:
        if obj["radius"] <= 0:          raise ValueError("regular_polygon radius must be > 0")
        if int(obj["nmb_of_sides"]) < 3: raise ValueError("regular_polygon nmb_of_sides must be >= 3")
        sketch = cq.Sketch().regularPolygon(obj["radius"], int(obj["nmb_of_sides"]), angle=angle, mode=mode, tag=tag)

    elif shape == ShapeType.POLYGON:
        if not isinstance(obj["pts"], list) or len(obj["pts"]) < 3:
            raise ValueError("polygon pts must be a list of >= 3 points")
        sketch = cq.Sketch().polygon(obj["pts"], angle=angle, mode=mode, tag=tag)

    else:
        raise RuntimeError(f"Unhandled shape type: {shape}")
    try: wp = cq.Workplane(sketch_plane)
    except Exception as e: raise ValueError(f"Invalid sketch_plane={sketch_plane!r}") from e
    wp_with_sketch = wp.placeSketch(sketch.clean())
    wp_with_sketch._plane_name = sketch_plane  # type: ignore[attr-defined]
    return wp_with_sketch
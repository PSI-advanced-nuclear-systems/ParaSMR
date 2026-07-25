import cadquery as cq
from typing import Sequence, Tuple, Literal

PlaneName = Literal["XY", "XZ", "YZ"]

def create_profile_from_straight_connections(
    l: Sequence[Tuple[float, float]],
    plane: PlaneName = "XY",
    closed: bool = False
) -> cq.Workplane:
    s = cq.Sketch()
    for i in range(len(l) - 1):
        s = s.segment(l[i], l[i + 1])
    if closed:
        s = s.close().assemble()
    wp = cq.Workplane(plane).placeSketch(s)
    wp._plane_name = plane  # type: ignore[attr-defined]
    return wp
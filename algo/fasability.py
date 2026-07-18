from __future__ import annotations

from shapely import Polygon
from shapely.affinity import translate
from shapely.geometry import box

from algo.nfp import EPSILON


def try_placement(
    moving: Polygon,
    x: float,
    y: float,
    placed_polygons: list[Polygon],
    canvas_width: float,
    canvas_height: float
):
    candidate = translate(moving, xoff=x, yoff=y)
    canvas = box(0, 0, canvas_width, canvas_height)

    # covers() allows the polygon to touch the canvas boundary.
    if not canvas.covers(candidate):
        return None

    for placed in placed_polygons:
        overlap_area = candidate.intersection(placed).area

        if overlap_area > EPSILON:
            return None

    return candidate
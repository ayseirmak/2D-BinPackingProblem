"""
Scoring metrics, split into cheap (O(1)) and expensive stages.

Cheap  : bounding-box density, canvas utilisation, max_x, max_y  (from cache).
Expensive : exact contact ratio, mandatory feasibility gate, capped flexibility.
"""

from shapely.geometry import LineString, MultiLineString

from algo.nfp import EPSILON
from algo.nfp_candidate import candidate_translations_fast


# --------------------------------------------------------------------------- #
# Cheap stage - pure arithmetic on cached aggregates
# --------------------------------------------------------------------------- #

def cheap_metrics(layout, candidate):
    """density, utilisation, max_x, max_y for layout + candidate, in O(1)."""
    cx0, cy0, cx1, cy1 = candidate.bounds
    if layout.is_empty:
        min_x, min_y, max_x, max_y = cx0, cy0, cx1, cy1
    else:
        min_x = min(layout.min_x, cx0)
        min_y = min(layout.min_y, cy0)
        max_x = max(layout.max_x, cx1)
        max_y = max(layout.max_y, cy1)

    new_used = layout.used_area + candidate.area
    bbox_area = (max_x - min_x) * (max_y - min_y)
    density = new_used / bbox_area if bbox_area > EPSILON else 0.0

    return {
        "density": density,
        "utilisation": new_used / layout.canvas_area,
        "max_x": max_x,
        "max_y": max_y,
    }


# --------------------------------------------------------------------------- #
# Expensive stage
# --------------------------------------------------------------------------- #

def _line_length(geometry) -> float:
    if geometry.is_empty:
        return 0.0
    if isinstance(geometry, LineString):
        return geometry.length
    if isinstance(geometry, MultiLineString):
        return sum(seg.length for seg in geometry.geoms)
    if hasattr(geometry, "geoms"):
        return sum(_line_length(p) for p in geometry.geoms)
    return 0.0


def contact_ratio(candidate, placed_polygons, canvas) -> float:
    """Shared edge length with other parts + canvas walls, over the perimeter."""
    perimeter = candidate.length
    if perimeter <= EPSILON:
        return 0.0
    total = _line_length(candidate.boundary.intersection(canvas.boundary))
    for placed in placed_polygons:
        total += _line_length(candidate.boundary.intersection(placed.boundary))
    return total / perimeter


def count_feasible_placements(layout, shape_type, canvas, max_count: int) -> int:
    """Feasible placements for shape_type on `layout`, capped at max_count."""
    count = 0
    for angle in shape_type.rotations:
        moving = shape_type.variants[angle]
        placements = candidate_translations_fast(layout, shape_type, angle, moving, canvas)
        count += len(placements)
        if count >= max_count:
            return max_count
    return count


def future_flexibility(layout, shape_types, canvas, K: int) -> float:
    """F = mean over types of min(1, N_t / K). 1.0 if no types given."""
    if not shape_types:
        return 1.0
    total = 0.0
    for t in shape_types:
        n_t = count_feasible_placements(layout, t, canvas, K)
        total += min(1.0, n_t / K)
    return total / len(shape_types)

"""
Scoring metric: bounding-box density of the whole cluster.

The score is deliberately a single objective. A candidate is NOT scored by its
own bounding-box density, but by the density of the bounding box covering
*every* placed part once this candidate is added:

    D = (A_used + A(candidate)) / area(bbox(cluster + candidate))

Computing it is O(1): Layout caches used_area and the cluster bounds, so no
geometry is rebuilt per candidate.
"""

from algo.nfp import EPSILON


def cluster_density(layout, candidate):
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

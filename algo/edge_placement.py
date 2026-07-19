"""
Edge-derived rotations (replaces the preset rotation list).

Instead of a fixed set of angles, the useful rotations are DERIVED so that a
candidate edge of the moving shape becomes anti-parallel to a "frontier" edge of
the current layout (or a canvas wall):

    theta = angle(frontier_edge) + pi - angle(candidate_edge)

An anti-parallel edge can sit flush against the frontier edge -> maximal contact.
We only produce the ANGLE SET here; the actual feasible positions for each angle
are still found by the NFP search, which keeps the algorithm robust (it will find
a spot whenever one exists, unlike pure edge-endpoint seating).
"""

import math

from shapely import unary_union

from algo.nfp_cache import placed_nfp


def _poly_edges(polygon):
    """Consecutive exterior edges as ((x0,y0),(x1,y1))."""
    cs = list(polygon.exterior.coords)   # closed ring, last == first
    return [(cs[i], cs[i + 1]) for i in range(len(cs) - 1)]


def _line_segments(geometry, out):
    """Flatten any (Multi)LineString / ring into a list of segments."""
    if geometry.is_empty:
        return
    gt = geometry.geom_type
    if gt in ("LineString", "LinearRing"):
        cs = list(geometry.coords)
        for i in range(len(cs) - 1):
            out.append((cs[i], cs[i + 1]))
    elif hasattr(geometry, "geoms"):
        for g in geometry.geoms:
            _line_segments(g, out)


def frontier_edges(layout, canvas):
    """Exposed boundary of the placed cluster + the canvas walls (as segments)."""
    edges = []
    _line_segments(canvas.exterior, edges)
    if layout.polygons:
        union = unary_union(layout.polygons)
        _line_segments(union.boundary, edges)
    return edges


def derived_angles(shape_type, frontiers, ndigits=2):
    """
    Distinct rotations (degrees) that align some shape edge parallel OR
    anti-parallel to some frontier edge. Both orientations are included so a
    shape edge can meet a frontier edge from either side; the NFP position
    search then decides which placements are actually feasible.
    """
    cedges = _poly_edges(shape_type.base_polygon)
    angles = set()
    for (A, B) in frontiers:
        fang = math.atan2(B[1] - A[1], B[0] - A[0])
        for (P, Q) in cedges:
            cang = math.atan2(Q[1] - P[1], Q[0] - P[0])
            theta = math.degrees(fang + math.pi - cang)
            angles.add(round(theta % 360.0, ndigits))
            angles.add(round((theta + 180.0) % 360.0, ndigits))
    return sorted(angles)


def fresh_forbidden(layout, moving_type, moving_rotation):
    """
    Union of all placed NFPs for one moving variant, computed from scratch (not
    cached). Edge-derived rotations rarely repeat between steps, so the cached
    incremental region would only accumulate dead entries.
    """
    if not layout.items:
        return None
    return unary_union([
        placed_nfp(p, moving_type, moving_rotation) for p in layout.items
    ])

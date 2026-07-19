"""
Candidate translation positions via a single forbidden-region union.

Instead of intersecting every pair of NFPs explicitly, we take the union of all
(translated) NFPs = the forbidden region for the moving reference point. Any
touching placement lies on the boundary of this union. Clipping the union to the
IFP automatically inserts the NFP-IFP contact vertices, and unary_union inserts
the NFP-NFP contact vertices where two parts meet. Interior holes are kept:
they are feasible pockets fully surrounded by forbidden region.
"""

from shapely.affinity import translate
from shapely.geometry import Point, Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection

from algo.IFP import rectangular_ifp
from algo.nfp import EPSILON


def add_geometry_vertices(points: set, geometry):
    """Collect every boundary vertex of any geometry into `points` (rounded)."""
    if geometry.is_empty:
        return
    if isinstance(geometry, Point):
        points.add((round(geometry.x, 8), round(geometry.y, 8)))
    elif isinstance(geometry, LineString):
        for x, y in geometry.coords:
            points.add((round(x, 8), round(y, 8)))
    elif isinstance(geometry, MultiLineString):
        for seg in geometry.geoms:
            add_geometry_vertices(points, seg)
    elif isinstance(geometry, Polygon):
        for x, y in geometry.exterior.coords:
            points.add((round(x, 8), round(y, 8)))
        for ring in geometry.interiors:            # keep hole boundaries
            for x, y in ring.coords:
                points.add((round(x, 8), round(y, 8)))
    elif isinstance(geometry, (MultiPolygon, GeometryCollection)) or hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            add_geometry_vertices(points, part)


def is_feasible(candidate: Polygon, layout, canvas) -> bool:
    """
    Inside the canvas (touching allowed) and non-overlapping with placed parts.

    Only parts returned by the spatial index are tested; a part whose bounding
    box misses the candidate cannot overlap it, so the result is unchanged.
    """
    if not canvas.covers(candidate):
        return False
    for placed in layout.nearby(candidate):
        if candidate.intersection(placed).area > EPSILON:
            return False
    return True


_UNSET = object()


def candidate_translations_fast(
    layout,
    moving_type,
    moving_rotation,
    moving_polygon,
    canvas,
    forbidden=_UNSET,
):
    """
    Return feasible placements [(x, y, polygon)] for the moving variant.

    `layout`    : Layout object (cached).
    `canvas`    : shapely box(0,0,W,H).
    `forbidden` : optional precomputed forbidden region. Pass one for edge-derived
                  (continuous) rotations so the persistent incremental cache - which
                  only pays off for a fixed rotation set - is bypassed. Omit to use
                  the cached region (preset rotations).
    """
    W, H = layout.canvas_width, layout.canvas_height
    ifp = rectangular_ifp(moving_polygon, W, H)
    if ifp.is_empty:
        return []

    points = set()

    # Canvas-contact candidates (corners / edges of the feasible region).
    add_geometry_vertices(points, ifp)

    # Forbidden region = union of all placed NFPs.
    if forbidden is _UNSET:
        forbidden = layout.forbidden(moving_type, moving_rotation)
    if forbidden is not None:
        # Clip to IFP: inserts NFP-IFP contact vertices and drops outside points.
        add_geometry_vertices(points, forbidden.intersection(ifp))

    # Materialise and feasibility-test each candidate point.
    results = []
    for x, y in points:
        candidate = translate(moving_polygon, xoff=x, yoff=y)
        if is_feasible(candidate, layout, canvas):
            results.append((x, y, candidate))

    results.sort(key=lambda r: (r[0], r[1]))   # deterministic order
    return results

"""
Candidate translation positions via a single forbidden-region union.

Instead of intersecting every pair of NFPs explicitly, we take the union of all
(translated) NFPs = the forbidden region for the moving reference point. Any
touching placement lies on the boundary of this union. Clipping the union to the
IFP automatically inserts the NFP-IFP contact vertices, and unary_union inserts
the NFP-NFP contact vertices where two parts meet. Interior holes are kept:
they are feasible pockets fully surrounded by forbidden region.
"""

from shapely import unary_union
from shapely.geometry import Point, Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection

from algo.IFP import rectangular_ifp
from algo.nfp import polygon_vertices, EPSILON
from algo.nfp_cache import placed_nfp


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


def is_feasible(candidate: Polygon, placed_polygons: list, canvas) -> bool:
    """Inside the canvas (touching allowed) and non-overlapping with placed parts."""
    if not canvas.covers(candidate):
        return False
    for placed in placed_polygons:
        if candidate.intersection(placed).area > EPSILON:
            return False
    return True


def candidate_translations_fast(
    layout,
    moving_type,
    moving_rotation,
    moving_polygon,
    canvas,
):
    """
    Return feasible placements [(x, y, polygon)] for the moving variant.

    `layout`   : Layout object (cached).
    `canvas`   : shapely box(0,0,W,H).
    """
    W, H = layout.canvas_width, layout.canvas_height
    ifp = rectangular_ifp(moving_polygon, W, H)
    if ifp.is_empty:
        return []

    points = set()

    # Canvas-contact candidates (corners / edges of the feasible region).
    add_geometry_vertices(points, ifp)

    # Forbidden region = union of all placed NFPs.
    if layout.items:
        nfps = [
            placed_nfp(placement, moving_type, moving_rotation)
            for placement in layout.items
        ]
        forbidden = unary_union(nfps)
        # Clip to IFP: inserts NFP-IFP contact vertices and drops outside points.
        forbidden_inside_ifp = forbidden.intersection(ifp)
        add_geometry_vertices(points, forbidden_inside_ifp)

    # Materialise and feasibility-test each candidate point.
    from shapely.affinity import translate
    results = []
    for x, y in points:
        candidate = translate(moving_polygon, xoff=x, yoff=y)
        if is_feasible(candidate, layout.polygons, canvas):
            results.append((x, y, candidate))

    results.sort(key=lambda r: (r[0], r[1]))   # deterministic order
    return results

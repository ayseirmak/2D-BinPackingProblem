from shapely.geometry import MultiPoint, Polygon

# Minimal convex no-fit polygon (NFP) construction
EPSILON = 1e-8


def polygon_vertices(polygon: Polygon):
    """Return exterior vertices without Shapely's repeated closing point."""
    return list(polygon.exterior.coords)[:-1]


def is_convex(polygon: Polygon) -> bool:
    """Check convexity by comparing the polygon with its convex hull."""
    return abs(polygon.area - polygon.convex_hull.area) <= EPSILON


def convex_nfp(fixed: Polygon, moving: Polygon) -> Polygon:
    """
    Return the no-fit polygon for two convex polygons.

    A translation point inside the NFP causes an overlap.
    A point on its boundary gives a touching placement.
    A point outside it produces no overlap.

    The returned coordinates represent translations applied to `moving`.
    """
    if not is_convex(fixed) or not is_convex(moving):
        raise ValueError("convex_nfp supports convex polygons only")

    fixed_vertices = polygon_vertices(fixed)
    moving_vertices = polygon_vertices(moving)

    # NFP(A, B) = A ⊕ (-B)
    minkowski_points = [
        (ax - bx, ay - by)
        for ax, ay in fixed_vertices
        for bx, by in moving_vertices
    ]

    nfp = MultiPoint(minkowski_points).convex_hull

    if not isinstance(nfp, Polygon):
        raise ValueError("NFP construction did not produce a polygon")

    return nfp
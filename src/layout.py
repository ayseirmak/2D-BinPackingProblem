"""
Layout state with cached aggregates, an incremental forbidden-region cache and
a spatial index.

Three caches, none of which change the algorithm's decisions - only its cost:

  * used_area / bounds  -> cheap score in O(1)
  * forbidden[variant]  -> union of all placed NFPs for one moving variant.
    Maintained INCREMENTALLY: adding a part unions the existing region with the
    single new NFP instead of re-unioning all n NFPs from scratch. Union is
    associative, so the geometry is identical to the from-scratch version.
  * STRtree             -> overlap tests only against parts whose bounding box
    actually overlaps the candidate, instead of all n placed parts.
"""

from dataclasses import dataclass

from shapely import unary_union
from shapely.strtree import STRtree

from algo.nfp_cache import placed_nfp

INF = float("inf")


@dataclass
class Placement:
    shape_type: object   # ShapeType
    rotation: float      # angle in degrees
    x: float             # translation applied to the canonical local polygon
    y: float
    polygon: object      # shapely Polygon in canvas coordinates


class Layout:
    def __init__(self, canvas_width: float, canvas_height: float):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.canvas_area = canvas_width * canvas_height

        self.items = []        # list[Placement]
        self.polygons = []     # parallel list of shapely polygons

        self.used_area = 0.0
        self.min_x = INF
        self.min_y = INF
        self.max_x = -INF
        self.max_y = -INF

        self._forbidden = {}   # (ShapeType, angle) -> unioned NFP region (or None)
        self._tree = None      # lazily built STRtree over self.polygons

    @property
    def is_empty(self) -> bool:
        return not self.items

    # ------------------------------------------------------------------ #
    # aggregates
    # ------------------------------------------------------------------ #

    def _absorb(self, placement: Placement):
        poly = placement.polygon
        self.items.append(placement)
        self.polygons.append(poly)
        self.used_area += poly.area
        x0, y0, x1, y1 = poly.bounds
        self.min_x = min(self.min_x, x0)
        self.min_y = min(self.min_y, y0)
        self.max_x = max(self.max_x, x1)
        self.max_y = max(self.max_y, y1)
        self._tree = None      # invalidate spatial index

    # ------------------------------------------------------------------ #
    # forbidden-region cache
    # ------------------------------------------------------------------ #

    def forbidden(self, moving_type, moving_rotation):
        """Union of NFP(placed_i, moving variant) over all placed parts."""
        key = (moving_type, moving_rotation)
        if key not in self._forbidden:
            # Cold path: materialise this variant from scratch (once per layout).
            nfps = [placed_nfp(p, moving_type, moving_rotation) for p in self.items]
            self._forbidden[key] = unary_union(nfps) if nfps else None
        return self._forbidden[key]

    def add(self, placement: Placement):
        """Mutating add; every materialised forbidden region is updated in O(1)."""
        for (mtype, rot), region in list(self._forbidden.items()):
            new_nfp = placed_nfp(placement, mtype, rot)
            self._forbidden[(mtype, rot)] = (
                new_nfp if region is None else unary_union([region, new_nfp])
            )
        self._absorb(placement)

    def added(self, placement: Placement) -> "Layout":
        """Return a copy with `placement` added (hypothetical layout L')."""
        clone = Layout(self.canvas_width, self.canvas_height)
        clone.items = list(self.items)
        clone.polygons = list(self.polygons)
        clone.used_area = self.used_area
        clone.min_x, clone.min_y = self.min_x, self.min_y
        clone.max_x, clone.max_y = self.max_x, self.max_y
        clone._forbidden = dict(self._forbidden)   # geometries are immutable
        clone.add(placement)
        return clone

    # ------------------------------------------------------------------ #
    # spatial index
    # ------------------------------------------------------------------ #

    def nearby(self, geometry):
        """Placed polygons whose bounding box overlaps `geometry`'s."""
        if not self.polygons:
            return []
        if self._tree is None:
            self._tree = STRtree(self.polygons)
        return [self.polygons[i] for i in self._tree.query(geometry)]

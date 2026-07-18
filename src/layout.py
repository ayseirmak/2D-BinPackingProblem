"""
Layout state with cached aggregates.

Caching used_area and the cluster bounds lets us compute the score
(bounding-box density, utilisation, max_x, max_y) in O(1) per candidate,
without rebuilding any geometry.
"""

from dataclasses import dataclass, field

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

    @property
    def is_empty(self) -> bool:
        return not self.items

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

    def add(self, placement: Placement):
        """Mutating add (used to grow the real layout)."""
        self._absorb(placement)

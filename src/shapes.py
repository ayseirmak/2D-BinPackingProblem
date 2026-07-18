"""
Shape definitions for the packing task.

Every shape is described ONCE as a convex polygon in its own local frame.
Nothing about the algorithm is hard-coded to a specific shape: to add a new
convex polygon you only append a ShapeType here.
"""

import math
from dataclasses import dataclass, field

from shapely.geometry import Polygon

from algo.nfp import is_convex
from src.rotation_polygon import create_rotated_local_polygon


def _shape_key(polygon: Polygon, ndigits: int = 6):
    """
    Rotation-invariant identity for an already-canonicalised polygon.

    create_rotated_local_polygon() anchors every variant at its bounding-box
    minimum, so two rotations that produce the same shape produce the same
    vertex set. Sorting + rounding makes that comparable.
    """
    return tuple(sorted(
        (round(x, ndigits), round(y, ndigits))
        for x, y in polygon.exterior.coords[:-1]
    ))


@dataclass
class ShapeType:
    """A convex shape type together with the rotations we are allowed to use."""
    id: int
    name: str
    base_polygon: Polygon
    rotations: tuple  # allowed angles in degrees, fixed order

    # angle -> canonical local polygon (min corner at origin), filled in __post_init__
    variants: dict = field(default_factory=dict)

    def __post_init__(self):
        if not is_convex(self.base_polygon):
            raise ValueError(f"Shape '{self.name}' is not convex")
        # Pre-compute (cache) every rotated version once, dropping any rotation
        # that reproduces an earlier one (see _dedupe_rotations).
        kept = []
        seen = set()
        for angle in self.rotations:
            variant = create_rotated_local_polygon(self.base_polygon, angle)
            key = _shape_key(variant)
            if key in seen:
                continue
            seen.add(key)
            kept.append(angle)
            self.variants[angle] = variant
        self.rotations = tuple(kept)

    @property
    def area(self) -> float:
        return self.base_polygon.area


# ---- geometry builders (local frame, will be normalised to origin later) ----

def square(side: float) -> Polygon:
    return Polygon([(0, 0), (side, 0), (side, side), (0, side)])


def rectangle(width: float, height: float) -> Polygon:
    return Polygon([(0, 0), (width, 0), (width, height), (0, height)])


def equilateral_triangle(side: float) -> Polygon:
    height = side * math.sqrt(3) / 2.0
    return Polygon([(0, 0), (side, 0), (side / 2.0, height)])


def isosceles_triangle(base: float, leg: float) -> Polygon:
    # apex height from the two equal legs and half the base
    height = math.sqrt(leg ** 2 - (base / 2.0) ** 2)
    return Polygon([(0, 0), (base, 0), (base / 2.0, height)])


def trapezium(top: float, bottom: float, height: float) -> Polygon:
    # symmetric isosceles trapezium, bottom edge on y=0
    inset = (bottom - top) / 2.0
    return Polygon([
        (0, 0),
        (bottom, 0),
        (bottom - inset, height),
        (inset, height),
    ])


def edge_directions(polygon: Polygon) -> set:
    """Undirected direction (degrees, mod 180) of every edge of the polygon."""
    coords = list(polygon.exterior.coords)[:-1]
    directions = set()
    for i in range(len(coords)):
        (x0, y0), (x1, y1) = coords[i], coords[(i + 1) % len(coords)]
        theta = math.degrees(math.atan2(y1 - y0, x1 - x0))
        directions.add(round(theta % 180.0, 6))
    return directions


def pairwise_aligned_rotations(polygon: Polygon, target_directions) -> tuple:
    """
    Candidate orientations derived FROM THE GEOMETRY, not hard-coded.

    A part earns its place in a packing by lying flush against something: a
    canvas wall, or a neighbour's edge. Two edges can only be flush if they are
    parallel. So the useful orientations are exactly those that bring some edge
    of this polygon parallel to some edge direction present in the shape set
    (`target_directions`, which includes the canvas' own 0/90 via the
    rectangles). Every angle is taken in both senses (+180) so a part can meet
    that direction from either side.

    We currently call this with target_directions = {0} (see
    build_default_shapes), which lays each edge flat on the horizontal and
    yields 30 distinct variants over the whole shape set.

    Passing the full set of edge directions instead is the richer option: it
    adds the intermediate angles that let two parts with differing slants sit
    flush - e.g. the equilateral triangle's 60 deg edge against the 30/35
    isosceles triangle's 64.6 deg leg, which under {0} can only ever touch at
    a point. That was implemented and MEASURED, and it did not pay off with a
    greedy placer: 258 variants, ~6x the cost per step, and utilisation at 45
    parts went 0.4332 -> 0.4061, because a myopic density score prefers a
    near-horizontal tilt that shaves the bounding box this step while leaving
    an unusable wedge behind. Gating tilted orientations on proven contact
    brought it back to exactly 0.4332 with zero tilted parts chosen at any
    threshold from 0.05 to 0.50 - i.e. tilted orientations are structurally
    unreachable for a greedy step, since tilting almost always grows the
    bounding box and loses on density before contact even matters.
    Worth revisiting once the search has an outer loop that can commit to a
    tilted part and its partner together.

    Sweeping all 360 one-degree rotations was also measured: ~60x the cost per
    step, and the ~350 extra angles align nothing to anything - they are
    tilted copies of these same orientations.

    Duplicates are dropped by ShapeType.__post_init__, so symmetric shapes
    collapse on their own (square -> {0}, equilateral triangle -> {0, 60}).
    """
    angles = set()
    for theta in edge_directions(polygon):
        for target in target_directions:
            angles.add(round((target - theta) % 360.0, 6))
            angles.add(round((target - theta + 180.0) % 360.0, 6))
    return tuple(sorted(angles))


def build_default_shapes() -> list:
    """The exact shape set from the task specification."""
    specs = [
        # (name, polygon)
        ("square_20",       square(20)),
        ("square_25",       square(25)),
        ("rect_30x15",      rectangle(30, 15)),
        ("rect_35x25",      rectangle(35, 25)),
        ("eqtri_5",         equilateral_triangle(5)),
        ("eqtri_30",        equilateral_triangle(30)),
        ("eqtri_40",        equilateral_triangle(40)),
        ("isotri_20_25",    isosceles_triangle(20, 25)),
        ("isotri_30_35",    isosceles_triangle(30, 35)),
        ("trapezium_20_30", trapezium(20, 30, 20)),
    ]
    # Align every edge to the horizontal. Swap this for the union of all shapes'
    # edge directions to get the richer pairwise-aligned set - see the measured
    # trade-off in pairwise_aligned_rotations.__doc__.
    targets = {0.0}

    return [
        ShapeType(id=i, name=name, base_polygon=poly,
                  rotations=pairwise_aligned_rotations(poly, targets))
        for i, (name, poly) in enumerate(specs)
    ]

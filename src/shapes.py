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


@dataclass(eq=False)   # identity-based hash so ShapeType can key the NFP caches
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
        # Pre-compute (cache) every rotated version once.
        for angle in self.rotations:
            self.variants[angle] = create_rotated_local_polygon(
                self.base_polygon, angle
            )

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


# Rotations. Squares are 90-degree symmetric -> a single orientation is enough.
# Everything else gets the four axis-aligned orientations so the solver can
# pair triangles / flip trapeziums to close gaps.
FOUR = (0.0, 90.0, 180.0, 270.0)


def build_default_shapes() -> list:
    """The exact shape set from the task specification."""
    specs = [
        # (name, polygon, rotations)
        ("square_20",       square(20),                       (0.0,)),
        ("square_25",       square(25),                       (0.0,)),
        ("rect_30x15",      rectangle(30, 15),                (0.0, 90.0)),
        ("rect_35x25",      rectangle(35, 25),                (0.0, 90.0)),
        ("eqtri_5",         equilateral_triangle(5),          FOUR),
        ("eqtri_30",        equilateral_triangle(30),         FOUR),
        ("eqtri_40",        equilateral_triangle(40),         FOUR),
        ("isotri_20_25",    isosceles_triangle(20, 25),       FOUR),
        ("isotri_30_35",    isosceles_triangle(30, 35),       FOUR),
        ("trapezium_20_30", trapezium(20, 30, 20),            FOUR),
    ]
    return [
        ShapeType(id=i, name=name, base_polygon=poly, rotations=rot)
        for i, (name, poly, rot) in enumerate(specs)
    ]

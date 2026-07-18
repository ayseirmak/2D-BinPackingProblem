from shapely.affinity import rotate, translate
from shapely.geometry import  Polygon

def create_rotated_local_polygon(
    polygon: Polygon,
    angle_degrees: float
) -> Polygon:
    rotated = rotate(
        polygon,
        angle_degrees,
        origin="centroid",
        use_radians=False
    )

    min_x, min_y, _, _ = rotated.bounds

    return translate(
        rotated,
        xoff=-min_x,
        yoff=-min_y
    )
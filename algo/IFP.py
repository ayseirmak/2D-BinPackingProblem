from shapely.geometry import box
from shapely.geometry import Polygon

def rectangular_ifp(
    moving: Polygon,
    canvas_width: float,
    canvas_height: float
) -> Polygon:
    """
    Region in which the moving polygon's translation reference may lie
    while the polygon remains inside the rectangular canvas.
    """
    min_x, min_y, max_x, max_y = moving.bounds

    if max_x - min_x > canvas_width:
        return Polygon()

    if max_y - min_y > canvas_height:
        return Polygon()

    return box(
        -min_x,
        -min_y,
        canvas_width - max_x,
        canvas_height - max_y
    )
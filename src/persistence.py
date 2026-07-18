"""
Layout persistence so a long run can survive being killed and resume.

Only (shape_id, angle, x, y) is stored - the polygon is rebuilt by translating
the cached canonical variant, so the reconstruction is exact.
"""

import json
import os

from shapely.affinity import translate

from src.layout import Placement

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
LAYOUT_PATH = os.path.join(RESULTS_DIR, "layout.json")


def save_placements(layout, path=LAYOUT_PATH):
    """Atomic write: a kill mid-write can never corrupt the saved layout."""
    data = [
        {"shape_id": p.shape_type.id, "angle": p.rotation, "x": p.x, "y": p.y}
        for p in layout.items
    ]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh)
    os.replace(tmp, path)   # atomic on POSIX


def load_placements(shapes, path=LAYOUT_PATH):
    """Rebuild Placement objects from disk. Returns [] if there is nothing saved."""
    if not os.path.exists(path):
        return []
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return []

    by_id = {s.id: s for s in shapes}
    placements = []
    for rec in data:
        shape = by_id.get(rec["shape_id"])
        if shape is None:
            continue
        angle = rec["angle"]
        poly = translate(shape.variants[angle], xoff=rec["x"], yoff=rec["y"])
        placements.append(Placement(shape, angle, rec["x"], rec["y"], poly))
    return placements

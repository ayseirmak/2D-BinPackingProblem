"""Independent check: no overlaps, everything inside the canvas, area adds up."""

from shapely.geometry import box

from src.shapes import build_default_shapes
from src.persistence import load_placements

EPS = 1e-8
W, H = 200.0, 100.0


def main():
    shapes = build_default_shapes()
    placements = load_placements(shapes)
    canvas = box(0, 0, W, H)

    print(f"placements: {len(placements)}")

    outside = [p for p in placements if not canvas.covers(p.polygon)]
    print(f"outside canvas: {len(outside)}")

    worst = 0.0
    overlaps = 0
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            a, b = placements[i].polygon, placements[j].polygon
            if a.bounds[2] < b.bounds[0] or b.bounds[2] < a.bounds[0]:
                continue
            if a.bounds[3] < b.bounds[1] or b.bounds[3] < a.bounds[1]:
                continue
            area = a.intersection(b).area
            worst = max(worst, area)
            if area > EPS:
                overlaps += 1
    print(f"overlapping pairs: {overlaps}   (worst overlap area {worst:.3e})")

    used = sum(p.polygon.area for p in placements)
    print(f"used area: {used:.2f} / {W*H:.0f}  ->  utilisation {used/(W*H)*100:.2f}%")

    types = {p.shape_type.name for p in placements}
    missing = [s.name for s in shapes if s.name not in types]
    print(f"mandatory types missing: {missing if missing else 'none'}")


if __name__ == "__main__":
    main()

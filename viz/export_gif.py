"""
Render a results/layout.json into an animated GIF that replays the packing
placement by placement (for embedding in the README).

Usage:
    python3 viz/export_gif.py results_simple assets/simple.gif
    python3 viz/export_gif.py results_edge   assets/edge.gif   --frames 140
"""

import os
import sys
import argparse

# allow "from src...." when run as a plain script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from src.shapes import build_default_shapes
from src.persistence import load_placements

CANVAS_W, CANVAS_H = 200.0, 100.0

# tab10 palette, indexed by shape id (matches the matplotlib pictures)
PALETTE = [(31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40),
           (148, 103, 189), (140, 86, 75), (227, 119, 194), (127, 127, 127),
           (188, 189, 34), (23, 190, 207)]


def render_frame(polys_colors, upto, scale, margin):
    """Draw shapes 0..upto; highlight the newest with a thick black outline."""
    img_w = int(CANVAS_W * scale + 2 * margin)
    img_h = int(CANVAS_H * scale + 2 * margin)
    img = Image.new("RGB", (img_w, img_h), "white")
    d = ImageDraw.Draw(img)

    def tx(x, y):                       # world -> pixels, y flipped
        return (margin + x * scale, margin + (CANVAS_H - y) * scale)

    # canvas border
    d.rectangle([tx(0, CANVAS_H), tx(CANVAS_W, 0)], outline=(225, 30, 30), width=3)

    for k in range(upto + 1):
        verts, color = polys_colors[k]
        pts = [tx(x, y) for x, y in verts]
        d.polygon(pts, fill=color, outline=(40, 40, 40))

    # re-outline the newest shape thicker
    verts, _ = polys_colors[upto]
    pts = [tx(x, y) for x, y in verts]
    d.line(pts + [pts[0]], fill=(0, 0, 0), width=3)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("out_path")
    ap.add_argument("--frames", type=int, default=150, help="max GIF frames")
    ap.add_argument("--scale", type=float, default=4.0, help="pixels per unit")
    ap.add_argument("--ms", type=int, default=70, help="ms per frame")
    args = ap.parse_args()

    shapes = build_default_shapes()
    placements = load_placements(shapes, path=os.path.join(args.results_dir, "layout.json"))
    if not placements:
        print(f"no placements in {args.results_dir}/layout.json")
        return

    polys_colors = [
        ([(x, y) for x, y in list(p.polygon.exterior.coords)[:-1]],
         PALETTE[p.shape_type.id % len(PALETTE)])
        for p in placements
    ]

    n = len(polys_colors)
    stride = max(1, (n + args.frames - 1) // args.frames)
    indices = list(range(0, n, stride))
    if indices[-1] != n - 1:
        indices.append(n - 1)                 # always end on the final layout

    margin = 12
    frames = [render_frame(polys_colors, i, args.scale, margin) for i in indices]
    durations = [args.ms] * len(frames)
    durations[-1] = 2500                       # hold the final frame

    os.makedirs(os.path.dirname(args.out_path) or ".", exist_ok=True)
    frames[0].save(args.out_path, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, optimize=True)
    kb = os.path.getsize(args.out_path) // 1024
    print(f"wrote {args.out_path}  ({len(frames)} frames from {n} placements, {kb} KB)")


if __name__ == "__main__":
    main()

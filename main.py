"""
Entry point: run (or resume) the packer, persist progress, draw the layout.

Usage:
    python3 main.py            # resumes from layout.json if present
    ./run_forever.sh           # same, but restarts automatically if killed
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

from src.shapes import build_default_shapes
from algo.greedy import run_packing
from src.persistence import save_placements, load_placements

CANVAS_W = 200.0
CANVAS_H = 100.0
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DONE_FILE = os.path.join(RESULTS_DIR, "DONE")
PNG_PATH = os.path.join(RESULTS_DIR, "layout.png")
PNG_EVERY = 25          # redraw the picture every N placements (drawing is slow)


def plot_layout(layout, path=None):
    path = path or PNG_PATH
    os.makedirs(RESULTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    cmap = plt.get_cmap("tab10")

    for pl in layout.items:
        xs, ys = pl.polygon.exterior.xy
        ax.add_patch(MplPolygon(
            list(zip(xs, ys)), closed=True,
            facecolor=cmap(pl.shape_type.id % 10),
            edgecolor="black", linewidth=0.7, alpha=0.85,
        ))

    ax.plot([0, CANVAS_W, CANVAS_W, 0, 0], [0, 0, CANVAS_H, CANVAS_H, 0],
            color="red", linewidth=2)
    util = layout.used_area / layout.canvas_area
    ax.set_xlim(-5, CANVAS_W + 5)
    ax.set_ylim(-5, CANVAS_H + 5)
    ax.set_aspect("equal")
    ax.set_title(f"Deterministic greedy NFP packing - "
                 f"{len(layout.items)} shapes, utilisation {util*100:.2f}%")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    shapes = build_default_shapes()

    resumed = load_placements(shapes)
    if resumed:
        print(f"resuming from results/layout.json with {len(resumed)} placements")

    def checkpoint(layout):
        save_placements(layout)                       # cheap, every placement
        if len(layout.items) % PNG_EVERY == 0:        # expensive, throttled
            plot_layout(layout)

    layout, utilisation, wasted = run_packing(
        shapes,
        canvas_width=CANVAS_W,
        canvas_height=CANVAS_H,
        K=10,
        use_flexibility=True,
        verbose=True,
        checkpoint_every=1,
        checkpoint_fn=checkpoint,
        initial_placements=resumed,
    )

    save_placements(layout)
    plot_layout(layout)

    print("\n================ RESULT ================")
    print(f"shapes placed      : {len(layout.items)}")
    print(f"canvas utilisation : {utilisation:.4f}  ({utilisation*100:.2f}%)")
    print(f"wasted-space ratio : {wasted:.4f}  ({wasted*100:.2f}%)")

    counts = {}
    for pl in layout.items:
        counts[pl.shape_type.name] = counts.get(pl.shape_type.name, 0) + 1
    print("\nplaced per type:")
    for name in sorted(counts):
        print(f"  {name:16s} x {counts[name]}")

    # Tell the supervisor loop that we finished naturally.
    with open(DONE_FILE, "w") as fh:
        fh.write(f"{len(layout.items)} shapes, utilisation {utilisation:.6f}\n")


if __name__ == "__main__":
    main()

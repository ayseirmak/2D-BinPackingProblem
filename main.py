"""
Entry point: run the packer, print the report, draw the layout.

Usage:
    python3 main.py
"""

import os

import matplotlib
matplotlib.use("Agg")  # headless-safe; comment out to show interactively
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon

from src.shapes import build_default_shapes
from algo.greedy import run_packing

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
LAYOUT_PNG = os.path.join(RESULTS_DIR, "layout.png")

CANVAS_W = 200.0
CANVAS_H = 100.0

# GRASP outer loop. TRIALS=1 gives the plain deterministic greedy.
TRIALS = 12
POOL = 5          # restricted candidate list size for the randomised trials
MAX_PARTS = None  # no cap: a trial now terminates on its own in ~60s


def plot_layout(layout, path=LAYOUT_PNG):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))

    # colour per shape type id
    cmap = plt.get_cmap("tab10")

    for pl in layout.items:
        xs, ys = pl.polygon.exterior.xy
        patch = MplPolygon(
            list(zip(xs, ys)),
            closed=True,
            facecolor=cmap(pl.shape_type.id % 10),
            edgecolor="black",
            linewidth=0.7,
            alpha=0.85,
        )
        ax.add_patch(patch)

    # canvas outline
    ax.plot([0, CANVAS_W, CANVAS_W, 0, 0],
            [0, 0, CANVAS_H, CANVAS_H, 0],
            color="red", linewidth=2)

    ax.set_xlim(-5, CANVAS_W + 5)
    ax.set_ylim(-5, CANVAS_H + 5)
    ax.set_aspect("equal")
    util = layout.used_area / layout.canvas_area
    ax.set_title(f"NFP packing, GRASP over greedy  -  "
                 f"{len(layout.items)} parts, {util * 100:.2f}% utilised")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    shapes = build_default_shapes()

    layout, utilisation, wasted = run_packing(
        shapes,
        canvas_width=CANVAS_W,
        canvas_height=CANVAS_H,
        trials=TRIALS,
        pool=POOL,
        max_parts=MAX_PARTS,
        verbose=True,
        checkpoint_fn=lambda lay: plot_layout(lay, path=LAYOUT_PNG),
    )

    print("\n================ RESULT ================")
    print(f"shapes placed      : {len(layout.items)}")
    print(f"canvas utilisation : {utilisation:.4f}  ({utilisation*100:.2f}%)")
    print(f"wasted-space ratio : {wasted:.4f}  ({wasted*100:.2f}%)")

    # count per type
    counts = {}
    for pl in layout.items:
        counts[pl.shape_type.name] = counts.get(pl.shape_type.name, 0) + 1
    print("\nplaced per type:")
    for name in sorted(counts):
        print(f"  {name:16s} x {counts[name]}")

    plot_layout(layout)


if __name__ == "__main__":
    main()

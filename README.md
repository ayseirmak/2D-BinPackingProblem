# GRASP NFP Packer

A GRASP solver for 2D irregular packing (nesting): fit as many convex polygons
as possible into a fixed 200 × 100 canvas, without overlaps and without leaving
the boundary.

Placement is exact, not sampled — candidate positions come from the
**No-Fit Polygon** (NFP) and **Inner-Fit Polygon** (IFP) boundaries, so the
packer only ever considers positions where a shape touches something.

**Current result: 254 shapes placed, 90.11 % canvas utilisation.**

Non-overlap and containment are enforced during construction — candidates come
from the forbidden-region union, so an overlapping position is never generated.
There is no independent post-hoc validator on this branch.

![Layout](results/layout.png)

> This branch is a reimplementation of the deterministic packer on `main`
> (905 shapes, 89.37 %). Two things changed: the objective function was replaced,
> and a randomised outer loop was added on top of the greedy construction. The
> checkpoint/resume layer from `main` is not part of this branch.

## How it works

### Inner loop — one greedy construction

Two phases:

1. **Coverage** — place every required shape type at least once.
2. **Fill** — repeat any type until nothing fits.

Each step enumerates every feasible translation of every eligible
(type, rotation) pair from the forbidden-region union, then ranks them by a
**lexicographic score** (`algo/greedy.py:_score`):

```
utilisation      → prefer the largest part that still fits
-max_y, -max_x   → push it as low, then as far left, as possible
id / rot / x / y → deterministic tie-breaks
```

That is first-fit-decreasing plus bottom-left-fill: take the biggest piece that
fits, shove it into the bottom-left corner.

### Why the objective changed

The previous objective was **bounding-box density** (`A_used / bbox_area`), and
it turned out to be actively harmful. A small part never grows the cluster's
bounding box, so it *always* raises density; a large part usually grows the box,
so it *always* lowers it. The score therefore systematically rewarded the
smallest available part — a capped 60-part run placed 45 of the 10.8-area
triangles, 5.5 % of the packed area (`results/grasp.log`, 44.14 % utilisation).

Three separate attempts to fix the packing around that score — a richer rotation
set, a contact filter, and the GRASP outer loop itself — all converged to the
same utilisation, because each was following the same broken compass. Density is
still computed in `algo/metrics.py` and reported; it just isn't optimised for.

### Outer loop — GRASP

A single greedy pass samples exactly one point in the space of placement
sequences and commits to its early decisions irrevocably. That is where the loss
concentrates: the first few large parts decide whether the rest fits. Every
competitive nesting solver spends its budget revisiting those early decisions —
by re-ordering (genetic algorithms: SVGnest, Deepnest), by relaxing feasibility
and repairing (guided local search: sparrow), or by backtracking (tree search:
PackingSolver).

GRASP is the cheapest member of that family and needs no new geometry. At each
step, instead of always taking the best candidate, pick uniformly at random from
the `pool` best ones — a restricted candidate list. Repeat the whole construction
`trials` times from different seeds and keep the best layout.

**Trial 0 always runs with `pool=1`**, i.e. the plain deterministic greedy, so
the result can never be worse than the greedy baseline. On the current run the
randomisation paid off — trial 0 reached 89.30 %, trial 5 found 90.11 %
(`results/grasp_b.log`).

## Layout

```
main.py             entry point: run the packer, print the report, draw the layout

src/                geometry and data model
  shapes.py           shape types + rotation variants
  layout.py           the canvas, placements, spatial index
  rotation_polygon.py rotate a polygon into a canonical local frame

algo/               the packing algorithm
  greedy.py           greedy inner loop + GRASP outer loop
  nfp.py              no-fit polygon (convex)
  nfp_cache.py        cached NFPs for placed shapes
  nfp_candidate.py    candidate positions from the forbidden-region union
  IFP.py              inner-fit polygon (canvas containment)
  metrics.py          cluster density and scoring metrics

results/            output: layout.png, run logs
docs/               design notes and pseudocode
```

## Requirements

```bash
pip install shapely matplotlib
```

## Usage

```bash
python3 main.py
```

Tuning knobs are constants at the top of `main.py`:

| constant    | default | meaning                                                 |
|-------------|---------|---------------------------------------------------------|
| `TRIALS`    | `12`    | GRASP constructions; `1` = plain deterministic greedy    |
| `POOL`      | `5`     | restricted candidate list size for the randomised trials |
| `MAX_PARTS` | `None`  | cap on parts per trial; `None` = run until nothing fits  |

`results/layout.png` is redrawn whenever a trial improves on the best layout so
far, so you can watch progress mid-run.

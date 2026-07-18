"""
NFP packer: a greedy inner loop wrapped in a GRASP outer loop.

INNER LOOP (_run_once) - one construction pass:
  Phase 1 : place every required type at least once.
  Phase 2 : repeat any type until nothing fits.
  Per step:
    1. For every eligible (type, rotation), build the feasible candidate
       translations from the forbidden-region union (see nfp_candidate).
    2. Score each candidate with ONE objective: the bounding-box density of
       the whole cluster after adding it (see metrics.cluster_density).
    3. Commit one candidate (see below).

OUTER LOOP (run_packing) - GRASP:
  A single greedy pass samples exactly ONE point in the space of placement
  sequences, and commits to its early decisions irrevocably. That is where the
  loss concentrates: the first few large parts decide whether the rest fits.
  Every competitive nesting solver spends its budget revisiting those early
  decisions - by re-ordering (genetic algorithms, as in SVGnest/Deepnest), by
  relaxing feasibility and repairing (guided local search, as in sparrow), or
  by backtracking (tree search, as in PackingSolver).

  GRASP is the cheapest member of that family and needs no new geometry: at
  each step, instead of always taking the best candidate, pick uniformly at
  random from the `pool` best ones (a restricted candidate list). Repeat the
  whole construction `trials` times from different seeds and keep the best
  layout. Trial 0 always runs with pool=1, i.e. the plain deterministic greedy,
  so the result can never be worse than the greedy baseline.
"""

import random

from shapely.geometry import box

from src.layout import Layout, Placement
from algo.nfp_candidate import candidate_translations_fast
from algo.metrics import cluster_density


def _score(m, shape_id, rot_index, x, y):
    """
    Lexicographic score, highest wins.

    utilisation  - area packed so far, over the fixed canvas area. Since the
                   already-placed area is constant within a step, this simply
                   prefers the LARGEST part that still fits.
    max_y, max_x - bottom-left bias. utilisation is identical for every
                   position of the same part, so these actually choose the
                   position: as low, then as far left, as possible.
    the rest     - pure tie-breakers so a run is reproducible.

    Together this is first-fit-decreasing + bottom-left-fill, a long-standing
    packing heuristic: take the biggest piece that fits, push it into the
    bottom-left corner.

    Bounding-box density (A_used / bbox_area) was the objective before, and it
    was measured to be actively harmful here: a small part never grows the
    cluster's bounding box, so it ALWAYS raises density, while a large part
    usually grows the box and so ALWAYS lowers it. The score therefore
    systematically rewarded the smallest available part - a run would place 45
    of the 10.8-area triangles (5.5% of the packed area) out of 60 parts.
    Three separate attempts to fix the packing around that score - a richer
    rotation set, a contact filter, and a GRASP outer loop - all converged to
    the same utilisation, because each of them was following the same broken
    compass. Density is still computed in metrics.cluster_density and is
    reported, just not optimised for.
    """
    return (
        round(m["utilisation"], 10),
        -round(m["max_y"], 10),
        -round(m["max_x"], 10),
        -shape_id,
        -rot_index,
        -round(x, 10),
        -round(y, 10),
    )


def _scored_candidates(layout, types_to_try, canvas):
    """Every feasible placement of every eligible type, with its score."""
    out = []
    for shape in types_to_try:
        for rot_index, angle in enumerate(shape.rotations):
            moving = shape.variants[angle]
            for x, y, poly in candidate_translations_fast(
                layout, shape, angle, moving, canvas
            ):
                m = cluster_density(layout, poly)
                out.append((
                    _score(m, shape.id, rot_index, x, y),
                    Placement(shape, angle, x, y, poly),
                ))
    return out


def _pick(layout, types_to_try, canvas, rng, pool):
    """Best candidate, or a random one from the `pool` best (GRASP)."""
    scored = _scored_candidates(layout, types_to_try, canvas)
    if not scored:
        return None
    if pool <= 1:
        return max(scored, key=lambda s: s[0])[1]
    scored.sort(key=lambda s: s[0], reverse=True)
    return rng.choice(scored[:pool])[1]


def _run_once(shapes, canvas, canvas_width, canvas_height,
              rng, pool, max_parts, verbose):
    """One full construction pass. Returns the Layout."""
    layout = Layout(canvas_width, canvas_height)

    # ---------------- PHASE 1: every type at least once ---------------- #
    remaining = list(shapes)
    while remaining:
        best = _pick(layout, remaining, canvas, rng, pool)
        if best is None:
            names = ", ".join(t.name for t in remaining)
            raise RuntimeError(f"No feasible placement left for: {names}")
        layout.add(best)
        remaining = [t for t in remaining if t.id != best.shape_type.id]
        if verbose:
            print(f"  [mandatory] {best.shape_type.name:16s} @ {best.rotation:5.0f}  "
                  f"util={layout.used_area / layout.canvas_area:.4f}")

    # ---------------- PHASE 2: repetition until nothing fits ------------ #
    while max_parts is None or len(layout.items) < max_parts:
        best = _pick(layout, shapes, canvas, rng, pool)
        if best is None:
            break
        layout.add(best)

    return layout


def run_packing(shapes, canvas_width=200.0, canvas_height=100.0,
                trials=1, pool=4, seed=0, max_parts=None,
                verbose=True, checkpoint_every=0, checkpoint_fn=None):
    """
    Run `trials` GRASP constructions and return the best layout found.

    trials=1 reproduces the plain deterministic greedy exactly.
    """
    canvas = box(0, 0, canvas_width, canvas_height)

    best_layout = None
    best_util = -1.0

    for trial in range(trials):
        # Trial 0 is the deterministic greedy baseline; the rest are randomised.
        trial_pool = 1 if trial == 0 else pool
        rng = random.Random(seed + trial)

        layout = _run_once(
            shapes, canvas, canvas_width, canvas_height,
            rng, trial_pool, max_parts, verbose=(verbose and trial == 0),
        )
        util = layout.used_area / layout.canvas_area

        improved = util > best_util
        if improved:
            best_layout, best_util = layout, util
            # Pure observability hook; does not affect selection or scoring.
            if checkpoint_fn:
                checkpoint_fn(layout)

        if verbose:
            print(f"[trial {trial:3d}] pool={trial_pool:2d}  "
                  f"parts={len(layout.items):3d}  util={util:.4f}"
                  f"{'   <-- best' if improved else ''}", flush=True)

    return best_layout, best_util, 1.0 - best_util
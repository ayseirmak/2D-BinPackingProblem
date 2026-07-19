"""
Deterministic greedy NFP packer (two-stage scoring).

Phase 1 : place every required type at least once (with a hard feasibility gate
          so a mandatory shape is never stranded).
Phase 2 : repeat any type until nothing fits.

Per step:
  1. Generate every feasible candidate (forbidden-region union) for the eligible
     types and score it with the CHEAP O(1) metrics.
  2. Shortlist: global top-N by cheap score + per-type top-2 (so no type is
     accidentally dropped).
  3. For the shortlist only, run the EXPENSIVE stage: mandatory feasibility gate,
     exact contact ratio, capped future flexibility -> full lexicographic score.
  4. Place the best.
"""

from shapely.geometry import box

from src.layout import Layout, Placement
from algo.nfp_candidate import candidate_translations_fast
from algo.metrics import (
    cheap_metrics,
    contact_ratio,
    count_feasible_placements,
    future_flexibility,
)

GLOBAL_KEEP = 20
PER_TYPE_KEEP = 2


def _cheap_score(m, shape_id, rot_index, x, y):
    return (
        round(m["density"], 10),
        round(m["utilisation"], 10),
        -round(m["max_y"], 10),
        -round(m["max_x"], 10),
        -shape_id,
        -rot_index,
        -round(x, 10),
        -round(y, 10),
    )


def _generate_scored_candidates(layout, types_to_try, canvas):
    """All feasible candidates with cheap score attached."""
    records = []
    for shape in types_to_try:
        for rot_index, angle in enumerate(shape.rotations):
            moving = shape.variants[angle]
            for x, y, poly in candidate_translations_fast(layout, shape, angle, moving, canvas):
                m = cheap_metrics(layout, poly)
                records.append({
                    "shape": shape, "angle": angle, "rot_index": rot_index,
                    "x": x, "y": y, "poly": poly, "cheap": m,
                    "cheap_score": _cheap_score(m, shape.id, rot_index, x, y),
                })
    return records


def _shortlist(records):
    """Global top-N by cheap score plus per-type top-2, de-duplicated."""
    by_cheap = sorted(records, key=lambda r: r["cheap_score"], reverse=True)
    keep = list(by_cheap[:GLOBAL_KEEP])

    per_type = {}
    for r in by_cheap:
        sid = r["shape"].id
        bucket = per_type.setdefault(sid, [])
        if len(bucket) < PER_TYPE_KEEP:
            bucket.append(r)
            keep.append(r)

    seen, unique = set(), []
    for r in keep:
        key = (r["shape"].id, r["angle"], round(r["x"], 8), round(r["y"], 8))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _passes_gate(layout, record, gate_types, canvas):
    """Every still-required OTHER type must keep >=1 feasible placement on L'."""
    l_prime = layout.added(Placement(
        record["shape"], record["angle"], record["x"], record["y"], record["poly"]
    ))
    for r in gate_types:
        if r.id == record["shape"].id:
            continue
        if count_feasible_placements(l_prime, r, canvas, 1) == 0:
            return False
    return record  # truthy; caller can reuse (we recompute l_prime lazily below)


def _simple_score(layout, record, canvas, contact_weight):
    """
    Simplified score: weighted sum of bounding-box density and contact ratio.

        score = bbox_density + contact_weight * contact_ratio

    No future flexibility, no fragmentation, no bottom-left bias. Rotation and
    position are chosen purely by this score, so for each position the rotation
    that maximises contact naturally wins. Contact is measured only against the
    parts the spatial index says are adjacent (same result, much cheaper).
    """
    density = record["cheap"]["density"]
    contact = contact_ratio(record["poly"], layout.nearby(record["poly"]), canvas)
    return (
        round(density + contact_weight * contact, 12),
        # deterministic tie-break only (NOT a bottom-left preference):
        -record["shape"].id,
        -record["rot_index"],
        -round(record["x"], 10),
        -round(record["y"], 10),
    )


def _full_score(layout, record, flexibility_types, canvas, K):
    m = record["cheap"]
    l_prime = layout.added(Placement(
        record["shape"], record["angle"], record["x"], record["y"], record["poly"]
    ))
    flex = future_flexibility(l_prime, flexibility_types, canvas, K)
    contact = contact_ratio(record["poly"], layout.polygons, canvas)
    return (
        round(m["density"], 10),
        round(m["utilisation"], 10),
        round(flex, 10),
        round(contact, 10),
        -round(m["max_y"], 10),
        -round(m["max_x"], 10),
        -record["shape"].id,
        -record["rot_index"],
        -round(record["x"], 10),
        -round(record["y"], 10),
    )


def _pick_best(layout, records, gate_types, flexibility_types, canvas, K,
               use_flexibility, simple=False, contact_weight=0.25):
    """Shortlist -> gate -> full score -> best record (or None)."""
    shortlist = _shortlist(records)

    # Simplified path: no gate, no flexibility, no fragmentation, and crucially
    # NO hidden bottom-left bias from the shortlist. Because contact_ratio is in
    # [0, 1], the contact term can shift the score by at most contact_weight, so a
    # candidate whose density is more than contact_weight below the best can never
    # win. We evaluate the exact score (with contact) for exactly those contenders
    # and pick the max - this lets a higher-contact placement beat a lower one at
    # equal density instead of being dropped for being higher up / less bottom-left.
    if simple:
        if not records:
            return None
        max_density = max(r["cheap"]["density"] for r in records)
        contenders = [r for r in records
                      if r["cheap"]["density"] >= max_density - contact_weight]
        scored = [(_simple_score(layout, r, canvas, contact_weight), r) for r in contenders]
        return max(scored, key=lambda s: s[0])[1]

    scored = []
    for r in shortlist:
        if gate_types and not _passes_gate(layout, r, gate_types, canvas):
            continue
        if use_flexibility:
            score = _full_score(layout, r, flexibility_types, canvas, K)
        else:
            score = _full_score(layout, r, [], canvas, K)  # flex neutral (=1.0)
        scored.append((score, r))

    # Fallback: if the whole shortlist failed the gate, scan the rest in cheap
    # order until one passes (guarantees we don't give up prematurely).
    if not scored and gate_types:
        for r in sorted(records, key=lambda r: r["cheap_score"], reverse=True):
            if _passes_gate(layout, r, gate_types, canvas):
                scored.append((_full_score(layout, r, flexibility_types, canvas, K), r))
                break

    if not scored:
        return None
    return max(scored, key=lambda s: s[0])[1]


def run_packing(shapes, canvas_width=200.0, canvas_height=100.0,
                K=10, use_flexibility=True, verbose=True,
                checkpoint_every=0, checkpoint_fn=None,
                initial_placements=None,
                simple=False, contact_weight=0.25):
    canvas = box(0, 0, canvas_width, canvas_height)
    layout = Layout(canvas_width, canvas_height)

    # Resume: replay previously saved placements. The algorithm is deterministic,
    # so continuing from here yields exactly the same sequence as an unbroken run.
    for placement in (initial_placements or []):
        layout.add(placement)
    if initial_placements and verbose:
        print(f"[resume   ] restored {len(layout.items)} placements, "
              f"util={layout.used_area / layout.canvas_area:.4f}")

    def _checkpoint():
        # Pure observability/persistence hook; does not affect selection.
        if checkpoint_every and checkpoint_fn and len(layout.items) % checkpoint_every == 0:
            checkpoint_fn(layout)

    # ---------------- PHASE 1: mandatory ---------------- #
    placed_ids = {p.shape_type.id for p in layout.items}
    remaining = [t for t in shapes if t.id not in placed_ids]
    while remaining:
        records = _generate_scored_candidates(layout, remaining, canvas)
        best = _pick_best(
            layout, records,
            gate_types=remaining, flexibility_types=remaining,
            canvas=canvas, K=K, use_flexibility=use_flexibility,
            simple=simple, contact_weight=contact_weight,
        )
        if best is None:
            raise RuntimeError(
                "Deterministic greedy path could not place all mandatory shapes."
            )
        layout.add(Placement(best["shape"], best["angle"], best["x"], best["y"], best["poly"]))
        remaining = [t for t in remaining if t.id != best["shape"].id]
        if verbose:
            print(f"[mandatory] {best['shape'].name:16s} @ {best['angle']:5.0f}  "
                  f"util={layout.used_area / layout.canvas_area:.4f}")
        _checkpoint()

    # ---------------- PHASE 2: repetition ---------------- #
    while True:
        records = _generate_scored_candidates(layout, shapes, canvas)
        best = _pick_best(
            layout, records,
            gate_types=[], flexibility_types=shapes,
            canvas=canvas, K=K, use_flexibility=use_flexibility,
            simple=simple, contact_weight=contact_weight,
        )
        if best is None:
            break
        layout.add(Placement(best["shape"], best["angle"], best["x"], best["y"], best["poly"]))
        if verbose:
            print(f"[repeat   ] {best['shape'].name:16s} @ {best['angle']:5.0f}  "
                  f"util={layout.used_area / layout.canvas_area:.4f}")
        _checkpoint()

    utilisation = layout.used_area / layout.canvas_area
    return layout, utilisation, 1.0 - utilisation

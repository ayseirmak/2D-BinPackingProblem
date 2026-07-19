"""
Base-NFP cache (the PRECOMPUTE step).

We compute NFP once for each (fixed_type, fixed_rotation, moving_type,
moving_rotation) using the canonical local polygons, then reuse it for every
placed instance: because NFP(A + t, B) = NFP(A, B) + t, a placed part's NFP is
just the base NFP translated by the part's placement offset.
"""

from shapely.affinity import translate

from algo.nfp import convex_nfp

_BASE_NFP = {}


def base_nfp(fixed_type, fixed_rotation, moving_type, moving_rotation):
    """Cached NFP of the two canonical (origin-anchored) local polygons."""
    key = (fixed_type.id, fixed_rotation, moving_type.id, moving_rotation)
    nfp = _BASE_NFP.get(key)
    if nfp is None:
        nfp = convex_nfp(
            fixed_type.variant(fixed_rotation),
            moving_type.variant(moving_rotation),
        )
        _BASE_NFP[key] = nfp
    return nfp


def placed_nfp(placement, moving_type, moving_rotation):
    """NFP between an already-placed part and the moving variant, in canvas coords."""
    base = base_nfp(placement.shape_type, placement.rotation, moving_type, moving_rotation)
    return translate(base, xoff=placement.x, yoff=placement.y)

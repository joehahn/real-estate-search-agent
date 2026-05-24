"""Deterministic filtering and scoring of normalized listings against a wishlist.

Two stages, mirroring the wave-rider split of "rules vs judgment":

1. Hard filters: drop any listing that fails a wishlist hard constraint
   (zip already guaranteed by the API call, plus price/beds/baths/acres/type/age).
   Each drop is logged with a reason so the run is auditable.

2. Soft scoring: each survivor gets a 0..1 score per weighted dimension, combined
   into a single weighted score in [0, 100]. The score is fully explainable: we
   return the per-dimension contributions so the report can say WHY a home ranked
   where it did. No LLM is involved at this stage; ranking is reproducible.

The Claude `property-analyst` subagent runs AFTER this, only on the top N survivors,
to add the qualitative signal (schools, flood risk, commute, red flags) that no
structured feed captures.
"""
from __future__ import annotations

from .wishlist import Wishlist


def passes_hard_filters(home: dict, w: Wishlist) -> tuple[bool, str | None]:
    if w.property_types and home.get("property_type") not in w.property_types:
        return False, f"property_type {home.get('property_type')} not in {w.property_types}"
    price = home.get("price")
    if price is None:
        return False, "no price"
    if w.price_max and price > w.price_max:
        return False, f"price {price:.0f} > max {w.price_max:.0f}"
    if price < w.price_min:
        return False, f"price {price:.0f} < min {w.price_min:.0f}"
    if w.bedrooms_min and (home.get("bedrooms") or 0) < w.bedrooms_min:
        return False, f"bedrooms {home.get('bedrooms')} < {w.bedrooms_min}"
    if w.bathrooms_min and (home.get("bathrooms") or 0) < w.bathrooms_min:
        return False, f"bathrooms {home.get('bathrooms')} < {w.bathrooms_min}"
    if w.acres_min and (home.get("acres") or 0) < w.acres_min:
        return False, f"acres {home.get('acres')} < {w.acres_min}"
    if w.max_days_on_market is not None and home.get("days_on_market") is not None:
        if home["days_on_market"] > w.max_days_on_market:
            return False, f"days_on_market {home['days_on_market']} > {w.max_days_on_market}"
    return True, None


def _minmax(values: list[float]) -> tuple[float, float]:
    vals = [v for v in values if v is not None]
    return (min(vals), max(vals)) if vals else (0.0, 0.0)


def _norm(v, lo, hi, *, higher_is_better: bool) -> float:
    """Scale v into [0,1] across the candidate pool. Flat pool -> 0.5 (neutral)."""
    if v is None:
        return 0.0
    if hi == lo:
        return 0.5
    frac = (v - lo) / (hi - lo)
    return frac if higher_is_better else 1.0 - frac


# Each dimension: which normalized field, and whether higher raw value is better.
_DIMS = {
    "price": ("price", False),
    "acres": ("acres", True),
    "square_footage": ("sqft", True),
    "price_per_sqft": ("price_per_sqft", False),
    "bedrooms": ("bedrooms", True),
    "bathrooms": ("bathrooms", True),
    "freshness": ("days_on_market", False),
}


def score_candidates(homes: list[dict], w: Wishlist) -> list[dict]:
    """Attach a `score` (0..100) and `score_breakdown` to each home; return sorted desc."""
    if not homes:
        return []

    total_weight = sum(w.weights.values()) or 1.0
    ranges = {
        dim: _minmax([h.get(field) for h in homes])
        for dim, (field, _) in _DIMS.items()
    }

    for h in homes:
        breakdown = {}
        score = 0.0
        for dim, weight in w.weights.items():
            if dim not in _DIMS or weight == 0:
                continue
            field, higher = _DIMS[dim]
            lo, hi = ranges[dim]
            unit = _norm(h.get(field), lo, hi, higher_is_better=higher)
            contribution = (weight / total_weight) * unit
            breakdown[dim] = round(contribution * 100, 1)
            score += contribution
        h["score"] = round(score * 100, 1)
        h["score_breakdown"] = breakdown

    return sorted(homes, key=lambda h: h["score"], reverse=True)


def filter_and_score(raw_normalized: list[dict], w: Wishlist):
    """Return (ranked_survivors, dropped) where dropped is [(home, reason), ...]."""
    survivors, dropped = [], []
    for h in raw_normalized:
        ok, reason = passes_hard_filters(h, w)
        (survivors if ok else dropped).append(h if ok else (h, reason))
    return score_candidates(survivors, w), dropped

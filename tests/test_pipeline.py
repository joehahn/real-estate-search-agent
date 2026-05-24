"""Tests for the deterministic core: parsing, normalization, filtering, scoring."""
from __future__ import annotations

from src.normalize import normalize
from src.scoring import filter_and_score
from src.wishlist import Wishlist

RAW = [
    {  # good match: cheap, big lot
        "id": "a", "formattedAddress": "1 Oak Ln, Cedar Park, TX 78613",
        "zipCode": 78613, "latitude": 30.5, "longitude": -97.8,
        "propertyType": "Single Family", "price": 500000, "bedrooms": 4,
        "bathrooms": 3, "squareFootage": 2500, "lotSize": 43560, "daysOnMarket": 5,
    },
    {  # too expensive -> dropped
        "id": "b", "formattedAddress": "2 Elm St, Cedar Park, TX 78613",
        "zipCode": 78613, "propertyType": "Single Family", "price": 900000,
        "bedrooms": 5, "bathrooms": 4, "squareFootage": 4000, "lotSize": 21780,
        "daysOnMarket": 40,
    },
    {  # too few beds -> dropped
        "id": "c", "formattedAddress": "3 Pine Ct, Cedar Park, TX 78613",
        "zipCode": 78613, "propertyType": "Single Family", "price": 400000,
        "bedrooms": 2, "bathrooms": 1, "squareFootage": 1200, "lotSize": 8000,
        "daysOnMarket": 10,
    },
    {  # ok match: pricier, smaller lot than home a
        "id": "d", "formattedAddress": "4 Birch Rd, Cedar Park, TX 78613",
        "zipCode": 78613, "propertyType": "Single Family", "price": 650000,
        "bedrooms": 4, "bathrooms": 3, "squareFootage": 2800, "lotSize": 17424,
        "daysOnMarket": 20,
    },
]

WISH = Wishlist(
    zip_codes=["78613"], price_min=0, price_max=750000, bedrooms_min=3,
    bathrooms_min=2, acres_min=0.25, property_types=["Single Family"],
    max_days_on_market=None,
    weights={"price": 0.3, "acres": 0.3, "square_footage": 0.2, "freshness": 0.2},
    enrich_top_n=8,
)


def test_normalize_converts_lot_to_acres():
    n = normalize(RAW[0])
    assert n["acres"] == 1.0           # 43560 sqft == 1 acre
    assert n["price_per_sqft"] == 200.0  # 500000 / 2500


def test_hard_filters_drop_expected():
    ranked, dropped = filter_and_score([normalize(r) for r in RAW], WISH)
    ids = {h["id"] for h in ranked}
    assert ids == {"a", "d"}           # b too pricey, c too few beds
    assert len(dropped) == 2


def test_scoring_orders_better_match_first():
    ranked, _ = filter_and_score([normalize(r) for r in RAW], WISH)
    # Home a is cheaper, bigger lot, and fresher than d -> should rank first.
    assert ranked[0]["id"] == "a"
    assert ranked[0]["score"] >= ranked[1]["score"]
    # Breakdown contributions sum to roughly the total score.
    a = ranked[0]
    assert abs(sum(a["score_breakdown"].values()) - a["score"]) < 0.5

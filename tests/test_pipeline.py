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
    zip_codes=["78613"], region=None, center=None, center_lat=None, center_lon=None,
    radius_miles=None, prefer_near=None, prefer_lat=None, prefer_lon=None,
    price_min=0, price_max=750000, bedrooms_min=3,
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


def test_provider_factory_selects_rentcast_and_realtor():
    from src.providers import get_provider
    from src.providers.rentcast import RentCastProvider
    from src.providers.realtor_rapidapi import RealtorRapidAPIProvider
    assert isinstance(get_provider("rentcast"), RentCastProvider)
    assert isinstance(get_provider("realtor"), RealtorRapidAPIProvider)


def test_unknown_provider_raises():
    import pytest
    from src.providers import get_provider
    with pytest.raises(ValueError):
        get_provider("zillow")


def test_realtor_stub_refuses_until_configured():
    import pytest
    from src.providers.realtor_rapidapi import RealtorRapidAPIProvider
    with pytest.raises((NotImplementedError, Exception)):
        RealtorRapidAPIProvider(api_key=None).search_sale("78613")


def test_normalize_captures_listing_identity_and_history():
    raw = {
        "formattedAddress": "9 Test Rd, Knoxville, TN 37934", "zipCode": 37934,
        "propertyType": "Single Family", "price": 900000, "bedrooms": 5,
        "bathrooms": 3, "squareFootage": 3000, "lotSize": 43560, "county": "Knox",
        "mlsNumber": "1234567", "mlsName": "EastTennessee",
        "listingAgent": {"name": "Jane Doe", "phone": "8655551212", "email": "j@x.com"},
        "listingOffice": {"name": "Acme Realty"},
        "history": {
            "2026-01-01": {"event": "Sale Listing", "price": 950000, "listedDate": "2026-01-01T00:00:00.000Z"},
            "2026-03-01": {"event": "Price Change", "price": 900000, "listedDate": "2026-03-01T00:00:00.000Z"},
        },
    }
    n = normalize(raw)
    assert n["mls_number"] == "1234567"
    assert n["listing_agent"]["phone"] == "8655551212"
    assert n["listing_office"]["name"] == "Acme Realty"
    assert n["county"] == "Knox"
    assert [e["price"] for e in n["price_history"]] == [950000.0, 900000.0]  # date-sorted
    assert n["price_cut"] is True   # current 900k < earlier 950k


def test_search_mode_detection():
    import dataclasses
    zip_w = dataclasses.replace(WISH)
    assert zip_w.search_mode == "zips"
    radius_w = dataclasses.replace(WISH, zip_codes=[], center="downtown Knoxville, TN",
                                   center_lat=35.96, center_lon=-83.92, radius_miles=25)
    assert radius_w.search_mode == "radius"


def test_proximity_dimension_rewards_closer_homes():
    import dataclasses
    # Two identical homes except location; prefer point sits on top of the "near" one.
    near = {"id": "near", "formattedAddress": "near", "zipCode": 1, "latitude": 35.92,
            "longitude": -84.05, "propertyType": "Single Family", "price": 800000,
            "bedrooms": 5, "bathrooms": 3, "squareFootage": 3000, "lotSize": 43560}
    far = {**near, "id": "far", "latitude": 36.5, "longitude": -83.0}
    w = dataclasses.replace(
        WISH, price_max=1000000, bedrooms_min=5, acres_min=0.5,
        prefer_near="X", prefer_lat=35.92, prefer_lon=-84.05,
        weights={"proximity": 1.0},
    )
    ranked, _ = filter_and_score([normalize(near), normalize(far)], w)
    assert ranked[0]["id"] == "near"
    assert ranked[0]["distance_pref_mi"] < ranked[1]["distance_pref_mi"]


def test_proximity_weight_dropped_when_no_prefer_point():
    # With no prefer point, a proximity weight must not blow up or dominate.
    ranked, _ = filter_and_score([normalize(r) for r in RAW],
                                 __import__("dataclasses").replace(
                                     WISH, weights={"price": 0.5, "proximity": 0.5}))
    assert "proximity" not in ranked[0]["score_breakdown"]

"""Normalize raw RentCast sale listings into a stable internal schema.

RentCast returns lot size in square feet; we convert to acres. We also derive
price-per-square-foot and a clean address. Missing fields are tolerated (set to None)
so a sparse listing still flows through scoring instead of crashing.
"""
from __future__ import annotations

SQFT_PER_ACRE = 43560.0


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _hoa_fee(listing: dict):
    hoa = listing.get("hoa")
    if isinstance(hoa, dict):
        return _num(hoa.get("fee"))
    return _num(hoa)


def normalize(listing: dict) -> dict:
    price = _num(listing.get("price"))
    sqft = _num(listing.get("squareFootage"))
    lot_sqft = _num(listing.get("lotSize"))
    acres = round(lot_sqft / SQFT_PER_ACRE, 3) if lot_sqft else None
    ppsf = round(price / sqft, 1) if price and sqft else None

    return {
        "id": listing.get("id") or listing.get("formattedAddress"),
        "address": listing.get("formattedAddress") or listing.get("addressLine1"),
        "city": listing.get("city"),
        "state": listing.get("state"),
        "zip": str(listing.get("zipCode")) if listing.get("zipCode") else None,
        "lat": _num(listing.get("latitude")),
        "lon": _num(listing.get("longitude")),
        "property_type": listing.get("propertyType"),
        "price": price,
        "bedrooms": _num(listing.get("bedrooms")),
        "bathrooms": _num(listing.get("bathrooms")),
        "sqft": sqft,
        "acres": acres,
        "price_per_sqft": ppsf,
        "year_built": _num(listing.get("yearBuilt")),
        "days_on_market": _num(listing.get("daysOnMarket")),
        "listed_date": listing.get("listedDate"),
        "hoa_fee": _hoa_fee(listing),
        "status": listing.get("status"),
    }

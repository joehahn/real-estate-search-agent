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


def _contact(node) -> dict | None:
    """Pull name/phone/email/website from a RentCast agent/office object."""
    if not isinstance(node, dict):
        return None
    out = {k: node.get(k) for k in ("name", "phone", "email", "website") if node.get(k)}
    return out or None


def _price_history(listing: dict) -> list[dict]:
    """Flatten RentCast's `history` dict into a date-sorted list of events.

    RentCast keys `history` by date string, each value an event with price and type.
    We surface this so the report can show price cuts and the true listing timeline.
    """
    hist = listing.get("history")
    if not isinstance(hist, dict):
        return []
    events = []
    for date, ev in hist.items():
        if isinstance(ev, dict):
            events.append({
                "date": ev.get("listedDate", date)[:10] if ev.get("listedDate") else date,
                "event": ev.get("event"),
                "price": _num(ev.get("price")),
            })
    return sorted(events, key=lambda e: e["date"])


def normalize(listing: dict) -> dict:
    price = _num(listing.get("price"))
    sqft = _num(listing.get("squareFootage"))
    lot_sqft = _num(listing.get("lotSize"))
    acres = round(lot_sqft / SQFT_PER_ACRE, 3) if lot_sqft else None
    ppsf = round(price / sqft, 1) if price and sqft else None
    history = _price_history(listing)
    # A price cut is any later event priced below the first recorded price.
    prices = [e["price"] for e in history if e["price"]]
    price_cut = bool(prices) and price is not None and price < max(prices)

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
        "county": listing.get("county"),
        "year_built": _num(listing.get("yearBuilt")),
        "days_on_market": _num(listing.get("daysOnMarket")),
        "listed_date": listing.get("listedDate"),
        "hoa_fee": _hoa_fee(listing),
        "status": listing.get("status"),
        # Listing identity / contact (RentCast carries no portal URL, so these are how
        # you actually find and reach the listing).
        "mls_number": listing.get("mlsNumber"),
        "mls_name": listing.get("mlsName"),
        "listing_agent": _contact(listing.get("listingAgent")),
        "listing_office": _contact(listing.get("listingOffice")),
        "price_history": history,
        "price_cut": price_cut,
    }

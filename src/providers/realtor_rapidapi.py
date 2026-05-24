"""Realtor.com provider via RapidAPI (STUB - wire up when you decide to pivot).

This is intentionally a skeleton. RapidAPI hosts several different "Realtor" products
(for example "us-real-estate", "realtor16", "realtor-com4"), each with its own endpoint
paths and response field names. Before this provider can run you must:

  1. Pick a specific RapidAPI product and subscribe (set RAPIDAPI_KEY in .env).
  2. Set RAPIDAPI_REALTOR_HOST to that product's host (e.g. "us-real-estate.p.rapidapi.com").
  3. Confirm the search endpoint path + params and fill in `_SEARCH_PATH` / param mapping.
  4. Confirm the response field names and complete `_normalize` below.

Once those four are filled in and verified against a live response, flip the data source
with `DATA_PROVIDER=realtor` and the rest of the pipeline works unchanged, because this
class emits the same internal schema as the RentCast provider.
"""
from __future__ import annotations

import os

from ..normalize import SQFT_PER_ACRE, _num
from .base import load_dotenv

# TODO: set these for your chosen RapidAPI product before enabling this provider.
_HOST = os.environ.get("RAPIDAPI_REALTOR_HOST", "")  # e.g. "us-real-estate.p.rapidapi.com"
_SEARCH_PATH = "/v2/for-sale"   # VERIFY against your product's docs
_PROPERTY_PATH = "/v2/detail"   # VERIFY against your product's docs


class RealtorRapidAPIProvider:
    name = "realtor"

    def __init__(self, api_key: str | None = None):
        if not api_key:
            load_dotenv()
            api_key = os.environ.get("RAPIDAPI_KEY")
        self._api_key = api_key

    def _headers(self) -> dict:
        if not self._api_key or not _HOST:
            raise NotImplementedError(
                "Realtor (RapidAPI) provider is not configured. Set RAPIDAPI_KEY and "
                "RAPIDAPI_REALTOR_HOST in .env, then complete the endpoint paths and the "
                "_normalize field mapping in src/providers/realtor_rapidapi.py. See the "
                "module docstring for the four steps."
            )
        return {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": _HOST,
            "Accept": "application/json",
        }

    @staticmethod
    def _normalize(item: dict) -> dict:
        """Map ONE RapidAPI listing into the internal schema.

        The keys below are placeholders. Replace each right-hand lookup with the actual
        field name from your chosen product's response, then verify against a live call.
        """
        price = _num(item.get("list_price"))
        sqft = _num(item.get("building_size_sqft"))
        lot_sqft = _num(item.get("lot_size_sqft"))
        acres = round(lot_sqft / SQFT_PER_ACRE, 3) if lot_sqft else None
        addr = item.get("address") or {}
        return {
            "id": item.get("property_id") or item.get("listing_id"),
            "address": item.get("formatted_address") or addr.get("line"),
            "city": addr.get("city"),
            "state": addr.get("state_code"),
            "zip": str(addr.get("postal_code")) if addr.get("postal_code") else None,
            "lat": _num(addr.get("lat")),
            "lon": _num(addr.get("lon")),
            "property_type": item.get("prop_type"),
            "price": price,
            "bedrooms": _num(item.get("beds")),
            "bathrooms": _num(item.get("baths")),
            "sqft": sqft,
            "acres": acres,
            "price_per_sqft": round(price / sqft, 1) if price and sqft else None,
            "year_built": _num(item.get("year_built")),
            "days_on_market": _num(item.get("days_on_market")),
            "listed_date": item.get("list_date"),
            "hoa_fee": _num((item.get("hoa") or {}).get("fee")),
            "status": item.get("status"),
        }

    def search_sale(self, zip_code: str, *, use_cache: bool = True) -> list[dict]:
        raise NotImplementedError(self._headers.__doc__ or "configure Realtor provider")

    def search_radius(self, lat: float, lon: float, radius_miles: float, *,
                      price_min: float = 0, price_max: float = 0,
                      bedrooms_min: float = 0, property_types: list[str] | None = None,
                      use_cache: bool = True) -> list[dict]:
        raise NotImplementedError("configure Realtor provider; see module docstring")

    def get_property(self, address: str, *, use_cache: bool = True) -> dict | None:
        raise NotImplementedError("configure Realtor provider; see module docstring")

    def usage_note(self) -> str:
        return "Realtor (RapidAPI): quota depends on your RapidAPI subscription tier."

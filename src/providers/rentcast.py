"""RentCast provider: sale-listings search + single-address lookup.

Free-tier discipline (50 calls/month, 20 req/sec):
- One API call per zip, up to 500 listings, then we filter locally.
- Every response cached to data/raw/rentcast-{key}-{date}.json; same-day repeat is free.
- Monthly call tally in data/api_usage.json; we self-cap at MONTHLY_BUDGET (< 50).

Endpoint: GET https://api.rentcast.io/v1/listings/sale   (auth header: X-Api-Key)
Docs: https://developers.rentcast.io/reference/sale-listings
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import requests

from ..normalize import normalize
from .base import load_dotenv

BASE_URL = "https://api.rentcast.io/v1/listings/sale"
MONTHLY_BUDGET = 45  # margin below the 50/month free cap
RAW_DIR = Path("data/raw")
USAGE_PATH = Path("data/api_usage.json")


class BudgetExceeded(RuntimeError):
    pass


def _today() -> str:
    return dt.date.today().isoformat()


class RentCastProvider:
    name = "rentcast"

    def __init__(self, api_key: str | None = None):
        if not api_key:
            load_dotenv()
            api_key = os.environ.get("RENTCAST_API_KEY")
        self._api_key = api_key

    # ---- usage tracking -------------------------------------------------
    @staticmethod
    def _month() -> str:
        return _today()[:7]

    def _load_usage(self) -> dict:
        return json.loads(USAGE_PATH.read_text()) if USAGE_PATH.exists() else {}

    def calls_used_this_month(self) -> int:
        return int(self._load_usage().get(self._month(), 0))

    def _record_call(self) -> int:
        USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        usage = self._load_usage()
        m = self._month()
        usage[m] = int(usage.get(m, 0)) + 1
        USAGE_PATH.write_text(json.dumps(usage, indent=2))
        return usage[m]

    def usage_note(self) -> str:
        return (f"RentCast: {self.calls_used_this_month()}/{MONTHLY_BUDGET} calls this "
                f"month (free cap 50).")

    # ---- core request ---------------------------------------------------
    def _require_key(self) -> str:
        if not self._api_key:
            raise RuntimeError(
                "RENTCAST_API_KEY not set. Copy .env.example to .env and paste your key. "
                "The .env file is gitignored and read directly by Python."
            )
        return self._api_key

    def _get(self, params: dict, cache: Path, use_cache: bool) -> list[dict]:
        if use_cache and cache.exists():
            return json.loads(cache.read_text())
        if self.calls_used_this_month() >= MONTHLY_BUDGET:
            raise BudgetExceeded(
                f"Used {self.calls_used_this_month()} RentCast calls this month "
                f"(budget {MONTHLY_BUDGET}). Cached lookups still work; new ones are "
                f"blocked until next month."
            )
        resp = requests.get(
            BASE_URL,
            headers={"X-Api-Key": self._require_key(), "Accept": "application/json"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        listings = data if isinstance(data, list) else data.get("listings", data)
        n = self._record_call()
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(listings, indent=2))
        print(f"  RentCast: {len(listings)} listings (call {n}/{MONTHLY_BUDGET} this month)")
        return listings

    # ---- provider interface --------------------------------------------
    def search_sale(self, zip_code: str, *, use_cache: bool = True) -> list[dict]:
        cache = RAW_DIR / f"rentcast-{zip_code}-{_today()}.json"
        raw = self._get(
            {"zipCode": zip_code, "status": "Active", "limit": 500}, cache, use_cache
        )
        return [normalize(x) for x in raw]

    def search_radius(self, lat: float, lon: float, radius_miles: float, *,
                      price_min: float = 0, price_max: float = 0,
                      bedrooms_min: float = 0, property_types: list[str] | None = None,
                      use_cache: bool = True) -> list[dict]:
        """Return normalized listings within radius_miles of (lat, lon) in ONE call.

        Hard filters that RentCast supports server-side (price, bedrooms, single
        propertyType) are pushed to the API so a wide radius stays under the 500-result
        cap. The caller still filters acres/baths locally via scoring.
        """
        params: dict = {
            "latitude": round(lat, 5), "longitude": round(lon, 5),
            "radius": radius_miles, "status": "Active", "limit": 500,
        }
        if price_min or price_max:
            params["price"] = f"{int(price_min)}:{int(price_max) if price_max else 100000000}"
        if bedrooms_min:
            params["bedrooms"] = f"{int(bedrooms_min)}:20"
        if property_types and len(property_types) == 1:
            params["propertyType"] = property_types[0]
        cache = RAW_DIR / f"rentcast-radius-{round(lat,3)}_{round(lon,3)}-{int(radius_miles)}mi-{_today()}.json"
        raw = self._get(params, cache, use_cache)
        return [normalize(x) for x in raw]

    def get_property(self, address: str, *, use_cache: bool = True) -> dict | None:
        slug = "".join(c if c.isalnum() else "-" for c in address.lower())[:60]
        cache = RAW_DIR / f"rentcast-addr-{slug}-{_today()}.json"
        raw = self._get({"address": address, "limit": 1}, cache, use_cache)
        if raw:
            return normalize(raw[0])
        return {"id": address, "address": address, "status": "not found in feed"}

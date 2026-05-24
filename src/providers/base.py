"""Listing-provider interface and shared helpers.

A provider is the ONLY part of the system that knows about a specific data vendor's API
and field names. Every provider returns listings already mapped into the project's
internal schema (see normalize.py), so the scorer, CLI, skills, and bot stay vendor
agnostic. To pivot from RentCast to Realtor.com (via RapidAPI), you implement a new
provider and flip the DATA_PROVIDER env var; nothing downstream changes.

Internal listing schema (what every provider must emit per home):
    id, address, city, state, zip, county, lat, lon, property_type, price, bedrooms,
    bathrooms, sqft, acres, price_per_sqft, year_built, days_on_market, listed_date,
    hoa_fee, status, mls_number, mls_name, listing_agent, listing_office,
    price_history, price_cut

RentCast carries no portal URL, so mls_number + listing_agent (name/phone/email/website)
are how a buyer finds and reaches a listing; price_history is a date-sorted list of events
and price_cut is a derived bool. A provider that lacks some of these may set them to None.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol, runtime_checkable


def load_dotenv(path: str | Path = ".env") -> None:
    """Load KEY=VALUE pairs from a local .env into os.environ, without printing them.

    Real environment variables win (setdefault), so CI or a shell export still takes
    precedence. This keeps every secret in the gitignored .env: callers never pass a key
    on the command line and it never lands in shell history or a chat transcript.
    """
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


@runtime_checkable
class ListingProvider(Protocol):
    """Contract every data provider implements. Methods return internal-schema dicts."""

    name: str

    def search_sale(self, zip_code: str, *, use_cache: bool = True) -> list[dict]:
        """Return normalized active for-sale listings for one zip code."""
        ...

    def search_radius(self, lat: float, lon: float, radius_miles: float, *,
                      price_min: float = 0, price_max: float = 0,
                      bedrooms_min: float = 0, property_types: list[str] | None = None,
                      use_cache: bool = True) -> list[dict]:
        """Return normalized active listings within radius_miles of a point.

        Implementations should push whatever hard filters the vendor supports server-side
        (price, bedrooms, property type) so a wide radius stays within result caps.
        """
        ...

    def get_property(self, address: str, *, use_cache: bool = True) -> dict | None:
        """Return one normalized listing for an address, or None if not found.

        Used by the rank-a-single-address path (the driving-around feature). A provider
        that cannot look up by address may return a minimal dict carrying just the
        address so the analyst can still research it from the web.
        """
        ...

    def usage_note(self) -> str:
        """One-line human summary of remaining quota / budget for this provider."""
        ...

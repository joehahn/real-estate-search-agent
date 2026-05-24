"""Provider registry. Select with the DATA_PROVIDER env var (default: rentcast)."""
from __future__ import annotations

import os

from .base import ListingProvider, load_dotenv


def get_provider(name: str | None = None) -> ListingProvider:
    if name is None:
        load_dotenv()
        name = os.environ.get("DATA_PROVIDER", "rentcast").strip().lower()

    if name == "rentcast":
        from .rentcast import RentCastProvider
        return RentCastProvider()
    if name == "realtor":
        from .realtor_rapidapi import RealtorRapidAPIProvider
        return RealtorRapidAPIProvider()
    raise ValueError(
        f"Unknown DATA_PROVIDER {name!r}. Supported: rentcast, realtor."
    )


__all__ = ["get_provider", "ListingProvider"]

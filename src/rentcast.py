"""RentCast sale-listings client with caching and free-tier budget tracking.

Design notes that matter for the free tier (50 calls/month, 20 req/sec):

- One API call returns up to 500 listings, so we make exactly ONE call per zip code.
  Searching 3 zips costs 3 of your 50 monthly calls.
- Every response is cached to data/raw/{zip}-{YYYY-MM-DD}.json. A second search of the
  same zip on the same day is served from cache and costs zero API calls.
- A running tally of calls this calendar month is kept in data/api_usage.json. We refuse
  to exceed `MONTHLY_BUDGET` so a runaway loop can never blow your quota.

Endpoint: GET https://api.rentcast.io/v1/listings/sale   (auth header: X-Api-Key)
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import requests

BASE_URL = "https://api.rentcast.io/v1/listings/sale"
MONTHLY_BUDGET = 45  # leave a small margin below the 50/month free cap
RAW_DIR = Path("data/raw")
USAGE_PATH = Path("data/api_usage.json")


class BudgetExceeded(RuntimeError):
    pass


def _load_dotenv(path: str | Path = ".env") -> None:
    """Load KEY=VALUE pairs from a local .env into os.environ, without printing them.

    Real environment variables take precedence (we use setdefault), so CI or a shell
    export still wins. This lets the key live only in the gitignored .env file: callers
    never pass it on the command line and it never lands in shell history or a transcript.
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


def _today() -> str:
    return dt.date.today().isoformat()


def _this_month() -> str:
    return _today()[:7]  # YYYY-MM


def _load_usage() -> dict:
    if USAGE_PATH.exists():
        return json.loads(USAGE_PATH.read_text())
    return {}


def _record_call() -> int:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    usage = _load_usage()
    month = _this_month()
    usage[month] = int(usage.get(month, 0)) + 1
    USAGE_PATH.write_text(json.dumps(usage, indent=2))
    return usage[month]


def calls_used_this_month() -> int:
    return int(_load_usage().get(_this_month(), 0))


def _cache_path(zip_code: str) -> Path:
    return RAW_DIR / f"{zip_code}-{_today()}.json"


def fetch_sale_listings(
    zip_code: str,
    *,
    api_key: str | None = None,
    limit: int = 500,
    use_cache: bool = True,
    status: str = "Active",
) -> list[dict]:
    """Return raw RentCast sale listings for one zip code.

    Pulls a broad set per zip (up to `limit`) and lets the scorer apply the
    wishlist filters locally. This keeps the API-call count at one per zip
    regardless of how many filter dimensions the wishlist has.
    """
    cache = _cache_path(zip_code)
    if use_cache and cache.exists():
        return json.loads(cache.read_text())

    if not api_key:
        _load_dotenv()
        api_key = os.environ.get("RENTCAST_API_KEY")
    if not api_key:
        raise RuntimeError(
            "RENTCAST_API_KEY not set. Copy .env.example to .env and paste your key. "
            "The .env file is gitignored and read directly by Python; you do not need to "
            "export it or pass it on the command line."
        )

    used = calls_used_this_month()
    if used >= MONTHLY_BUDGET:
        raise BudgetExceeded(
            f"Already used {used} RentCast calls this month (budget {MONTHLY_BUDGET}). "
            f"Cached zips still work; new zips are blocked until next month."
        )

    resp = requests.get(
        BASE_URL,
        headers={"X-Api-Key": api_key, "Accept": "application/json"},
        params={"zipCode": zip_code, "status": status, "limit": limit},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    listings = data if isinstance(data, list) else data.get("listings", data)

    n = _record_call()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(listings, indent=2))
    print(f"  RentCast: pulled {len(listings)} listings for {zip_code} "
          f"(call {n}/{MONTHLY_BUDGET} this month)")
    return listings

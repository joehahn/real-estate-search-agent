"""Command-line entry point for the deterministic half of the pipeline.

    python -m src.cli search     # fetch + filter + score, write data/candidates.json
    python -m src.cli usage      # show RentCast calls used this month

The Claude `/search-homes` skill calls `search`, then takes over: it reads
data/candidates.json, sends the top N to the property-analyst subagent for web
enrichment, and hands the result to the report-writer subagent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import rentcast
from .normalize import normalize
from .scoring import filter_and_score
from .wishlist import load_wishlist

CANDIDATES_PATH = Path("data/candidates.json")


def cmd_search(args) -> int:
    w = load_wishlist(args.wishlist)
    print(f"Wishlist: {len(w.zip_codes)} zips, price<= {w.price_max:.0f}, "
          f">= {w.bedrooms_min:.0f}bd/{w.bathrooms_min:.0f}ba, >= {w.acres_min} acres")

    raw: list[dict] = []
    for z in w.zip_codes:
        try:
            listings = rentcast.fetch_sale_listings(z, use_cache=not args.no_cache)
        except rentcast.BudgetExceeded as e:
            print(f"  ! {e}", file=sys.stderr)
            continue
        except Exception as e:  # network / auth / bad-zip: skip this zip, keep going
            print(f"  ! zip {z} failed: {e}", file=sys.stderr)
            continue
        raw.extend(normalize(x) for x in listings)

    if not raw:
        print("No listings pulled. Check your API key and zip codes.", file=sys.stderr)
        return 1

    ranked, dropped = filter_and_score(raw, w)
    print(f"\nPulled {len(raw)} listings -> {len(ranked)} pass hard filters "
          f"({len(dropped)} dropped).")

    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PATH.write_text(json.dumps({
        "wishlist_zips": w.zip_codes,
        "enrich_top_n": w.enrich_top_n,
        "count": len(ranked),
        "candidates": ranked,
    }, indent=2))
    print(f"Wrote {CANDIDATES_PATH} (top {w.enrich_top_n} flagged for enrichment).\n")

    for i, h in enumerate(ranked[:max(w.enrich_top_n, 10)], 1):
        print(f"  {i:2d}. score {h['score']:5.1f}  ${h['price']:>9,.0f}  "
              f"{h.get('bedrooms') or '?'}bd/{h.get('bathrooms') or '?'}ba  "
              f"{h.get('acres') or '?'} ac  {h.get('address')}")
    return 0


def cmd_usage(args) -> int:
    used = rentcast.calls_used_this_month()
    print(f"RentCast calls this month: {used} / {rentcast.MONTHLY_BUDGET} "
          f"(hard free cap is 50).")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="home-search", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="fetch + filter + score listings")
    s.add_argument("--wishlist", default="wishlist.md")
    s.add_argument("--no-cache", action="store_true",
                   help="bypass cache and spend an API call even if today's pull exists")
    s.set_defaults(func=cmd_search)

    u = sub.add_parser("usage", help="show RentCast call usage this month")
    u.set_defaults(func=cmd_usage)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

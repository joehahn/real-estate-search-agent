"""Command-line entry point for the deterministic half of the pipeline.

    python -m src.cli search            # fetch + filter + score -> data/candidates.json
    python -m src.cli rank "123 Main St, City, ST"   # fetch one property -> data/rank_target.json
    python -m src.cli usage             # show provider quota used this month

The data source is chosen by the DATA_PROVIDER env var (default: rentcast). The Claude
`/search-homes` and `/rank-address` skills call these commands, then take over: they send
the result(s) to the property-analyst subagent for web enrichment and hand off to the
report-writer subagent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .normalize import normalize  # noqa: F401  (kept for external callers/tests)
from .providers import get_provider
from .providers.rentcast import BudgetExceeded
from .scoring import filter_and_score
from .wishlist import load_wishlist

CANDIDATES_PATH = Path("data/candidates.json")
RANK_TARGET_PATH = Path("data/rank_target.json")


def cmd_search(args) -> int:
    w = load_wishlist(args.wishlist)
    provider = get_provider()
    print(f"Provider: {provider.name} | {provider.usage_note()}")
    print(f"Wishlist: {len(w.zip_codes)} zips, price<= {w.price_max:.0f}, "
          f">= {w.bedrooms_min:.0f}bd/{w.bathrooms_min:.0f}ba, >= {w.acres_min} acres")

    homes: list[dict] = []
    for z in w.zip_codes:
        try:
            homes.extend(provider.search_sale(z, use_cache=not args.no_cache))
        except BudgetExceeded as e:
            print(f"  ! {e}", file=sys.stderr)
            continue
        except Exception as e:  # network / auth / bad-zip: skip this zip, keep going
            print(f"  ! zip {z} failed: {e}", file=sys.stderr)
            continue

    if not homes:
        print("No listings pulled. Check your API key and zip codes.", file=sys.stderr)
        return 1

    ranked, dropped = filter_and_score(homes, w)
    print(f"\nPulled {len(homes)} listings -> {len(ranked)} pass hard filters "
          f"({len(dropped)} dropped).")

    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PATH.write_text(json.dumps({
        "provider": provider.name,
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


def cmd_rank(args) -> int:
    """Fetch one property by address for the rank-a-single-address flow."""
    provider = get_provider()
    print(f"Provider: {provider.name} | {provider.usage_note()}")
    try:
        home = provider.get_property(args.address, use_cache=not args.no_cache)
    except BudgetExceeded as e:
        print(f"! {e}", file=sys.stderr)
        return 1
    if not home:
        print(f"No property found for: {args.address}", file=sys.stderr)
        return 1
    RANK_TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    RANK_TARGET_PATH.write_text(json.dumps(home, indent=2))
    print(f"Wrote {RANK_TARGET_PATH}:")
    print(json.dumps(home, indent=2))
    return 0


def cmd_usage(args) -> int:
    print(get_provider().usage_note())
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="home-search", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="fetch + filter + score listings")
    s.add_argument("--wishlist", default="wishlist.md")
    s.add_argument("--no-cache", action="store_true",
                   help="bypass cache and spend an API call even if today's pull exists")
    s.set_defaults(func=cmd_search)

    r = sub.add_parser("rank", help="fetch one property by address")
    r.add_argument("address", help="full address: 'Street, City, ST Zip'")
    r.add_argument("--no-cache", action="store_true")
    r.set_defaults(func=cmd_rank)

    u = sub.add_parser("usage", help="show provider quota used this month")
    u.set_defaults(func=cmd_usage)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

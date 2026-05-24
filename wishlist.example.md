# Home Search Wishlist

This file is your single source of truth. The deterministic ranker reads the YAML
block below for hard filters and scoring weights. The `property-analyst` subagent and
the final report read the prose sections for context you cannot express as a number
(school quality, commute, "must have a view", red flags to watch for). Every
recommendation cites lines from this file.

Copy this file to `wishlist.md` and edit it. `wishlist.md` is gitignored so your
personal search stays private.

```yaml
# ----- Hard filters (applied first, deterministically; non-matching homes are dropped) -----
# You can give a human region label and/or an explicit zip list. If you set `region` and
# leave zip_codes empty, the /search-homes (or /init-wishlist) skill expands the region
# into a concrete zip list and writes it back here, so you always see and control exactly
# which zips are queried (one RentCast call per zip). region is optional.
region: "West Knoxville, TN"        # optional human label; delete if you only use zips
zip_codes: [78613, 78641, 78626]   # 5-digit zips to search. One RentCast call per zip.
price_min: 0
price_max: 650000
bedrooms_min: 3
bathrooms_min: 2
acres_min: 0.50                    # 0 to disable. Lot size comes from RentCast in sqft; we convert.
property_types: ["Single Family"]  # RentCast values: Single Family, Condo, Townhouse,
                                   # Manufactured, Multi-Family, Apartment, Land
max_days_on_market: null           # e.g. 90 to hide stale listings; null disables

# ----- Scoring weights (soft preferences for the survivors; auto-normalized) -----
# Higher weight = matters more to the final rank. Tune freely.
weights:
  price: 0.30            # cheaper (within range) scores higher
  acres: 0.25            # more land scores higher
  square_footage: 0.15   # more living area scores higher
  price_per_sqft: 0.10   # better $/sqft scores higher
  bedrooms: 0.08
  bathrooms: 0.04
  freshness: 0.08        # newer listings score higher

# ----- Enrichment budget -----
enrich_top_n: 8          # how many top-ranked homes get web-research enrichment by the subagent
```

## Must-haves (the analyst eliminates a home that clearly fails one)

- Not on a flood plain (FEMA zone A/AE is a hard no).
- A usable, mostly-flat back yard (not all slope or ravine).

## Nice-to-haves (reward these in the writeup, do not eliminate)

- Mature trees / wooded lot.
- Updated kitchen within the last ~10 years.
- Quiet street, cul-de-sac preferred.
- Good or improving school ratings.

## Warning flags (the analyst marks these "caution": surfaced loudly, not eliminated)

Use this for things that should stop you from a wasted trip or sharpen your questions,
but that you would not auto-reject a home over. The right call depends on the rest of the
deal.

- Directly on a major highway or arterial road.
- Very old construction without evidence of major systems updates.
- Backs onto commercial property or a busy parking lot.

## Deal-breakers (the analyst eliminates these from picks)

- HOA fee over $100/month.
- Active foundation issues mentioned in the listing or inspection notes.
- Located within 1 mile of a known nuisance (landfill, quarry, feedlot, rail yard).

## Lifestyle / commute context

Describe what your daily life looks like so the analyst can judge location.
Example: "Primary commute is to downtown Austin, want under 40 minutes off-peak.
Prefer a walkable distance to a grocery store. Two school-age kids."

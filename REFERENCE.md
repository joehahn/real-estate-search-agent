# REFERENCE

Repo layout, schemas, and file formats for the Real Estate Search Agent.

## Repo layout

```
real-estate-search-agent/
├── README.md                 project overview and setup
├── CLAUDE.md                 guidance for Claude Code
├── REFERENCE.md              this file
├── pyproject.toml            package metadata, deps, pytest config
├── .env.example              RENTCAST_API_KEY template (copy to .env)
├── wishlist.example.md       wishlist template (committed)
├── wishlist.md               your real wishlist (gitignored)
│
├── src/
│   ├── wishlist.py           parse wishlist.md -> Wishlist dataclass
│   ├── rentcast.py           RentCast client: cache + monthly budget tracking
│   ├── normalize.py          raw listing -> internal schema (acres, $/sqft)
│   ├── scoring.py            hard filters + explainable weighted score
│   └── cli.py                `search` and `usage` commands
│
├── scripts/
│   └── build_dashboard.py    candidates + enrichment -> docs/index.html (Leaflet map)
│
├── .claude/
│   ├── agents/
│   │   ├── property-analyst.md   enrichment subagent (web research, one per candidate)
│   │   └── report-writer.md      report-composition subagent
│   └── skills/
│       ├── search-homes/SKILL.md   the end-to-end orchestrator
│       └── init-wishlist/SKILL.md  guided wishlist setup
│
├── tests/
│   └── test_pipeline.py      parsing, normalization, filters, scoring
│
├── data/                     (gitignored contents)
│   ├── raw/{zip}-{date}.json     cached RentCast pulls
│   ├── candidates.json           filtered + scored homes (Python -> skill handoff)
│   ├── enrichment.json           analyst verdicts (skill -> report handoff)
│   └── api_usage.json            {month: calls_used}
│
├── reports/{date}-shortlist.md   the buyer-facing report (gitignored)
└── docs/index.html               the map dashboard (gitignored; publish via Pages)
```

## Wishlist schema (the ```yaml block in wishlist.md)

| Field | Type | Meaning |
|-------|------|---------|
| `zip_codes` | list of 5-digit zips | one RentCast call each |
| `price_min` / `price_max` | number | hard price band; `price_max` of 0 disables the ceiling |
| `bedrooms_min` / `bathrooms_min` | number | hard minimums |
| `acres_min` | number | hard minimum lot size in acres; 0 disables |
| `property_types` | list | RentCast values: Single Family, Condo, Townhouse, Manufactured, Multi-Family, Apartment, Land |
| `max_days_on_market` | int or null | drop staler listings; null disables |
| `weights` | map | soft-preference weights, auto-normalized |
| `enrich_top_n` | int | how many top homes get analyst enrichment |

Scoring weight keys: `price`, `acres`, `square_footage`, `price_per_sqft`, `bedrooms`,
`bathrooms`, `freshness`. For `price`, `price_per_sqft`, and `freshness` (days on
market), a lower raw value scores higher; for the rest, higher scores higher. Each
dimension is min-max normalized across the surviving candidate pool, so the score is
relative to what is actually for sale right now.

The prose sections (Must-haves, Nice-to-haves, Deal-breakers, Lifestyle/commute) are not
parsed by Python. They are passed verbatim to the `property-analyst` subagent.

## RentCast endpoint

`GET https://api.rentcast.io/v1/listings/sale`, auth header `X-Api-Key`. The client sends
`zipCode`, `status=Active`, `limit=500`. Lot size returns in square feet; `normalize.py`
divides by 43,560 for acres. See <https://developers.rentcast.io/reference/sale-listings>.

## data/candidates.json

```json
{
  "wishlist_zips": ["78613"],
  "enrich_top_n": 8,
  "count": 12,
  "candidates": [
    {
      "id": "...", "address": "...", "lat": 30.5, "lon": -97.8,
      "property_type": "Single Family", "price": 540000,
      "bedrooms": 4, "bathrooms": 3, "sqft": 2600, "acres": 1.1,
      "price_per_sqft": 207.7, "year_built": 2015, "days_on_market": 7,
      "hoa_fee": null, "status": "Active",
      "score": 79.0,
      "score_breakdown": {"price": 22.1, "acres": 25.0, "square_footage": 12.3, "...": 0.0}
    }
  ]
}
```

`score` is 0..100; `score_breakdown` gives each weighted dimension's points, which sum to
`score`. Candidates are sorted by `score` descending.

## data/enrichment.json

An array of `property-analyst` verdicts, one per enriched candidate. See the schema in
`.claude/agents/property-analyst.md`. Joined to candidates by `id`.

## Final re-rank (in /search-homes)

```
final_score = 0.6 * numeric_score + 0.4 * (qual_score * 10)
```

Homes with `deal_breaker_status == "eliminate"` are removed from picks and listed in the
report's eliminated section with the triggering reason. The 0.6/0.4 split is a default;
the skill adjusts it on request and states the split used in the report.

## Extending to another data source

Replace `src/rentcast.py` with a client that returns a list of raw listing dicts per
search. As long as `normalize.py` can map the fields (price, bedrooms, bathrooms,
squareFootage, lotSize, latitude, longitude, formattedAddress, ...), the rest of the
pipeline is source-agnostic.

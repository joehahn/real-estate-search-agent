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
│   ├── normalize.py          raw listing -> internal schema (acres, $/sqft)
│   ├── scoring.py            hard filters + explainable weighted score
│   ├── cli.py                `search`, `rank`, `usage` commands
│   └── providers/
│       ├── base.py               provider Protocol + load_dotenv + internal schema
│       ├── rentcast.py           RentCast impl: cache + monthly budget tracking
│       ├── realtor_rapidapi.py   Realtor.com via RapidAPI (stub, ready to wire up)
│       └── __init__.py           get_provider() factory (DATA_PROVIDER env)
│
├── bot/
│   └── telegram_bot.py       Level-C two-way bot: phone -> claude -p -> reply
│
├── scripts/
│   ├── build_dashboard.py    candidates + enrichment -> docs/index.html (Leaflet map)
│   └── run_bot.sh            start the Telegram bot (wrap in caffeinate to stay awake)
│
├── .claude/
│   ├── agents/
│   │   ├── property-analyst.md   enrichment subagent (web research, one per candidate)
│   │   └── report-writer.md      report-composition subagent
│   └── skills/
│       ├── search-homes/SKILL.md   the end-to-end orchestrator
│       ├── rank-address/SKILL.md   evaluate one property by address (phone /rank)
│       └── init-wishlist/SKILL.md  guided wishlist setup
│
├── tests/
│   └── test_pipeline.py      parsing, normalization, filters, scoring
│
├── data/                     (gitignored contents)
│   ├── raw/{provider}-{key}-{date}.json   cached provider pulls
│   ├── candidates.json           filtered + scored homes (Python -> skill handoff)
│   ├── enrichment.json           analyst verdicts (skill -> report handoff)
│   ├── rank_target.json          single property for /rank-address
│   └── api_usage.json            {month: calls_used}
│
├── reports/{date}-shortlist.md   the buyer-facing report (gitignored)
└── docs/index.html               the map dashboard (gitignored; publish via Pages)
```

## Wishlist schema (the ```yaml block in wishlist.md)

| Field | Type | Meaning |
|-------|------|---------|
| `region` | string or absent | optional human label (e.g. "West Knoxville, TN"); a skill expands it into `zip_codes` and writes them back |
| `zip_codes` | list of 5-digit zips | one RentCast call each; the canonical field the Python core queries |
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
      "hoa_fee": null, "status": "Active", "county": "Knox",
      "mls_number": "1333474", "mls_name": "EastTennessee",
      "listing_agent": {"name": "...", "phone": "...", "email": "...", "website": "..."},
      "listing_office": {"name": "..."},
      "price_history": [{"date": "2026-03-20", "event": "Sale Listing", "price": 1200000}],
      "price_cut": false,
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

## Adding a data provider

Implement the `ListingProvider` Protocol from `src/providers/base.py`: `search_sale(zip)`,
`get_property(address)`, and `usage_note()`, each returning internal-schema dicts (do the
vendor-specific field mapping inside the provider). Register it in
`src/providers/__init__.py`'s `get_provider()` factory, then select it with
`DATA_PROVIDER=<name>`. Nothing downstream (scoring, CLI, skills, bot, dashboard) changes
because they only ever see the internal schema. `realtor_rapidapi.py` is a worked-example
skeleton; its docstring lists the four things to fill in.

## Telegram bot (Level C)

`bot/telegram_bot.py` long-polls Telegram, accepts commands only from chat ids in
`TELEGRAM_ALLOWED_CHAT_IDS`, and runs the project via `claude -p` (extra permission args
from `CLAUDE_ARGS`, default `--permission-mode bypassPermissions`). `/usage` calls the
Python CLI directly (no LLM); `/search` and `/rank` and free text go through `claude -p`.
The bot reads its token from the gitignored `.env`, so the phone never handles a key. Run
it with `caffeinate -s ./scripts/run_bot.sh` to keep the laptop awake.

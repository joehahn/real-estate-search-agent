# Real Estate Search Agent

**Author:** Joe Hahn
**Email:** jmh.datasciences@gmail.com
**Date:** 2026-May-24
**branch:** main

This Claude Code project turns a plain-language home wishlist into a ranked, researched
shortlist of for-sale properties. You declare your hard requirements and soft preferences
(bedrooms, bathrooms, acres, price ceiling, zip codes, and what matters most), and the
system does two distinct jobs. First, a deterministic Python core pulls active listings
from the RentCast API, drops anything that fails a hard filter, and scores the survivors
with a transparent weighted match to your wishlist. Second, a Claude `property-analyst`
subagent researches each top candidate on the web for the signal no structured feed
carries: flood risk, school quality, commute, listing history, and neighborhood
nuisances. A `report-writer` subagent then composes a ranked shortlist that explains why
each home placed where it did, and a map dashboard plots every candidate colored by
score.

The split is deliberate. Ranking on numbers is reproducible and cheap, so it stays in
Python where it can be tested and audited. Judgment about location and risk is where an
LLM earns its keep, so that runs as enrichment on only the top candidates, which also
keeps the search inside the RentCast free tier.

**Who this helps.** A buyer who knows roughly what they want but does not have time to
open fifty listings a week, cross-check each against a flood map, and remember which ones
had a price cut. This produces a short, honest list of homes worth a Saturday visit, with
the reasoning attached so you can disagree with it.

## Architecture

```
wishlist.md  (your hard filters + scoring weights + prose preferences)
   │
/search-homes  (the orchestrating skill)
   │
   ├─ 1. src/cli.py search ........ RentCast: one cached call per zip (free tier: 50/mo)
   │       ├─ src/normalize.py ..... lot sqft -> acres, derive $/sqft
   │       └─ src/scoring.py ....... hard filters + explainable weighted score (0..100)
   │                                 -> data/candidates.json
   │
   ├─ 2. property-analyst (subagent, one per top candidate, run in parallel)
   │       └─ WebSearch/WebFetch ... flood, schools, commute, history, nuisances
   │                                 -> data/enrichment.json
   │
   ├─ 3. re-rank: 0.6*numeric + 0.4*analyst, drop deal-breakers
   │
   ├─ 4. report-writer (subagent) .. reports/{date}-shortlist.md
   │
   └─ 5. scripts/build_dashboard.py  docs/index.html (Leaflet map, GitHub Pages ready)
```

The deterministic core (`src/`) is unit-tested and runs without any LLM. The two
subagents (`.claude/agents/`) add and explain the qualitative layer.

## Setup

### 1. Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
```

### 2. Get a RentCast API key (free)

Sign up at <https://app.rentcast.io/app/api>. The free tier is 50 calls per month, which
is plenty: the client makes exactly one call per zip code and caches every response, so
re-running a search the same day costs nothing.

```bash
cp .env.example .env
# edit .env and paste your key. That is it.
```

`.env` is gitignored and read directly by the Python client, so your key never needs to
be exported, passed on the command line, or pasted into a chat. Never commit a real key;
only `.env.example` (a placeholder) is tracked.

### 3. Build your wishlist

Run `/init-wishlist` in Claude Code for a guided interview, or copy the template and edit
by hand:

```bash
cp wishlist.example.md wishlist.md
```

### 4. Run a search

In Claude Code, run `/search-homes`. It pulls listings, scores them, dispatches the
analyst subagents, writes `reports/{date}-shortlist.md`, and refreshes `docs/index.html`.

To run just the deterministic half from the shell:

```bash
python -m src.cli search     # writes data/candidates.json and prints the ranked list
python -m src.cli usage       # shows RentCast calls used this month
python scripts/build_dashboard.py   # rebuilds the map from the latest data
```

## A note on data sources

The major consumer portals (Zillow, Realtor.com, Redfin) actively block automated access
and their terms forbid scraping, so this project does not touch them. It uses RentCast, a
licensed real estate data API, as its single structured source. The agents enrich with
ordinary public web research. If you want full MLS coverage, that requires a licensed
agent or broker relationship or a paid RESO data feed; the architecture here drops in
behind any such source by swapping `src/rentcast.py`.

## Testing

```bash
python -m pytest -q
```

The tests cover wishlist parsing, the sqft-to-acres normalization, the hard filters, and
the scoring order, all without network or API calls.

## Files

See [REFERENCE.md](REFERENCE.md) for the full repo layout, the wishlist schema, the
subagent contracts, and the input and output file formats.

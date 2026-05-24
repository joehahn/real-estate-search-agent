---
name: search-homes
description: End-to-end home search. Pulls for-sale listings from RentCast for the wishlist's zips, filters and scores them deterministically, sends the top candidates to the property-analyst subagent for web enrichment, re-ranks, and writes a ranked shortlist report plus a refreshed map dashboard.
---

# /search-homes

Run the full pipeline: structured pull and scoring in Python, qualitative enrichment via
parallel `property-analyst` subagents, then a report from the `report-writer` subagent
and a refreshed map. The deterministic core decides the numeric rank; the agents add the
location-and-risk judgment that no feed carries.

## Before you start

1. Read `wishlist.md`. If it is missing, stop and tell the user to run `/init-wishlist`
   (or copy `wishlist.example.md` to `wishlist.md`). Do not invent a default wishlist.
2. Confirm a key exists: check that `.env` is present (or `RENTCAST_API_KEY` is already in
   the environment). The Python client reads `.env` directly, so you do NOT need to source
   it, echo it, or pass the key on the command line. Never print the key value. If `.env`
   is missing, tell the user to `cp .env.example .env` and paste their key. The free tier
   is 50 calls/month and the client caps itself at 45; one call per zip.
3. Check the budget: run `python -m src.cli usage`. If the month's calls are near the cap,
   warn the user before pulling new zips (cached zips from earlier today are free). The
   data source is whatever `DATA_PROVIDER` selects (default `rentcast`); the CLI prints it.

## Step 0 - resolve region to zips (only if needed)

Read the wishlist's `region` and `zip_codes`. If `region` is set and `zip_codes` is empty
(or the user just changed the region), expand the region into a concrete list of 5-digit
zip codes that cover it, using your geographic knowledge. Keep the list reasonable for the
free tier (one call per zip); if a region is huge, pick the zips that best match the
user's price band and say which you chose and which you left out.

Write the expanded list into `wishlist.md`'s `zip_codes` (keep the `region` label as a
comment), then show the user the zips and the projected call count (`len(zips)` plus
`python -m src.cli usage`) and let them trim before you pull. Do not silently query a long
list of zips.

## Step 1 - structured pull, filter, score (Python)

```bash
source .venv/bin/activate
python -m src.cli search
```

This writes `data/candidates.json` with every home that passed the hard filters, each
carrying a numeric `score` (0..100) and a `score_breakdown`. The top `enrich_top_n`
(from the wishlist) are the ones to enrich. If zero candidates pass, stop and tell the
user which filters were most limiting (read the dropped-reasons printed by the CLI) and
suggest loosening one.

## Step 2 - enrich the top candidates (parallel property-analyst subagents)

Read `data/candidates.json` and the prose sections of `wishlist.md` (Must-haves,
Nice-to-haves, Deal-breakers, Lifestyle/commute).

For each of the top `enrich_top_n` candidates, spawn a `property-analyst` subagent. Send
all of them in a SINGLE message (multiple Task calls) so they run concurrently. Pass each
agent a self-contained prompt with:

- `property`: that one candidate object from `candidates.json`.
- `wishlist_prose`: the four prose sections verbatim.

Collect each agent's JSON verdict. Save the array to `data/enrichment.json`.

## Step 3 - re-rank with the enrichment

Combine the numeric score and the analyst's `qual_score` into a final order:

- Drop any home with `deal_breaker_status: "eliminate"` from the picks; keep it for the
  "eliminated" section with its triggering reason.
- Final score = `0.6 * numeric_score + 0.4 * (qual_score * 10)` for the survivors. This
  weighting is a sensible default; if the user has asked for "trust the numbers more" or
  "location is everything", adjust the split and say so in the report.
- Sort survivors by final score. Mark the top 3 to 5 as the "top picks" the report
  expands in full; the rest go in the compact ranked table.

## Step 4 - write the report (report-writer subagent)

Spawn the `report-writer` subagent. Pass `final_ranked`, `eliminated`, the
`wishlist_prose`, and `report_path = reports/{YYYY-MM-DD}-shortlist.md`. It writes that
one file. Read it back and surface the top picks to the user in chat.

## Step 5 - refresh the map dashboard

```bash
python scripts/build_dashboard.py
```

This reads `data/candidates.json` and `data/enrichment.json` and writes `docs/index.html`:
a map with a marker per candidate, colored by final score, popups showing price/beds/
acres/verdict. If the user publishes `docs/` to GitHub Pages, this is the shareable
artifact.

## Output recap to the user

- Report: `reports/{date}-shortlist.md`
- Map: `docs/index.html`
- API budget used this month (from `python -m src.cli usage`).

## Notes

- Re-running the same zips on the same day costs zero API calls (cache). Re-ranking after
  a wishlist weight change does not need new pulls: re-run `search` (served from cache),
  then steps 2 to 5.
- Keep enrichment honest. If an analyst returns `"unverified"` for a field, the report
  must say so. Never let the report state a flood zone or school rating no agent sourced.

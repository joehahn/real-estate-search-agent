---
name: rank-address
description: Evaluate ONE property by address against the wishlist. The driving-around feature: "what about this house I am parked in front of?" Fetches the listing, runs the property-analyst subagent, and returns a concise verdict. Cheap; does not pull a whole zip.
---

# /rank-address

Evaluate a single address against the user's `wishlist.md` and return a short, decision-
ready verdict. Designed for in-the-field use (and as the bot's `/rank` command): one
property lookup plus one analyst pass, no full zip pull, so it stays well inside the data
budget.

Usage: `/rank-address 123 Ranch Rd, Cedar Park, TX 78613`

## Steps

1. Read `wishlist.md` for the hard filters and the prose sections. If missing, say so and
   stop.

2. Fetch the property (one provider call, cached for the day):
   ```bash
   source .venv/bin/activate
   python -m src.cli rank "<the address>"
   ```
   This writes `data/rank_target.json` with the normalized listing. If the provider has
   no record, the file still carries the address so the analyst can research it from the
   web; tell the user the structured data was unavailable.

3. Apply the hard filters in your head against the fetched numbers (price, beds, baths,
   acres, type). Note any that fail; a hard fail is worth saying up front.

4. Spawn ONE `property-analyst` subagent. Pass `property` = the contents of
   `data/rank_target.json` and `wishlist_prose` = the four prose sections of
   `wishlist.md`. Wait for its JSON verdict.

5. Reply with a tight summary the user can read on a phone:
   - One line: address, price, beds/baths, acres.
   - Hard-filter status (pass, or which constraint it misses).
   - Analyst `qual_score`/10 and `deal_breaker_status`.
   - Top 2 highlights and top 2 concerns.
   - Flood / schools / commute one-liners with their sources.
   - A one-sentence verdict: worth a closer look, or skip, and why.

Keep the reply short and skimmable. This is meant to be read at the curb, not at a desk.

## Notes

- Do not write a full report file for a single address; the chat/text reply is the
  deliverable. (The `/search-homes` skill is the one that writes report files.)
- Honesty rules apply: never state a flood zone, school rating, or commute the analyst
  did not source. If a field is `"unverified"`, say so.

# CLAUDE.md - Real Estate Search Agent

Guidance for Claude Code when working in this repository.

## What this project is

An AI home-search assistant. It converts a user's `wishlist.md` into a ranked, researched
shortlist of for-sale homes. The design separates two concerns on purpose:

- **Deterministic core (`src/`, Python):** pulls listings from RentCast, applies hard
  filters, and computes a transparent weighted score. Reproducible, tested, no LLM.
- **Judgment layer (`.claude/agents/`, subagents):** the `property-analyst` enriches the
  top candidates with web research (flood, schools, commute, history, nuisances); the
  `report-writer` composes the final report. The `/search-homes` skill orchestrates both.

When you change ranking logic, keep it in `src/scoring.py` so it stays testable. When you
change what gets researched or how it reads, change the agent specs. Do not move
qualitative judgment into Python or numeric ranking into the agents.

## Data contract

**User layer (never overwrite with defaults; this is the user's private data):**
- `wishlist.md` (gitignored), `.env` (gitignored)
- `data/raw/`, `data/candidates.json`, `data/enrichment.json`, `data/api_usage.json`
- `reports/`, `docs/index.html`

**System layer (safe to edit and commit):**
- `src/*.py`, `scripts/*.py`, `tests/*`
- `.claude/agents/*`, `.claude/skills/*`
- `wishlist.example.md`, `README.md`, `REFERENCE.md`, `CLAUDE.md`, `pyproject.toml`

When the user asks to customize the search (new weights, new filters, new things to
research), edit `wishlist.md` for their criteria, or the agent specs for shared behavior.
Never put a user's personal criteria into `wishlist.example.md`.

## RentCast free tier discipline (important)

- Free tier is 50 calls/month; `src/rentcast.py` caps itself at 45 (`MONTHLY_BUDGET`).
- One call per zip, capped at 500 listings. Never loop the API per-filter; pull broad and
  filter locally in `scoring.py`.
- Every response is cached to `data/raw/{zip}-{date}.json`. Re-running the same zip the
  same day is free. Prefer re-running `search` (cache-served) over new pulls when only the
  weights changed.
- Before pulling new zips, check `python -m src.cli usage` and warn the user if near cap.

## Orchestration rules for /search-homes

1. Read `wishlist.md` first. If missing, route to `/init-wishlist`. Never fabricate a
   wishlist.
2. Run `python -m src.cli search`. If zero candidates pass, report the most limiting
   filter and suggest loosening, do not silently proceed.
3. Spawn one `property-analyst` per top-N candidate in a SINGLE message (parallel Task
   calls). Save results to `data/enrichment.json`.
4. Re-rank: drop `deal_breaker_status == "eliminate"`; final = 0.6*numeric + 0.4*qual*10.
5. Spawn `report-writer` to write `reports/{date}-shortlist.md`. Then rebuild the map.
6. Recap to the user: report path, map path, API budget used.

## Honesty rules (non-negotiable)

- The report must never state a flood zone, school rating, commute time, or price history
  that no analyst sourced. If an analyst field is `"unverified"`, say so.
- A home flagged with a triggered deal-breaker is eliminated from picks even if its
  numeric score is high. Buyer safety beats rank.
- This is a pre-visit triage tool. The report should remind the user it has not seen
  inside any house and does not replace an inspection or a buyer's agent.

## Style

- No em dashes in narrative text (project owner's house style). Use colon, semicolon,
  comma, or period. Em dashes in tables or structural separators are fine.
- "Subagent" and "multi-tool agent" are accurate here: this genuinely uses Claude Code
  subagents. Describe it as such.

## Stack

Python 3.12 (`pyproject.toml`, setuptools), `requests` for RentCast, `folium` for the
map, `pytest` for tests. Markdown for config and reports, JSON for the Python/agent
handoff (`data/candidates.json`, `data/enrichment.json`).

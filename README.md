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
phone (Telegram) ─── bot/telegram_bot.py ─── claude -p "/search-homes" | "/rank-address ..."
                                                   │
wishlist.md  (your hard filters + scoring weights + prose preferences)
   │
/search-homes  (the orchestrating skill)
   │
   ├─ 1. src/cli.py search ........ provider (src/providers/): one cached call per zip
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

/rank-address  (single-property skill; the phone's /rank command) reuses steps 1-2 for one home.
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

You can name a search area two ways. Set explicit `zip_codes`, or set a `region` like
`"West Knoxville, TN"` and let the `/search-homes` (or `/init-wishlist`) skill expand it
into a concrete zip list, which it writes back into `wishlist.md` so you see and control
exactly which zips are queried (one API call per zip).

### 4. Run a search

In Claude Code, run `/search-homes`. It pulls listings, scores them, dispatches the
analyst subagents, writes `reports/{date}-shortlist.md`, and refreshes `docs/index.html`.

To run just the deterministic half from the shell:

```bash
python -m src.cli search     # writes data/candidates.json and prints the ranked list
python -m src.cli usage       # shows RentCast calls used this month
python scripts/build_dashboard.py   # rebuilds the map from the latest data
```

## Texting the agent from your phone (Level C)

You do not need the laptop with you to use this. The laptop is the server; your phone is
a thin client over Telegram. The bot runs where the repo and the keys live, accepts
commands from an allowlisted chat, runs the skills, and texts the answer back. Your phone
never sees a key.

```
phone --Telegram--> bot/telegram_bot.py --> claude -p "/rank-address ..." --> skills/subagents
phone <--Telegram-- bot <--------------------- Claude's final reply
```

**Setup**

1. In Telegram, message **@BotFather**, create a bot, copy its token into `.env` as
   `TELEGRAM_BOT_TOKEN`.
2. Start the bot, keeping the laptop awake:
   ```bash
   caffeinate -s ./scripts/run_bot.sh
   ```
3. Message your bot `/whoami`, copy the chat id it returns into
   `TELEGRAM_ALLOWED_CHAT_IDS` in `.env`. Only that chat can now run actions.
4. Grant the bot scoped permission to run the skills by setting `CLAUDE_ARGS` in `.env`,
   then restart:
   ```
   CLAUDE_ARGS=--allowedTools Bash(python*) Task Read Write WebSearch WebFetch
   ```

**Security model.** The bot runs `claude -p` on your machine, so it ships locked down:
the chat-id allowlist is mandatory, `CLAUDE_ARGS` is empty until you grant permission
(prefer the scoped allowlist above over `--permission-mode bypassPermissions`), and
open-ended free text is ignored unless you set `BOT_ALLOW_FREEFORM=1`. Treat the bot
token like a password: anyone holding it can talk to your bot, and the allowlist plus
scoped permissions are what keep that from becoming code execution on your laptop.

**Commands from your phone**

- `/search` runs a full search and texts back the top picks.
- `/rank 123 Ranch Rd, Cedar Park, TX` evaluates the house you are parked in front of.
- `/usage` shows your data-provider quota for the month.
- Any other message is handed to the agent to interpret, but only if you opt in with
  `BOT_ALLOW_FREEFORM=1` (off by default).

**Two real constraints.** The laptop must stay awake, plugged in, and online (use
`caffeinate`), and the RentCast free tier is 50 calls a month, so a full `/search` is a
once-or-twice-a-day action, not a continuous poll. The `/rank` command is cheap (one
property lookup), which is why it is the natural in-the-field tool. To remove the laptop
dependency entirely later, run the bot on a small always-on box (a cloud VM or a
Raspberry Pi at home); nothing else changes.

## Data sources: pluggable, RentCast first

The major consumer portals (Zillow, Realtor.com, Redfin) actively block automated access
and their terms forbid scraping, so this project does not scrape them. Data comes through
a provider interface (`src/providers/`) so the source is swappable:

- **RentCast** (default, `DATA_PROVIDER=rentcast`): a licensed real estate data API with a
  free tier. Fully implemented.
- **Realtor.com via RapidAPI** (`DATA_PROVIDER=realtor`): a scaffolded provider
  (`src/providers/realtor_rapidapi.py`) ready to wire up if you decide it adds value. Set
  the RapidAPI key and host, confirm the endpoint and field mapping, and flip the env var;
  nothing downstream changes because every provider emits the same internal schema.

Full MLS coverage requires a licensed agent or broker relationship or a paid RESO feed;
that too drops in as another provider.

## Testing

```bash
python -m pytest -q
```

The tests cover wishlist parsing, the sqft-to-acres normalization, the hard filters, and
the scoring order, all without network or API calls.

## Files

See [REFERENCE.md](REFERENCE.md) for the full repo layout, the wishlist schema, the
subagent contracts, and the input and output file formats.

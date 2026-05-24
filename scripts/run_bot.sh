#!/usr/bin/env bash
# Start the Telegram bot. Keep this laptop awake (caffeinate) while it runs.
# Usage:  ./scripts/run_bot.sh
#   or, to also prevent sleep:  caffeinate -s ./scripts/run_bot.sh
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
exec python -m bot.telegram_bot

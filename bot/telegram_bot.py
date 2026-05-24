"""Telegram bot: text your home-search agent from your phone while the laptop works.

This is the Level-C two-way interface. It runs on the machine that holds the repo and the
API keys (your laptop, kept awake). Your phone never sees a key; it just sends text.

Flow:
  phone --Telegram--> this listener --subprocess--> `claude -p "<skill or text>"`
                                                      (runs the project's skills/subagents)
  phone <--Telegram-- this listener <--stdout-------- Claude's final reply

Commands:
  /start, /help     usage
  /whoami           reply with your Telegram chat id (use it to fill the allowlist)
  /usage            data-provider quota this month (cheap, no LLM)
  /search           run /search-homes, reply with the top picks
  /rank <address>   run /rank-address on one property (the driving-around feature)
  any other text    piped to `claude -p` so the agent decides what to do

Security model (read this before exposing the bot):
  This bot runs `claude -p` on the host machine. That is powerful, so it is locked down by
  default and you opt into capability deliberately:
  * ALLOWLIST IS MANDATORY. Only chat ids in TELEGRAM_ALLOWED_CHAT_IDS may run anything.
    /start, /help, /whoami answer anyone (so you can discover your id) but run no skill.
  * NO BYPASS BY DEFAULT. CLAUDE_ARGS is empty unless you set it. To let /search and /rank
    run unattended you must grant tool permission yourself. Prefer a SCOPED allowlist over
    a blanket bypass, e.g. in .env:
        CLAUDE_ARGS=--allowedTools Bash(python*) Task Read Write WebSearch WebFetch
    Use `--permission-mode bypassPermissions` only if you accept that a leaked bot token
    then equals code execution on this machine.
  * FREE-FORM IS OPT-IN. By default only the known commands (/search, /rank, /usage) run.
    Arbitrary text is piped to the agent only when BOT_ALLOW_FREEFORM=1, because that is
    the widest injection surface. Even then, keep CLAUDE_ARGS scoped.
  The bot reads its token from the gitignored .env; your phone never sees a key.

Setup (see README "Texting the agent from your phone"):
  1. Create a bot with @BotFather, put the token in .env as TELEGRAM_BOT_TOKEN.
  2. Run this bot, message it /whoami, copy the id into TELEGRAM_ALLOWED_CHAT_IDS in .env.
  3. Set CLAUDE_ARGS to grant scoped permissions, restart. Now /search and /rank work.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import requests

# Make `import src...` work and run subprocesses from the repo root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.providers.base import load_dotenv  # noqa: E402

API = "https://api.telegram.org/bot{token}/{method}"
TELEGRAM_MAX = 4096
# Empty by default ON PURPOSE: shipping a blanket permission bypass would turn a leaked
# bot token into code execution. The user opts into scoped permissions via CLAUDE_ARGS in
# .env (see the security model in the module docstring).
DEFAULT_CLAUDE_ARGS = ""
CLAUDE_TIMEOUT_SEC = 600


def _env_chat_ids() -> set[str]:
    raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "")
    return {c.strip() for c in raw.split(",") if c.strip()}


class TelegramBot:
    def __init__(self):
        load_dotenv()
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN")
        if not self.token:
            sys.exit(
                "TELEGRAM_BOT_TOKEN not set. Create a bot with @BotFather and put the "
                "token in .env. See the module docstring for setup."
            )
        self.allowed = _env_chat_ids()
        self.claude_args = os.environ.get("CLAUDE_ARGS", DEFAULT_CLAUDE_ARGS).split()
        self.allow_freeform = os.environ.get("BOT_ALLOW_FREEFORM", "").strip() in ("1", "true", "yes")
        self.offset = 0
        if not self.allowed:
            print("WARNING: TELEGRAM_ALLOWED_CHAT_IDS is empty. Action commands are "
                  "locked until you add your chat id. Message the bot /whoami to get it.")
        if not self.claude_args:
            print("NOTE: CLAUDE_ARGS is empty, so /search and /rank may stall on a "
                  "permission prompt. Set a scoped CLAUDE_ARGS in .env to enable them "
                  "(see the security model in bot/telegram_bot.py).")

    # ---- Telegram I/O ---------------------------------------------------
    def _call(self, method: str, **params):
        r = requests.post(API.format(token=self.token, method=method),
                          data=params, timeout=70)
        r.raise_for_status()
        return r.json()

    def send(self, chat_id, text: str):
        # Telegram caps messages at 4096 chars; chunk longer replies.
        text = text or "(no output)"
        for i in range(0, len(text), TELEGRAM_MAX):
            self._call("sendMessage", chat_id=chat_id, text=text[i:i + TELEGRAM_MAX])

    # ---- running the agent ---------------------------------------------
    def run_claude(self, prompt: str) -> str:
        """Run `claude -p <prompt>` in the repo and return its final text."""
        try:
            proc = subprocess.run(
                ["claude", "-p", prompt, *self.claude_args],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=CLAUDE_TIMEOUT_SEC,
            )
        except FileNotFoundError:
            return ("The `claude` CLI was not found on this machine. Install Claude Code "
                    "or set its path so the bot can run skills.")
        except subprocess.TimeoutExpired:
            return f"That took longer than {CLAUDE_TIMEOUT_SEC // 60} min and was stopped."
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 and not out:
            return f"Run failed: {(proc.stderr or '').strip()[-800:]}"
        return out or "(the agent produced no text output)"

    def run_python(self, *args: str) -> str:
        proc = subprocess.run([sys.executable, "-m", "src.cli", *args],
                              cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        return ((proc.stdout or "") + (proc.stderr or "")).strip()

    # ---- message handling ----------------------------------------------
    def handle(self, chat_id, text: str):
        cid = str(chat_id)
        cmd, _, rest = text.partition(" ")
        cmd = cmd.lower().lstrip("/")
        rest = rest.strip()

        if cmd in ("start", "help"):
            self.send(chat_id,
                "Home-search agent.\n"
                "/search - run a full search, reply with top picks\n"
                "/rank <address> - evaluate one property\n"
                "/usage - data-provider quota this month\n"
                "/whoami - your chat id (for the allowlist)\n"
                "Or just describe what you want and I will figure it out.")
            return
        if cmd == "whoami":
            self.send(chat_id, f"Your chat id is: {cid}\n"
                               f"Add it to TELEGRAM_ALLOWED_CHAT_IDS in .env, then "
                               f"restart the bot.")
            return

        if self.allowed and cid not in self.allowed:
            self.send(chat_id, "Not authorized. Ask the owner to add your chat id.")
            print(f"Ignored command from non-allowlisted chat {cid}")
            return
        if not self.allowed:
            self.send(chat_id, "Bot has no allowlist yet. Send /whoami and add your id.")
            return

        if cmd == "usage":
            self.send(chat_id, self.run_python("usage"))
            return
        if cmd == "search":
            self.send(chat_id, "Searching... this can take a few minutes.")
            self.send(chat_id, self.run_claude("/search-homes"))
            return
        if cmd == "rank":
            if not rest:
                self.send(chat_id, "Usage: /rank <full address>")
                return
            self.send(chat_id, f"Looking at {rest} ...")
            self.send(chat_id, self.run_claude(f"/rank-address {rest}"))
            return

        # Free text: only when explicitly enabled (widest injection surface).
        if not self.allow_freeform:
            self.send(chat_id,
                "I only run /search, /rank <address>, and /usage. To enable open-ended "
                "chat, set BOT_ALLOW_FREEFORM=1 in .env (and keep CLAUDE_ARGS scoped).")
            return
        self.send(chat_id, "Working on it...")
        self.send(chat_id, self.run_claude(text))

    # ---- main loop ------------------------------------------------------
    def poll_forever(self):
        print(f"Bot online. Allowlist: {sorted(self.allowed) or '(empty)'}. "
              f"Ctrl-C to stop.")
        while True:
            try:
                resp = self._call("getUpdates", offset=self.offset, timeout=50)
            except Exception as e:
                print(f"getUpdates error: {e}; retrying in 5s")
                time.sleep(5)
                continue
            for upd in resp.get("result", []):
                self.offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg or "text" not in msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg["text"].strip()
                print(f"<- {chat_id}: {text[:80]}")
                try:
                    self.handle(chat_id, text)
                except Exception as e:
                    self.send(chat_id, f"Error: {e}")
                    print(f"handler error: {e}")


if __name__ == "__main__":
    TelegramBot().poll_forever()

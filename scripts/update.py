#!/usr/bin/env python3
"""Twice-daily bracket tracker — orchestrates one update run.

Steps:
  1. Scrape the leaderboard for the current standing (rank, P/W/L, points, ceiling).
  2. Ask the contest for an official STANDING reply via AgentMail (cross-check + showcase).
  3. Write data/standing.json, append data/history.csv.
  4. Re-render the auto-generated block in README.md.
  5. Email a digest to your Gmail via AgentMail.

Usage:
  python scripts/update.py                 # full run (scrape + AgentMail + email)
  python scripts/update.py --no-email      # skip the email
  python scripts/update.py --no-agentmail  # skip the STANDING email + digest (scrape only)
  python scripts/update.py --period AM     # label the email "AM" / "PM" (auto by hour if omitted)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

# make sibling modules importable when run as `python scripts/update.py`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agentcup
import agentmail_client as am
import render

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "bracket.json")
README_PATH = os.path.join(ROOT, "README.md")
DATA_DIR = os.path.join(ROOT, "data")
STANDING_JSON = os.path.join(DATA_DIR, "standing.json")
HISTORY_CSV = os.path.join(DATA_DIR, "history.csv")

HISTORY_FIELDS = [
    "ts", "rank", "movement", "played", "won", "lost",
    "points", "ceiling", "champion", "champion_alive",
    "matches_decided", "matches_total",
]


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_history() -> list[dict]:
    if not os.path.exists(HISTORY_CSV):
        return []
    with open(HISTORY_CSV, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def append_history(snap: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    new_file = not os.path.exists(HISTORY_CSV)
    with open(HISTORY_CSV, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({k: snap.get(k, "") for k in HISTORY_FIELDS})


def write_standing_json(snap: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(STANDING_JSON, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, indent=2)


def update_readme(block: str) -> None:
    with open(README_PATH, encoding="utf-8") as fh:
        content = fh.read()
    s, e = render.START, render.END
    if s in content and e in content:
        head = content.split(s)[0]
        tail = content.split(e)[1]
        content = head + block + tail
    else:  # markers missing — append the block
        content = content.rstrip() + "\n\n" + block + "\n"
    with open(README_PATH, "w", encoding="utf-8") as fh:
        fh.write(content)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-agentmail", action="store_true")
    ap.add_argument("--period", choices=["AM", "PM"], default=None)
    args = ap.parse_args()

    cfg = load_config()
    now = datetime.now(timezone.utc)
    period = args.period or ("AM" if now.hour < 12 else "PM")

    # 1) scrape standing
    snap: dict = {"ts": now.isoformat(timespec="seconds")}
    try:
        scraped = agentcup.get_standing(
            cfg["links"]["leaderboard"], cfg["org_handle"], cfg["bracket_id"]
        )
        snap.update(scraped)
        print(f"[scrape] rank={snap.get('rank')} pts={snap.get('points')}/{snap.get('ceiling')} "
              f"P-W-L={snap.get('played')}-{snap.get('won')}-{snap.get('lost')}")
    except Exception as exc:
        print(f"[scrape] FAILED: {exc}")

    # 2) AgentMail official STANDING reply (authoritative for the headline numbers)
    if not args.no_agentmail:
        try:
            reply = am.request_standing(cfg["send_from_inbox"], cfg["contest_address"])
            if reply:
                snap["standing_email"] = reply
                # The contest reply is the source of truth for rank/points/ceiling.
                # Overlay any value it provides on top of the (brittle) scrape.
                parsed = am.parse_standing_reply(reply)
                for key, val in parsed.items():
                    if val is not None:
                        snap[key] = val
                print(f"[agentmail] STANDING reply parsed: rank={snap.get('rank')} "
                      f"of {snap.get('field_size')} pts={snap.get('points')}/{snap.get('ceiling')}")
            else:
                print("[agentmail] no STANDING reply within the wait window")
        except Exception as exc:
            print(f"[agentmail] STANDING request skipped: {exc}")

    # 3) persist
    history = load_history()
    prev = history[-1] if history else None
    write_standing_json(snap)
    append_history(snap)

    # 4) render README
    history_after = load_history()  # includes this run
    block = render.render_readme_block(cfg, snap, prev, history_after)
    update_readme(block)
    print("[render] README updated")

    # 5) email digest
    if not args.no_agentmail and not args.no_email:
        try:
            subject, text = render.email_body(cfg, snap, prev, period)
            am.send_digest(cfg["send_from_inbox"], cfg["digest_to"], subject, text)
            print(f"[email] digest sent to {cfg['digest_to']}")
        except Exception as exc:
            print(f"[email] digest skipped: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

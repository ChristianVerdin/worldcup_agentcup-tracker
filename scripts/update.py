#!/usr/bin/env python3
"""Bracket tracker — orchestrates one update run.

Source of truth is LOCAL: scripts/scoring.py scores my picks against
data/results.json. The public leaderboard has scored unreliably, so the scrape
and the AgentMail STANDING reply are demoted to a cross-check — they can supply
things we can't compute locally (my rank among others, field size), but if they
disagree with the local score on any earned/ceiling/W-L field we log the
discrepancy and keep the local number.

Steps:
  1. Score locally from bracket.json + data/results.json  (authoritative).
  2. (unless --offline) Cross-check against the scraped leaderboard; log diffs.
  3. (unless --offline/--no-agentmail) Cross-check against the AgentMail reply;
     log diffs; pull rank/field_size from it.
  4. Write data/standing.json, append data/history.csv.
  5. Re-render the auto-generated block in README.md.
  6. (unless --offline/--no-email) Email a digest via AgentMail.

Usage:
  python scripts/update.py                 # local score + cross-check + email
  python scripts/update.py --offline       # local score only (no network at all)
  python scripts/update.py --no-email      # skip the digest email
  python scripts/update.py --no-agentmail  # skip STANDING + digest (scrape cross-check only)
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

import render        # stdlib-only
import scoring       # stdlib-only
# agentcup / agentmail_client are imported lazily so the local path needs no
# network dependencies (requests, bs4, agentmail) installed.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "bracket.json")
RESULTS_PATH = os.path.join(ROOT, "data", "results.json")
README_PATH = os.path.join(ROOT, "README.md")
DATA_DIR = os.path.join(ROOT, "data")
STANDING_JSON = os.path.join(DATA_DIR, "standing.json")
HISTORY_CSV = os.path.join(DATA_DIR, "history.csv")

HISTORY_FIELDS = [
    "ts", "rank", "movement", "played", "won", "lost",
    "points", "ceiling", "champion", "champion_alive",
    "matches_decided", "matches_total",
]

# Fields the LOCAL engine owns. If an external source reports a different value
# for one of these, we log it and keep local.
AUTHORITATIVE_FIELDS = ["points", "ceiling", "played", "won", "lost", "champion_alive"]


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def load_results() -> dict:
    with open(RESULTS_PATH, encoding="utf-8") as fh:
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


def cross_check(local: dict, external: dict, source: str) -> None:
    """Log any field where an external source disagrees with the local score.

    Local always wins; this only surfaces the discrepancy so a real scoring bug
    (ours or the contest's) is visible in the run log.
    """
    for key in AUTHORITATIVE_FIELDS:
        ext = external.get(key)
        loc = local.get(key)
        if ext is not None and ext != loc:
            print(f"[discrepancy] {source}.{key}={ext} != local.{key}={loc} — keeping local")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true",
                    help="local scoring only — no scrape, no AgentMail, no email")
    ap.add_argument("--no-email", action="store_true")
    ap.add_argument("--no-agentmail", action="store_true")
    ap.add_argument("--no-scrape", action="store_true")
    ap.add_argument("--period", choices=["AM", "PM"], default=None)
    ap.add_argument("--rank", type=int, default=None,
                    help="hand-read rank off the leaderboard when the scrape/AgentMail "
                         "reply return it blank; overrides any scraped rank")
    ap.add_argument("--field-size", type=int, default=None,
                    help="total number of ranked brackets (e.g. 60), read off the board")
    args = ap.parse_args()

    cfg = load_config()
    results_doc = load_results()
    now = datetime.now(timezone.utc)
    period = args.period or ("AM" if now.hour < 12 else "PM")

    # 1) LOCAL scoring — authoritative.
    local = scoring.compute_standing(cfg, results_doc)
    snap: dict = {"ts": now.isoformat(timespec="seconds")}
    snap.update(local)
    print(f"[local] pts={local['points']}/{local['ceiling']} "
          f"P-W-L={local['played']}-{local['won']}-{local['lost']} "
          f"champion={local['champion']} "
          f"{'alive' if local['champion_alive'] else 'out'} "
          f"decided={local['matches_decided']}/{local['matches_total']}")

    # 2) leaderboard scrape — cross-check only; contributes rank we can't compute.
    if not args.offline and not args.no_scrape:
        try:
            import agentcup  # lazy: needs requests + bs4
            scraped = agentcup.get_standing(
                cfg["links"]["leaderboard"], cfg["org_handle"], cfg["bracket_id"]
            )
            cross_check(local, scraped, "scrape")
            for key in ("rank", "movement", "field_size", "board_updated"):
                if scraped.get(key) is not None:
                    snap[key] = scraped[key]
            print(f"[scrape] rank={snap.get('rank')} (cross-checked)")
        except Exception as exc:
            print(f"[scrape] skipped: {exc}")

    # 3) AgentMail official STANDING reply — cross-check + rank; never overrides score.
    if not args.offline and not args.no_agentmail:
        try:
            import agentmail_client as am  # lazy: needs agentmail SDK
            reply = am.request_standing(cfg["send_from_inbox"], cfg["contest_address"])
            if reply:
                snap["standing_email"] = reply
                parsed = am.parse_standing_reply(reply)
                cross_check(local, parsed, "agentmail")
                for key in ("rank", "field_size"):
                    if parsed.get(key) is not None:
                        snap[key] = parsed[key]
                print(f"[agentmail] rank={snap.get('rank')} of {snap.get('field_size')} (cross-checked)")
            else:
                print("[agentmail] no STANDING reply within the wait window")
        except Exception as exc:
            print(f"[agentmail] skipped: {exc}")

    # 3b) manual rank override — the leaderboard is public but the scrape and the
    # AgentMail STANDING reply keep returning rank blank, so a value read straight
    # off the board and passed in always wins.
    if args.rank is not None:
        snap["rank"] = args.rank
        print(f"[manual] rank={snap['rank']} (hand-read from leaderboard)")
    if args.field_size is not None:
        snap["field_size"] = args.field_size

    # 4) persist
    history = load_history()
    prev = history[-1] if history else None
    write_standing_json(snap)
    append_history(snap)

    # 5) render README + regenerate the rank-history chart (SVG, both themes)
    history_after = load_history()  # includes this run
    block = render.render_readme_block(cfg, snap, prev, history_after)
    update_readme(block)
    print("[render] README updated")
    try:
        import chart  # stdlib-only
        chart.render_all(ROOT)
        print("[chart] rank-history SVGs regenerated")
    except Exception as exc:
        print(f"[chart] skipped: {exc}")

    # 6) email digest
    if not args.offline and not args.no_agentmail and not args.no_email:
        try:
            import agentmail_client as am  # lazy
            subject, text = render.email_body(cfg, snap, prev, period)
            am.send_digest(cfg["send_from_inbox"], cfg["digest_to"], subject, text)
            print(f"[email] digest sent to {cfg['digest_to']}")
        except Exception as exc:
            print(f"[email] digest skipped: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

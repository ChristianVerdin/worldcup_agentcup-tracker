"""Scrape the AgentMail World Cup leaderboard for one entrant's standing.

The leaderboard at agentcup.world is server-rendered HTML, so a plain GET +
BeautifulSoup is enough — no headless browser required. We locate the entrant's
row by the unique bracket-id anchor (robust to CSS/class changes) and read the
numbers out of the row cells.

If the site's markup ever changes, only `parse_standing` needs adjusting.
"""

from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (compatible; agentcup-tracker/1.0; "
    "+https://github.com/agentmail-world-cup-tracker)"
)


def fetch_html(url: str, timeout: int = 30) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _first_int(text: str):
    m = re.search(r"\d+", text or "")
    return int(m.group()) if m else None


def parse_standing(html: str, handle: str, bracket_id: str) -> dict:
    """Return a dict of this entrant's standing parsed from the leaderboard HTML."""
    soup = BeautifulSoup(html, "html.parser")

    out = {
        "rank": None,
        "movement": None,        # +N / -N change since last result, if shown
        "played": None,
        "won": None,
        "lost": None,
        "points": None,          # points earned so far
        "ceiling": None,         # max points still reachable
        "champion": None,        # predicted champion (display name)
        "champion_alive": None,  # False if the champion has been eliminated
        "matches_decided": None, # e.g. 3  (out of total)
        "matches_total": None,   # e.g. 32
        "board_updated": None,   # e.g. "3h ago"
    }

    # ---- locate this entrant's row via the unique bracket-id anchor ----
    row = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if bracket_id in href or f"/b/{bracket_id}" in href:
            row = a.find_parent("tr") or a.find_parent(
                lambda tag: tag.name in ("li", "div") and tag.find("img", alt=re.compile("Picked to win", re.I))
            )
            if row is not None:
                break

    if row is not None:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if not cells:  # non-table layout: split the row text
            cells = [s for s in row.get_text("|", strip=True).split("|") if s]

        # champion + alive state come from the flag image's alt text
        champ_img = row.find("img", alt=re.compile(r"Picked to win", re.I))
        if champ_img:
            alt = champ_img.get("alt", "")
            out["champion_alive"] = "eliminated" not in alt.lower()
            name = re.sub(r"(?i)picked to win:\s*", "", alt)
            name = re.sub(r"\s*\(eliminated\)\s*", "", name, flags=re.I).strip()
            out["champion"] = name or None

        # rank + movement live in the first cell, e.g. "1" or "1▲42" / "38▼37"
        if cells:
            out["rank"] = _first_int(cells[0])
            mv = re.search(r"([▲▼])\s*(\d+)", cells[0])
            if mv:
                sign = 1 if mv.group(1) == "▲" else -1
                out["movement"] = sign * int(mv.group(2))

        # points are the "earned / ceiling" cell, e.g. "2/ 59"
        for c in cells:
            m = re.search(r"(\d+)\s*/\s*(\d+)", c)
            if m:
                out["points"] = int(m.group(1))
                out["ceiling"] = int(m.group(2))
                break

        # P / W / L are the three pure-integer cells (in order), excluding rank/pts
        pure_ints = [int(c) for c in cells if re.fullmatch(r"\d+", c.strip())]
        if len(pure_ints) >= 3:
            out["played"], out["won"], out["lost"] = pure_ints[0], pure_ints[1], pure_ints[2]

    # ---- global board context (regex over the whole page text) ----
    text = soup.get_text(" ", strip=True)
    md = re.search(r"(\d+)\s+of\s+(\d+)\s+matches?\s+decided", text, re.I)
    if md:
        out["matches_decided"], out["matches_total"] = int(md.group(1)), int(md.group(2))
    up = re.search(r"Updated\s+(\d+\s*[smhd]\w*\s+ago|[\w ]+?ago)", text, re.I)
    if up:
        out["board_updated"] = up.group(1).strip()

    return out


def get_standing(leaderboard_url: str, handle: str, bracket_id: str) -> dict:
    return parse_standing(fetch_html(leaderboard_url), handle, bracket_id)

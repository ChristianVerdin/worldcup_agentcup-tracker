#!/usr/bin/env python3
"""Render the leaderboard-rank-over-time chart from data/history.csv.

Pure stdlib: builds a self-contained SVG (no external fonts/assets) so it renders
identically wherever it's embedded. Two themes are written — light and dark — and
the README swaps them with a <picture> element that follows the reader's color
scheme. Rank is drawn on an INVERTED axis (#1 at the top, "lower is better").

Run standalone (`python scripts/chart.py`) or via scripts/update.py, which calls
render_all() so the chart always matches the committed history.
"""

from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_CSV = os.path.join(ROOT, "data", "history.csv")
ASSETS_DIR = os.path.join(ROOT, "assets")

# Canvas
W, H = 860, 430
L, R, T, B = 70, 764, 110, 378          # plot rect edges
PLOT_W, PLOT_H = R - L, B - T

RANK_TOP, RANK_BOT = 1, 48               # y-domain (inverted: 1 at top)
RANK_TICKS = [1, 10, 20, 30, 40]

# Portugal (the champion pick) knocked out in the Round of 16 — the pivot of the
# whole story, when the rank fell off a cliff.
EVENT_TS = datetime.fromisoformat("2026-07-06T21:09:03+00:00")

THEMES = {
    "light": {
        "surface": "#fcfcfb", "border": "rgba(11,11,11,0.10)",
        "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "axis": "#c3c2b7",
        "series": "#2a78d6", "event": "#d03b3b",
        "chip": "#f2f1ec", "ring": "#fcfcfb",
    },
    "dark": {
        "surface": "#1a1a19", "border": "rgba(255,255,255,0.12)",
        "ink": "#ffffff", "ink2": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "axis": "#383835",
        "series": "#3987e5", "event": "#e05a5a",
        "chip": "#26261f", "ring": "#1a1a19",
    },
}

FONT = "system-ui,-apple-system,'Segoe UI',Roboto,sans-serif"


def _load_rank_series() -> list[tuple[datetime, int]]:
    pts: list[tuple[datetime, int]] = []
    with open(HISTORY_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rk = (row.get("rank") or "").strip()
            if not rk:
                continue
            pts.append((datetime.fromisoformat(row["ts"]), int(rk)))
    pts.sort(key=lambda p: p[0])
    return pts


def render(theme_name: str, pts: list[tuple[datetime, int]]) -> str:
    c = THEMES[theme_name]
    t0, t1 = pts[0][0], pts[-1][0]
    span = (t1 - t0).total_seconds() or 1.0

    def x_of(dt: datetime) -> float:
        return L + (dt - t0).total_seconds() / span * PLOT_W

    def y_of(rank: float) -> float:
        return T + (rank - RANK_TOP) / (RANK_BOT - RANK_TOP) * PLOT_H

    peak_rank = min(r for _, r in pts)
    low_rank = max(r for _, r in pts)
    final_rank = pts[-1][1]

    s: list[str] = []
    s.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" font-family="{FONT}" '
        f'role="img" aria-label="Leaderboard rank over time: peaked at #{peak_rank}, '
        f'fell to #{low_rank} after Portugal was eliminated, finished #{final_rank} of 62.">'
    )
    # card
    s.append(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="16" '
             f'fill="{c["surface"]}" stroke="{c["border"]}" stroke-width="1"/>')

    # header: title + subtitle
    s.append(f'<text x="28" y="42" font-size="20" font-weight="700" '
             f'fill="{c["ink"]}">Leaderboard rank over time</text>')
    s.append(f'<text x="28" y="64" font-size="12.5" fill="{c["ink2"]}">'
             f'AgentMail World Cup 2026 &#183; 62 brackets &#183; lower is better '
             f'(#1 = top of the board)</text>')

    # stat chips (top-right)
    chips = [("Peak", f"#{peak_rank}"), ("Low", f"#{low_rank}"), ("Final", f"#{final_rank} / 62")]
    cw, ch, gap = 92, 34, 8
    x = W - 28 - (cw * len(chips) + gap * (len(chips) - 1))
    for label, val in chips:
        s.append(f'<rect x="{x:.0f}" y="26" width="{cw}" height="{ch}" rx="8" fill="{c["chip"]}"/>')
        s.append(f'<text x="{x+10:.0f}" y="40" font-size="10" letter-spacing="0.5" '
                 f'fill="{c["muted"]}">{label.upper()}</text>')
        s.append(f'<text x="{x+10:.0f}" y="54" font-size="14" font-weight="700" '
                 f'fill="{c["ink"]}">{val}</text>')
        x += cw + gap

    # horizontal gridlines + y labels
    for rk in RANK_TICKS:
        y = y_of(rk)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{R}" y2="{y:.1f}" '
                 f'stroke="{c["grid"]}" stroke-width="1"/>')
        s.append(f'<text x="{L-10}" y="{y+4:.1f}" font-size="11" text-anchor="end" '
                 f'fill="{c["muted"]}" font-variant-numeric="tabular-nums">#{rk}</text>')

    # x date ticks
    d = datetime(t0.year, t0.month, t0.day, tzinfo=t0.tzinfo)
    while d <= t1 + timedelta(days=1):
        if d >= t0 - timedelta(hours=6):
            xp = x_of(max(d, t0))
            s.append(f'<line x1="{xp:.1f}" y1="{T}" x2="{xp:.1f}" y2="{B}" '
                     f'stroke="{c["grid"]}" stroke-width="1" opacity="0.5"/>')
            s.append(f'<text x="{xp:.1f}" y="{B+22}" font-size="11" text-anchor="middle" '
                     f'fill="{c["muted"]}">{d.strftime("%b %-d")}</text>')
        d += timedelta(days=4)

    # baseline
    s.append(f'<line x1="{L}" y1="{B}" x2="{R}" y2="{B}" stroke="{c["axis"]}" stroke-width="1.5"/>')

    # event marker: vertical dashed line + flag
    ex = x_of(EVENT_TS)
    s.append(f'<line x1="{ex:.1f}" y1="{T-4}" x2="{ex:.1f}" y2="{B}" '
             f'stroke="{c["event"]}" stroke-width="1.5" stroke-dasharray="4 4" opacity="0.85"/>')
    s.append(f'<path d="M{ex:.1f} {T-4} l 62 0 l 0 15 l -62 0 z" fill="{c["event"]}"/>')
    s.append(f'<text x="{ex+6:.1f}" y="{T+7:.1f}" font-size="10.5" font-weight="700" '
             f'fill="#ffffff">R16 EXIT</text>')
    s.append(f'<text x="{ex+8:.1f}" y="{T+34:.1f}" font-size="12" font-weight="600" '
             f'fill="{c["event"]}">Portugal eliminated</text>')
    s.append(f'<text x="{ex+8:.1f}" y="{T+50:.1f}" font-size="11" '
             f'fill="{c["ink2"]}">champion pick busted</text>')

    # rank line
    pathd = " ".join(
        ("M" if i == 0 else "L") + f"{x_of(dt):.1f} {y_of(rk):.1f}"
        for i, (dt, rk) in enumerate(pts)
    )
    s.append(f'<path d="{pathd}" fill="none" stroke="{c["series"]}" stroke-width="2.5" '
             f'stroke-linejoin="round" stroke-linecap="round"/>')

    # annotated markers
    def marker(dt, rk, dot=True):
        cx, cy = x_of(dt), y_of(rk)
        if dot:
            s.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{c["series"]}" '
                     f'stroke="{c["ring"]}" stroke-width="2"/>')
        return cx, cy

    # peak (#1, early lead)
    px, py = marker(pts[0][0], pts[0][1])
    s.append(f'<text x="{px+10:.1f}" y="{py+20:.1f}" font-size="12" font-weight="600" '
             f'fill="{c["ink2"]}">Led early at #{peak_rank}</text>')

    # low point (worst rank)
    low_dt = next(dt for dt, rk in pts if rk == low_rank)
    lx, ly = marker(low_dt, low_rank)
    s.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="5" fill="{c["event"]}" '
             f'stroke="{c["ring"]}" stroke-width="2"/>')
    s.append(f'<text x="{lx+12:.1f}" y="{ly+5:.1f}" font-size="12" font-weight="700" '
             f'fill="{c["event"]}">#{low_rank} low</text>')

    # final
    fx, fy = marker(pts[-1][0], final_rank)
    s.append(f'<text x="{fx+12:.1f}" y="{fy-2:.1f}" font-size="15" font-weight="800" '
             f'fill="{c["ink"]}">#{final_rank}</text>')
    s.append(f'<text x="{fx+12:.1f}" y="{fy+14:.1f}" font-size="11" '
             f'fill="{c["ink2"]}">final</text>')

    s.append("</svg>")
    return "\n".join(s)


def render_all(root: str = ROOT) -> list[str]:
    """Write both theme SVGs to assets/; returns the paths written."""
    global ASSETS_DIR
    ASSETS_DIR = os.path.join(root, "assets")
    os.makedirs(ASSETS_DIR, exist_ok=True)
    pts = _load_rank_series()
    written = []
    for name in ("light", "dark"):
        path = os.path.join(ASSETS_DIR, f"rank-history-{name}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(name, pts))
        written.append(path)
    return written


if __name__ == "__main__":
    for p in render_all():
        print(f"[chart] wrote {os.path.relpath(p, ROOT)}")

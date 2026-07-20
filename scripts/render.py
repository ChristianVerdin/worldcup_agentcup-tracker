"""Rendering: standing snapshot -> README block, bracket grid, and email body."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

ROUND_LABELS = {
    "R32": "Round of 32",
    "R16": "Round of 16",
    "QF": "Quarterfinals",
    "SF": "Semifinals",
    "F": "Final (champion)",
    "3P": "Third place",
}
ROUND_ORDER = ["R32", "R16", "QF", "SF", "F", "3P"]

# Markers in README.md that bound the auto-generated section.
START = "<!-- STANDING:START -->"
END = "<!-- STANDING:END -->"


def _to_int(value):
    """Coerce CSV/string values to int; return None if blank or non-numeric."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _d(value, dash: str = "—"):
    """Display helper: render None / missing values as an em dash."""
    return dash if value is None or value == "" else value


def _ct(now_utc: datetime) -> str:
    """Render a UTC time as US Central (UTC-5 in summer). Adjust offset for CST if needed."""
    ct = now_utc.astimezone(timezone(timedelta(hours=-5)))
    return ct.strftime("%b %d, %Y %I:%M %p CT")


def _name(cfg: dict, code: str) -> str:
    return cfg["codes"].get(code, code)


def rank_badge(rank) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "🏆")


def movement_str(delta) -> str:
    delta = _to_int(delta)
    if not delta:
        return ""
    if delta > 0:
        return f" ▲{delta}"
    return f" ▼{abs(delta)}"


def bracket_grid(cfg: dict) -> str:
    """Markdown of picks by round (champion highlighted)."""
    picks, scoring = cfg["picks"], cfg["scoring"]
    lines = ["| Round | Pts/correct | Picks |", "| --- | :-: | --- |"]
    for rnd in ROUND_ORDER:
        keys = sorted(
            [k for k in picks if k.split("-")[0] == rnd],
            key=lambda k: int(k.split("-")[1]) if "-" in k else 0,
        )
        if not keys:
            continue
        names = []
        for k in keys:
            n = _name(cfg, picks[k])
            if rnd == "F":
                n = f"**{n}** 🏆"
            names.append(n)
        lines.append(f"| {ROUND_LABELS[rnd]} | {scoring.get(rnd, '')} | {' · '.join(names)} |")
    return "\n".join(lines)


def history_table(history: list[dict], limit: int = 8) -> str:
    if not history:
        return "_No history yet — this is the first run._"
    rows = history[-limit:]
    lines = ["| Checked (UTC) | Rank | Points | Ceiling | P–W–L |", "| --- | :-: | :-: | :-: | :-: |"]
    for r in rows:
        ts = (r.get("ts") or "")[:16].replace("T", " ")
        parts = [r.get("played"), r.get("won"), r.get("lost")]
        if all(p in (None, "") for p in parts):
            pwl = "—"
        else:
            pwl = f"{_d(parts[0],'–')}–{_d(parts[1],'–')}–{_d(parts[2],'–')}"
        lines.append(
            f"| {ts} | {_d(r.get('rank'),'–')} | {_d(r.get('points'),'–')} | {_d(r.get('ceiling'),'–')} | {pwl} |"
        )
    return "\n".join(lines)


def render_readme_block(cfg: dict, snap: dict, prev: dict | None, history: list[dict]) -> str:
    """The full auto-generated section that goes between the README markers."""
    now = datetime.now(timezone.utc)
    badge = rank_badge(snap.get("rank"))

    # rank movement: prefer board-reported movement, else compute vs previous snapshot
    delta_rank = snap.get("movement")
    if delta_rank is None:
        pr, sr = _to_int(prev.get("rank")) if prev else None, _to_int(snap.get("rank"))
        if pr is not None and sr is not None:
            delta_rank = pr - sr  # positive = climbed
    delta_pts = None
    pp, sp = (_to_int(prev.get("points")) if prev else None), _to_int(snap.get("points"))
    if pp is not None and sp is not None:
        delta_pts = sp - pp

    champ = snap.get("champion") or _name(cfg, cfg["champion_pick"])
    alive = snap.get("champion_alive")
    champ_state = "✅ still alive" if alive else ("❌ eliminated" if alive is False else "—")

    total_matches = snap.get("matches_total") or 32
    final = (
        snap.get("matches_decided") is not None
        and snap["matches_decided"] >= total_matches
    )

    decided = ""
    if snap.get("matches_decided") is not None:
        total = snap.get("matches_total") or 32
        decided = f"{snap['matches_decided']} of {total} matches decided"
        if snap.get("board_updated"):
            decided += f" · board updated {snap['board_updated']}"

    rank_text = f"Rank #{_d(snap.get('rank'))}"
    if snap.get("field_size"):
        rank_text += f" of {snap['field_size']}"
    rank_line = f"### {badge} {rank_text}{movement_str(delta_rank)}{' — Final' if final else ''}"
    pts_line = f"**{_d(snap.get('points'))} pts** earned · ceiling **{_d(snap.get('ceiling'))}**"
    if delta_pts:
        pts_line += f" · {'+' if delta_pts > 0 else ''}{delta_pts} since last check"

    pwl = f"{_d(snap.get('played'))} played · {_d(snap.get('won'))} won · {_d(snap.get('lost'))} lost"

    champ_actual = snap.get("champion_actual")
    champion_line = f"Predicted champion: **{champ}** — {champ_state}"
    if final and champ_actual:
        champion_line += f"\nTournament won by **{champ_actual}** 🏆"

    if final:
        footer_note = (
            f"_Final standing — the tournament is over; all {total_matches} knockout matches "
            "are decided. Scored locally from `data/results.json`. The twice-daily "
            "[GitHub Actions](.github/workflows/update.yml) refresh has been retired._"
        )
    else:
        footer_note = (
            f"_Last checked: {_ct(now)} ({now.strftime('%Y-%m-%dT%H:%MZ')}). Scored locally from "
            "`data/results.json`; refreshed twice daily by [GitHub Actions](.github/workflows/update.yml), "
            "with the live leaderboard and the [AgentMail](https://agentmail.to) reply kept as a cross-check._"
        )

    standing_note = ""
    if snap.get("standing_email"):
        standing_note = (
            "\n> **AgentMail cross-check** (live reply from `worldcup@agentmail.to`):\n>\n"
            + "\n".join(f"> {ln}" for ln in snap["standing_email"].splitlines() if ln.strip())
            + "\n"
        )

    links = cfg["links"]
    block = f"""{START}

{rank_line}

{pts_line}
{pwl}
{champion_line}
{('_' + decided + '_') if decided else ''}

[![Live bracket card]({links['og_card']})]({links['my_bracket']})

{footer_note}
{standing_note}
#### My picks

{bracket_grid(cfg)}

#### History

{history_table(history)}

[Leaderboard]({links['leaderboard']}) · [My bracket]({links['my_bracket']}) · [Rules]({links['rules']})

{END}"""
    return block


def email_body(cfg: dict, snap: dict, prev: dict | None, period: str) -> tuple[str, str]:
    """Return (subject, text) for the digest email."""
    now = datetime.now(timezone.utc)
    badge = rank_badge(snap.get("rank"))
    champ = snap.get("champion") or _name(cfg, cfg["champion_pick"])
    alive = snap.get("champion_alive")
    champ_state = "still alive" if alive else ("ELIMINATED" if alive is False else "unknown")

    delta_rank = snap.get("movement")
    if delta_rank is None:
        pr, sr = _to_int(prev.get("rank")) if prev else None, _to_int(snap.get("rank"))
        if pr is not None and sr is not None:
            delta_rank = pr - sr
    move = ""
    if delta_rank:
        move = f" ({'up' if delta_rank > 0 else 'down'} {abs(delta_rank)} since last check)"

    rank_disp = f"#{_d(snap.get('rank'), '?')}"
    if snap.get("field_size"):
        rank_disp += f" of {snap['field_size']}"
    subject = f"WC Bracket — {rank_disp} · {_d(snap.get('points'), '?')} pts ({period})"

    lines = [
        f"{badge} Rank {rank_disp}{move}",
        f"{_d(snap.get('points'), '?')} pts earned · ceiling {_d(snap.get('ceiling'), '?')}",
        f"{_d(snap.get('played'), '?')} played · {_d(snap.get('won'), '?')} won · {_d(snap.get('lost'), '?')} lost",
        f"Champion (Portugal -> {champ}): {champ_state}",
    ]
    if snap.get("matches_decided") is not None:
        lines.append(f"{snap['matches_decided']} of {snap.get('matches_total',32)} matches decided")
    lines.append("")
    if snap.get("standing_email"):
        lines.append("Official AgentMail reply:")
        lines.append(snap["standing_email"])
        lines.append("")
    lines.append(f"Leaderboard: {cfg['links']['leaderboard']}")
    lines.append(f"Your bracket: {cfg['links']['my_bracket']}")
    lines.append(f"Checked {_ct(now)}")

    return subject, "\n".join(lines)

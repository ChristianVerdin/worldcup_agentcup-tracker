"""Independent, offline bracket scoring — the authoritative source of truth.

The public AgentMail leaderboard has scored unreliably, so this module computes
the standing locally from two data files and nothing else:

  * bracket.json   — my picks, the R32 matchups, team codes, the scoring table.
  * data/results.json — the actual winner of every DECIDED knockout match.

Everything (earned points, ceiling, played/won/lost, champion-alive) is derived
here so a new result is a one-line edit in results.json, never a code change.

Scoring rules (per https://agentcup.world/rules):
  R32 = 1 pt, R16 = 2, QF = 3, SF = 4, Final = 5, Third-place = 3.
  A pick scores only if that exact team actually wins that match.
  A team eliminated earlier can't win the later matches you placed it in — those
  picks score 0 (no penalty). "Ceiling" = points earned + the most still
  reachable given which of my advanced teams are still alive.
"""

from __future__ import annotations

ROUND_ORDER = ["R32", "R16", "QF", "SF", "F", "3P"]


def round_of(match_id: str) -> str:
    """'R32-1' -> 'R32', 'F' -> 'F', '3P' -> '3P'."""
    return match_id.split("-")[0]


def bracket_tree() -> dict[str, list[str]]:
    """Feeder map: each match id -> the two match ids that feed it.

    The knockout shape is fixed, so this is structure (not results) and stays in
    code. R32 matches have no feeders (their teams come from bracket.json).
    """
    tree: dict[str, list[str]] = {}
    for k in range(1, 9):   # R16-1..8  <- R32-(2k-1), R32-(2k)
        tree[f"R16-{k}"] = [f"R32-{2*k-1}", f"R32-{2*k}"]
    for k in range(1, 5):   # QF-1..4   <- R16-(2k-1), R16-(2k)
        tree[f"QF-{k}"] = [f"R16-{2*k-1}", f"R16-{2*k}"]
    for k in range(1, 3):   # SF-1..2   <- QF-(2k-1), QF-(2k)
        tree[f"SF-{k}"] = [f"QF-{2*k-1}", f"QF-{2*k}"]
    tree["F"] = ["SF-1", "SF-2"]
    # 3P is contested by the two SF losers; handled specially, no winner-feeders.
    return tree


def participants(match_id: str, matchups: dict, tree: dict, results: dict) -> list[str]:
    """The two real teams in a match: from bracket.json for R32, else the actual
    winners of the two feeder matches (present whenever this match is decided)."""
    if round_of(match_id) == "R32":
        return list(matchups.get(match_id, []))
    if match_id == "3P":
        return []  # losers of SF-1/SF-2 — not needed for elimination tracking
    return [results.get(f) for f in tree.get(match_id, [])]


def eliminated_teams(matchups: dict, results: dict) -> set[str]:
    """Every team that lost a decided match. A team is 'alive' iff it is not here.

    For each decided match the loser is the participant that isn't the winner —
    for R32 the other team in the matchup, for later rounds the feeder-winner
    that didn't advance.
    """
    tree = bracket_tree()
    elim: set[str] = set()
    for match_id, winner in results.items():
        for team in participants(match_id, matchups, tree, results):
            if team and team != winner:
                elim.add(team)
    return elim


def compute_standing(cfg: dict, results_doc: dict) -> dict:
    """Compute the full standing snapshot from config + results.

    Returns keys the renderer/history already understand: points, ceiling,
    played, won, lost, champion, champion_alive, matches_decided, matches_total,
    plus a per-round breakdown and the source tag.
    """
    picks: dict = cfg["picks"]
    matchups: dict = cfg["matchups"]
    scoring: dict = cfg["scoring"]
    codes: dict = cfg.get("codes", {})
    champion_pick: str = cfg["champion_pick"]

    results: dict = results_doc.get("results", {})
    matches_total: int = results_doc.get("matches_total", 32)

    eliminated = eliminated_teams(matchups, results)

    earned = 0
    played = won = lost = 0
    ceiling = 0
    by_round = {r: {"won": 0, "played": 0, "pts": 0} for r in ROUND_ORDER}
    pick_status: dict[str, str] = {}

    for match_id, my_team in picks.items():
        rnd = round_of(match_id)
        pts = scoring.get(rnd, 0)

        if match_id in results:  # this match has a real outcome
            played += 1
            by_round[rnd]["played"] += 1
            if my_team == results[match_id]:
                earned += pts
                ceiling += pts
                won += 1
                by_round[rnd]["won"] += 1
                by_round[rnd]["pts"] += pts
                pick_status[match_id] = "won"
            else:
                lost += 1
                pick_status[match_id] = "lost"
        else:  # undecided — still reachable iff my picked team is alive
            if my_team not in eliminated:
                ceiling += pts
                pick_status[match_id] = "open"
            else:
                pick_status[match_id] = "dead"

    champion_alive = champion_pick not in eliminated

    return {
        "points": earned,
        "ceiling": ceiling,
        "played": played,
        "won": won,
        "lost": lost,
        "champion": codes.get(champion_pick, champion_pick),
        "champion_pick": champion_pick,
        "champion_alive": champion_alive,
        "matches_decided": len(results),
        "matches_total": matches_total,
        "by_round": by_round,
        "pick_status": pick_status,
        "eliminated": sorted(eliminated),
        "source": "local",
    }

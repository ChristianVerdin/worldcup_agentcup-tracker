"""Regression tests for the independent scoring engine.

Runnable two ways with no extra dependencies:
    python tests/test_scoring.py     # plain asserts, prints a summary
    pytest tests/test_scoring.py     # if pytest is installed

The headline assertion mirrors the ground truth after 21 of 32 knockout matches
were entered (all 16 R32 + 5 R16). Spain beat Portugal in R16-3, eliminating the
champion pick: 17 pts, ceiling 36, 21-15-6, champion out.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import scoring  # noqa: E402


def _load():
    with open(os.path.join(ROOT, "bracket.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    with open(os.path.join(ROOT, "data", "results.json"), encoding="utf-8") as fh:
        results_doc = json.load(fh)
    return cfg, results_doc


def test_standing_matches_ground_truth():
    cfg, results_doc = _load()
    s = scoring.compute_standing(cfg, results_doc)

    assert s["points"] == 17, s["points"]
    assert s["ceiling"] == 36, s["ceiling"]
    assert s["played"] == 21, s["played"]
    assert s["won"] == 15, s["won"]
    assert s["lost"] == 6, s["lost"]
    assert s["champion_pick"] == "POR"
    assert s["champion_alive"] is False  # Portugal knocked out by Spain in R16-3
    assert s["matches_decided"] == 21  # 16 R32 + 5 R16 with recorded winners


def test_round_of():
    assert scoring.round_of("R32-1") == "R32"
    assert scoring.round_of("R16-8") == "R16"
    assert scoring.round_of("F") == "F"
    assert scoring.round_of("3P") == "3P"


def test_r32_misses_and_dead_branches():
    """The three R32 misses are RSA/AUS/ALG; dead downstream branches are BRA, MEX & POR."""
    cfg, results_doc = _load()
    s = scoring.compute_standing(cfg, results_doc)

    r32_losses = [
        mid for mid, st in s["pick_status"].items()
        if scoring.round_of(mid) == "R32" and st == "lost"
    ]
    assert sorted(cfg["picks"][m] for m in r32_losses) == ["ALG", "AUS", "RSA"]

    # Brazil, Mexico and now Portugal were advanced deep but knocked out.
    for dead in ("BRA", "MEX", "POR"):
        assert dead in s["eliminated"]
    # QF-3 (Mexico) was already dead; Portugal's exit kills QF-2, SF-1 and the Final.
    for dead_branch in ("QF-3", "QF-2", "SF-1", "F"):
        assert s["pick_status"][dead_branch] == "dead", dead_branch


def test_by_round_breakdown():
    cfg, results_doc = _load()
    s = scoring.compute_standing(cfg, results_doc)
    br = s["by_round"]
    assert br["R32"] == {"won": 13, "played": 16, "pts": 13}, br["R32"]
    assert br["R16"] == {"won": 2, "played": 5, "pts": 4}, br["R16"]
    assert br["QF"]["played"] == 0


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    cfg, results_doc = _load()
    s = scoring.compute_standing(cfg, results_doc)
    print(
        f"\nComputed: {s['points']} pts · ceiling {s['ceiling']} · "
        f"{s['played']}-{s['won']}-{s['lost']} (P-W-L) · "
        f"champion {s['champion']} {'alive' if s['champion_alive'] else 'out'} · "
        f"{s['matches_decided']}/{s['matches_total']} decided"
    )
    print(f"\n{len(tests)} tests passed.")


if __name__ == "__main__":
    _run_all()

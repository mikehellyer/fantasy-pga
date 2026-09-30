"""Fantasy points, as in PGA TOUR Fantasy Golf: points for every hole, round
bonuses, and a FedExCup finishing bonus added to the final round.

All the point values are in data.py so they're easy to change.
"""

from __future__ import annotations

import math

from . import data
from .sim import Tournament, finish_number


def hole_points(score: int, par: int) -> int:
    pts = data.HOLE_POINTS.get(score, data.DOUBLE_OR_WORSE)
    if score == -2 and par == 3:
        pts += data.HOLE_IN_ONE_BONUS
    return pts


def round_breakdown(card: list[int], pars: list[int]) -> dict:
    """Points for one round's scorecard, split into holes and bonuses."""
    holes = sum(hole_points(s, p) for s, p in zip(card, pars))
    run = best = 0
    for s in card:
        run = run + 1 if s < 0 else 0
        best = max(best, run)
    streak = data.BIRDIE_STREAK if best >= 3 else 0
    bogey_free = data.BOGEY_FREE if len(card) == 18 and all(s <= 0 for s in card) else 0
    return {"holes": holes, "streak": streak, "bogey_free": bogey_free}


def fedex_points(kind: str, position: str, winner_points: int | None = None) -> int:
    """FedExCup points for a finishing position ('1', 'T5', 'MC'). Tied golfers share."""
    top = winner_points or data.FEDEX_WINNER[kind]
    n = finish_number(position)
    if n >= 999:
        return 0
    return round(top * _share(n))


def _share(n: int) -> float:
    if n <= 10:
        return data.FEDEX_TOP10[n - 1]
    return max(0.004, 0.15 * math.exp(-(n - 10) / 16))


def shared_fedex(kind: str, finish: dict[int, str], winner_points: int | None = None) -> dict[int, int]:
    """FedExCup points for everyone, with tied golfers splitting the points for the places they fill."""
    top = winner_points or data.FEDEX_WINNER[kind]
    by_pos: dict[str, list[int]] = {}
    for g, p in finish.items():
        by_pos.setdefault(p, []).append(g)
    out = {}
    for p, golfers in by_pos.items():
        n = finish_number(p)
        if n >= 999:
            for g in golfers:
                out[g] = 0
            continue
        places = range(n, n + len(golfers))
        pts = round(top * sum(_share(k) for k in places) / len(golfers))
        for g in golfers:
            out[g] = pts
    return out


def finishing_bonuses(t: Tournament) -> dict[int, int]:
    """The fantasy finishing bonus for everyone in a finished event: FedExCup points / 10
    (the playoffs on the signature-event scale)."""
    if not t.complete:
        return {}
    pts = shared_fedex(t.event.kind, t.finish, data.BONUS_SCALE[t.event.kind])
    return {g: round(p / 10) for g, p in pts.items()}


def golfer_round_points(
    t: Tournament, g: int, r: int, pars: list[int], bonuses: dict[int, int] | None = None
) -> dict:
    """Everything golfer g scored in round r (0-3), before any captain doubling.

    `bonuses` is finishing_bonuses(t), passed in so it's only worked out once per event."""
    if r >= len(t.scores.get(g, [])):
        return {"holes": 0, "streak": 0, "bogey_free": 0, "finish": 0, "under70": 0, "total": 0}
    b = round_breakdown(t.scores[g][r], pars)
    b["finish"] = b["under70"] = 0
    if r == 3 and t.complete:
        if bonuses is None:
            bonuses = finishing_bonuses(t)
        b["finish"] = bonuses.get(g, 0)
        if all(t.round_strokes(g, k) < 70 for k in range(4)):
            b["under70"] = data.ALL_ROUNDS_UNDER_70
    b["total"] = b["holes"] + b["streak"] + b["bogey_free"] + b["finish"] + b["under70"]
    return b


def golfer_event_points(t: Tournament, g: int, pars: list[int], bonuses: dict[int, int] | None = None) -> int:
    return sum(golfer_round_points(t, g, r, pars, bonuses)["total"] for r in range(t.round_no))

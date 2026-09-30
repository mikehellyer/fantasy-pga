"""The golf engine: plays every golfer's round hole by hole.

Each hole's score is drawn from a realistic spread of eagles, birdies, pars and
bogeys for its par. That spread is tilted towards better or worse scores so the
average matches how well the golfer should play the hole today: his skill, his
form, a bit of luck on the day, how hard the course is and how hard the wind blows.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_left

from .data import SCHEDULE, Event
from .models import Golfer

SCORES = (-3, -2, -1, 0, 1, 2, 3)  # albatross ... triple bogey
# How often tour players make each score on an average hole of each par
BASE = {
    3: (0.0, 0.0004, 0.13, 0.68, 0.16, 0.026, 0.004),
    4: (0.00004, 0.004, 0.17, 0.63, 0.165, 0.027, 0.004),
    5: (0.0015, 0.06, 0.43, 0.42, 0.075, 0.011, 0.0025),
}
DAY_SPREAD = 0.9  # how much a golfer's day varies (strokes a round, one standard deviation)
WIND_STROKES = 0.9  # extra strokes a round for the field per level of wind above the course's usual
CALIBRATION = 2.0  # makes the winning scores come out like the real tour's


def _tilt_table(par: int):
    """Score spreads for a range of tilts, sorted by their average score."""
    base = BASE[par]
    means, cdfs = [], []
    for k in range(-500, 501):
        lam = k / 100
        w = [b * math.exp(-lam * s) for b, s in zip(base, SCORES)]
        total = sum(w)
        p = [x / total for x in w]
        means.append(sum(pi * s for pi, s in zip(p, SCORES)))
        acc, cdf = 0.0, []
        for pi in p:
            acc += pi
            cdf.append(acc)
        cdfs.append(cdf)
    means.reverse()
    cdfs.reverse()
    return means, cdfs


_TABLES = {par: _tilt_table(par) for par in BASE}
BASE_MEAN = {par: sum(b * s for b, s in zip(BASE[par], SCORES)) / sum(BASE[par]) for par in BASE}


def hole_score(par: int, target: float, rng: random.Random) -> int:
    """A score (relative to par) for one hole, averaging `target` over many plays."""
    means, cdfs = _TABLES[par]
    i = min(len(means) - 1, bisect_left(means, target))
    r = rng.random()
    for s, c in zip(SCORES, cdfs[i]):
        if r < c:
            return s
    return SCORES[-1]


def course_holes(event: Event) -> list[tuple[int, float]]:
    """(par, extra difficulty) for each of the 18 holes. Always the same for a course."""
    rng = random.Random(event.course)
    par5 = {72: 4, 71: 3, 70: 2}.get(event.par, 4)
    pars = [3] * 4 + [5] * par5 + [4] * (18 - 4 - par5)
    rng.shuffle(pars)
    # tidy up: no par 5s on 1 and 18 at most courses isn't a rule, but avoid par 3 on 1
    if pars[0] == 3:
        j = next(i for i, p in enumerate(pars) if p != 3)
        pars[0], pars[j] = pars[j], pars[0]
    extra = [rng.gauss(0, 0.12) for _ in pars]
    mean = sum(extra) / 18
    return [(p, round(e - mean, 3)) for p, e in zip(pars, extra)]


def hole_par(event: Event, hole: int) -> int:
    return course_holes(event)[hole][0]


class Tournament:
    """One week's event: the field, every hole played so far, the cut and the result."""

    def __init__(self, event_index: int, field: list[int], seed: int):
        self.event_index = event_index
        self.field = list(field)
        self.seed = seed
        self.scores: dict[int, list[list[int]]] = {g: [] for g in field}  # rounds of hole scores
        self.wind: list[int] = []
        self.tee: list[dict[int, float]] = []  # per round: golfer -> start time (0..1 of the day)
        self.round_no = 0  # rounds completed
        self.cut_made: list[int] | None = None  # golfers through to the weekend
        self.cut_score: int | None = None
        self.withdrawn: list[int] = []
        self.finish: dict[int, str] = {}  # golfer -> "1", "T5", "MC" once complete
        self.playoff: list[str] = []  # how a playoff went, if there was one
        self.winner: int | None = None

    @property
    def event(self) -> Event:
        return SCHEDULE[self.event_index]

    @property
    def complete(self) -> bool:
        return self.round_no >= 4

    def active(self) -> list[int]:
        """Golfers still playing (after the cut, only those who made it)."""
        players = self.cut_made if self.cut_made is not None else self.field
        return [g for g in players if g not in self.withdrawn]

    def total(self, g: int, rounds: int | None = None) -> int:
        rs = self.scores[g] if rounds is None else self.scores[g][:rounds]
        return sum(sum(r) for r in rs)

    def round_strokes(self, g: int, r: int) -> int:
        return sum(self.scores[g][r]) + self.event.par

    # -------------------------------------------------------------- playing
    def play_round(self, golfers: list[Golfer]) -> None:
        """Play the next round for everyone still in the event."""
        r = self.round_no
        ev = self.event
        rng = random.Random(self.seed * 10 + r)
        wind = max(0, min(3, ev.wind + rng.choice((-1, -1, 0, 0, 0, 1))))
        if ev.wind == 0:
            wind = rng.choice((0, 0, 0, 1))
        self.wind.append(wind)
        holes = course_holes(ev)
        players = self.active()
        self.tee.append(self._tee_times(players, rng))
        day = (ev.difficulty + (wind - ev.wind) * WIND_STROKES + CALIBRATION) / 18
        for g in players:
            golfer = golfers[g]
            q = golfer.skill + golfer.form_bonus + rng.gauss(0, DAY_SPREAD)
            # afternoon starters get a little more wind on a windy day
            q -= wind * 0.25 * self.tee[r][g]
            per_hole = q / 18
            card = [hole_score(par, BASE_MEAN[par] + extra + day - per_hole, rng) for par, extra in holes]
            self.scores[g].append(card)
        self.round_no += 1
        if self.round_no == 2 and ev.cut:
            self._make_cut()
        if self.round_no == 4:
            self._finish(golfers, rng)

    def _tee_times(self, players: list[int], rng: random.Random) -> dict[int, float]:
        """When each golfer starts (0 = first out, ~0.45 = last group). Leaders go out late."""
        if self.round_no < 2:
            order = list(players)
            rng.shuffle(order)
            size = 3
        else:
            order = sorted(players, key=lambda g: (-self.total(g), rng.random()))
            size = 2
        groups = max(1, math.ceil(len(order) / size))
        return {g: round(0.45 * (i // size) / max(1, groups - 1), 4) for i, g in enumerate(order)}

    def _make_cut(self):
        ranked = sorted(self.active(), key=self.total)
        n = self.event.cut
        if len(ranked) <= n:
            self.cut_made = ranked
            return
        line = self.total(ranked[n - 1])
        self.cut_score = line
        self.cut_made = [g for g in ranked if self.total(g) <= line]

    def _finish(self, golfers: list[Golfer], rng: random.Random):
        players = self.active()
        best = min(self.total(g) for g in players)
        leaders = [g for g in players if self.total(g) == best]
        if len(leaders) > 1:
            self.winner = self._playoff(leaders, golfers, rng)
        else:
            self.winner = leaders[0]
        for g, pos in self.positions(players).items():
            self.finish[g] = pos
        self.finish[self.winner] = "1"
        for g in leaders:
            if g != self.winner:
                self.finish[g] = "T2" if len(leaders) > 2 else "2"
        for g in self.field:
            if g not in self.finish:
                self.finish[g] = "WD" if g in self.withdrawn else "MC"

    def _playoff(self, leaders: list[int], golfers: list[Golfer], rng: random.Random) -> int:
        ev = self.event
        par = course_holes(ev)[17][0]
        alive = list(leaders)
        hole = 0
        self.playoff.append(" v ".join(golfers[g].surname for g in alive) + " go to a playoff on the 18th")
        while len(alive) > 1 and hole < 20:
            hole += 1
            day = (ev.difficulty + (self.wind[-1] - ev.wind) * WIND_STROKES + CALIBRATION) / 18
            res = {g: hole_score(par, BASE_MEAN[par] + day - golfers[g].skill / 18, rng) for g in alive}
            low = min(res.values())
            names = ", ".join(f"{golfers[g].surname} {_score_word(res[g])}" for g in alive)
            self.playoff.append(f"Extra hole {hole}: {names}")
            alive = [g for g in alive if res[g] == low]
        return alive[0] if len(alive) == 1 else rng.choice(alive)

    # -------------------------------------------------------------- tables
    def positions(self, players: list[int], rounds: int | None = None) -> dict[int, str]:
        """Leaderboard positions like '1', 'T4' for these golfers on total score."""
        totals = {g: self.total(g, rounds) for g in players}
        ordered = sorted(totals.values())
        out = {}
        for g, t in totals.items():
            pos = bisect_left(ordered, t) + 1
            tied = ordered.count(t) > 1
            out[g] = f"T{pos}" if tied else str(pos)
        return out

    def leaderboard(self, rounds: int | None = None) -> list[tuple[int, str, int]]:
        """[(golfer, position, total to par)] best first; missed cuts at the bottom."""
        rounds = self.round_no if rounds is None else rounds
        players = self.active() if rounds > 2 or self.cut_made is None else self.field
        if rounds <= 2:
            players = [g for g in self.field if g not in self.withdrawn]
        if self.complete and rounds == 4:
            order = sorted(players, key=lambda g: (finish_number(self.finish[g]), self.total(g)))
            return [(g, self.finish[g], self.total(g)) for g in order]
        pos = self.positions(players, rounds)
        order = sorted(players, key=lambda g: self.total(g, rounds))
        return [(g, pos[g], self.total(g, rounds)) for g in order]

    # -------------------------------------------------------------- saving
    def to_dict(self) -> dict:
        return {
            "event_index": self.event_index,
            "field": self.field,
            "seed": self.seed,
            "scores": {str(g): r for g, r in self.scores.items()},
            "wind": self.wind,
            "tee": [{str(g): t for g, t in d.items()} for d in self.tee],
            "round_no": self.round_no,
            "cut_made": self.cut_made,
            "cut_score": self.cut_score,
            "withdrawn": self.withdrawn,
            "finish": {str(g): p for g, p in self.finish.items()},
            "playoff": self.playoff,
            "winner": self.winner,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Tournament:
        t = cls(d["event_index"], d["field"], d["seed"])
        t.scores = {int(g): r for g, r in d["scores"].items()}
        t.wind = d["wind"]
        t.tee = [{int(g): v for g, v in x.items()} for x in d["tee"]]
        t.round_no = d["round_no"]
        t.cut_made = d["cut_made"]
        t.cut_score = d["cut_score"]
        t.withdrawn = d.get("withdrawn", [])
        t.finish = {int(g): p for g, p in d["finish"].items()}
        t.playoff = d.get("playoff", [])
        t.winner = d.get("winner")
        return t


def finish_number(pos: str) -> int:
    """'T4' -> 4. Missed cuts and withdrawals sort last."""
    digits = pos.lstrip("T")
    return int(digits) if digits.isdigit() else 999


def _score_word(s: int) -> str:
    return {-3: "albatross", -2: "eagle", -1: "birdie", 0: "par", 1: "bogey", 2: "double"}.get(s, "triple+")


def score_word(s: int, par: int = 4) -> str:
    if s == -2 and par == 3:
        return "HOLE-IN-ONE"
    return _score_word(s).upper()


def to_par(n: int) -> str:
    return "E" if n == 0 else f"{n:+d}"

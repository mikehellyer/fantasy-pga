"""Fantasy teams: picking six golfers, starting four with a captain, the
three-starts-per-segment limit, auto-swaps, and how the rival managers pick.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import data
from .models import Golfer
from .sim import Tournament, finish_number


@dataclass
class Team:
    name: str
    manager: str
    human: bool = False
    style: str = "balanced"  # rivals: chalk / balanced / longshot / saver
    points: int = 0  # this season
    segment_points: list[int] = field(default_factory=lambda: [0, 0, 0])
    event_points: dict[int, int] = field(default_factory=dict)  # event index -> points
    usage: dict[int, dict[int, int]] = field(default_factory=lambda: {0: {}, 1: {}, 2: {}})
    # this week's team
    picks: list[int] = field(default_factory=list)
    starters: list[int] = field(default_factory=list)
    captain: int | None = None
    counted: list[int] = field(default_factory=list)  # golfers whose start is used up this event
    rounds: list[dict] = field(default_factory=list)  # locked lineups and points, round by round
    notes: list[str] = field(default_factory=list)  # what happened to the lineup (auto-swaps)

    # -------------------------------------------------------------- usage
    def starts_used(self, g: int, segment: int) -> int:
        return self.usage[segment].get(g, 0)

    def starts_left(self, g: int, segment: int) -> int:
        return data.STARTS_PER_SEGMENT - self.starts_used(g, segment)

    def can_start(self, g: int, segment: int) -> bool:
        return g in self.counted or self.starts_left(g, segment) > 0

    @property
    def bench(self) -> list[int]:
        return [g for g in self.picks if g not in self.starters]

    def lineup_ready(self) -> bool:
        return (
            len(self.picks) == data.ROSTER_SIZE
            and len(self.starters) == data.STARTERS
            and self.captain in self.starters
        )

    @property
    def event_total(self) -> int:
        return sum(r["total"] for r in self.rounds)

    # -------------------------------------------------------------- changes
    def clear_week(self):
        self.picks, self.starters, self.captain = [], [], None
        self.counted, self.rounds, self.notes = [], [], []

    def lock_round(self, segment: int, t: Tournament):
        """The round is about to start: fill empty starter spots from the bench and use up starts."""
        active = set(t.active())
        for g in self.bench:
            if len(self.starters) >= data.STARTERS:
                break
            if g in active and self.can_start(g, segment):
                self.starters.append(g)
        if self.captain not in self.starters and self.starters:
            self.captain = self.starters[0]
        for g in self.starters:
            if g not in self.counted:
                self.counted.append(g)
                self.usage[segment][g] = self.starts_used(g, segment) + 1
        self.rounds.append(
            {"starters": list(self.starters), "captain": self.captain, "points": {}, "total": 0}
        )

    def auto_swap(self, segment: int, t: Tournament, golfers: list[Golfer]):
        """After the cut: bench golfers still in the event replace starters who aren't."""
        active = set(t.active())
        for g in list(self.starters):
            if g in active:
                continue
            sub = next(
                (b for b in self.bench if b in active and self.can_start(b, segment)),
                None,
            )
            i = self.starters.index(g)
            if sub is None:
                continue
            self.starters[i] = sub
            note = f"Auto-swap: {golfers[sub].surname} in for {golfers[g].surname}"
            if self.captain == g:
                self.captain = sub
                note += " (and takes the captaincy)"
            self.notes.append(note)

    def score_round(self, t: Tournament, r: int, pars: list[int], round_points) -> int:
        """Add up the locked starters' points for round r. round_points(g, r) -> dict."""
        lock = self.rounds[r]
        total = 0
        for g in lock["starters"]:
            pts = round_points(g, r)["total"]
            if g == lock["captain"]:
                pts *= data.CAPTAIN_MULTIPLIER
            lock["points"][g] = pts
            total += pts
        lock["total"] = total
        return total

    # -------------------------------------------------------------- saving
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "manager": self.manager,
            "human": self.human,
            "style": self.style,
            "points": self.points,
            "segment_points": self.segment_points,
            "event_points": {str(k): v for k, v in self.event_points.items()},
            "usage": {str(s): {str(g): n for g, n in u.items()} for s, u in self.usage.items()},
            "picks": self.picks,
            "starters": self.starters,
            "captain": self.captain,
            "counted": self.counted,
            "rounds": [{**r, "points": {str(g): p for g, p in r["points"].items()}} for r in self.rounds],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Team:
        t = cls(d["name"], d["manager"], d["human"], d["style"])
        t.points = d["points"]
        t.segment_points = d["segment_points"]
        t.event_points = {int(k): v for k, v in d["event_points"].items()}
        t.usage = {int(s): {int(g): n for g, n in u.items()} for s, u in d["usage"].items()}
        t.picks, t.starters, t.captain = d["picks"], d["starters"], d["captain"]
        t.counted = d["counted"]
        t.rounds = [{**r, "points": {int(g): p for g, p in r["points"].items()}} for r in d["rounds"]]
        t.notes = d.get("notes", [])
        return t


# ------------------------------------------------------------------ rival managers
STYLE_NOISE = {"chalk": 0.25, "balanced": 0.5, "saver": 0.45, "longshot": 0.8}


def expected_value(golfer: Golfer) -> float:
    """How good a pick a golfer looks this week (strokes a round, roughly)."""
    return golfer.skill + golfer.form_bonus


def ai_pick(team: Team, t: Tournament, golfers: list[Golfer], rng: random.Random, big_left: int):
    """Choose six golfers, four starters and a captain for a rival manager.

    big_left: how many signature events and majors are still to come in this segment,
    after this one - "savers" keep their stars for those.
    """
    ev = t.event
    seg = ev.segment
    big = ev.kind in ("signature", "players", "major", "playoff")
    noise = STYLE_NOISE.get(team.style, 0.5)
    scored = []
    for g in t.field:
        left = team.starts_left(g, seg)
        if left <= 0:
            continue
        golfer = golfers[g]
        v = expected_value(golfer) + rng.gauss(0, noise)
        if team.style == "longshot" and golfer.owgr > 30:
            v += 0.35
        if not big and big_left >= left and golfer.skill > 1.6:
            v -= 0.6 if team.style == "saver" else 0.25  # keep him for the big ones
        scored.append((v, g))
    scored.sort(reverse=True)
    team.clear_week()
    team.picks = [g for _, g in scored[: data.ROSTER_SIZE]]
    team.starters = team.picks[: data.STARTERS]
    team.captain = team.starters[0] if team.starters else None


def ai_between_rounds(team: Team, t: Tournament, golfers: list[Golfer]):
    """Before rounds 3 and 4: start the four best-placed golfers and captain the leader."""
    seg = t.event.segment
    board = {g: finish_number(p) for g, p, _ in t.leaderboard()}
    active = set(t.active())
    ranked = sorted(
        (g for g in team.picks if g in active and team.can_start(g, seg)), key=lambda g: board.get(g, 999)
    )
    if len(ranked) >= 1:
        # keep the starts of golfers not yet used where the gain is small: only swap in a
        # bench golfer who is clearly ahead
        new = list(team.starters)
        for b in [g for g in ranked if g not in new]:
            worst = max((s for s in new), key=lambda s: board.get(s, 999) if s in active else 9999)
            if worst not in active or board.get(b, 999) + 10 < board.get(worst, 999):
                new[new.index(worst)] = b
        team.starters = new
        live = [g for g in team.starters if g in active]
        if live:
            team.captain = min(live, key=lambda g: board.get(g, 999))

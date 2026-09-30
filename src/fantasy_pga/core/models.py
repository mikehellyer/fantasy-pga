"""The golfers: who they are, how good they are, and how they're playing."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

FORM_EVENTS = 5  # form is how a golfer has played against his skill in his last few events


def skill_from_rank(rank: int) -> float:
    """Strokes gained per round against an average tour player, from a world ranking.

    World No. 1 is about +3.0 a round, No. 10 +1.85, No. 50 +1.05, No. 200 +0.35.
    """
    return round(3.0 - 0.5 * math.log(max(1, rank)), 2)


def empty_stats() -> dict:
    return {
        "events": 0,
        "cuts": 0,
        "wins": 0,
        "top10": 0,
        "rounds": 0,
        "strokes": 0,  # total strokes, for the scoring average
        "eagles": 0,
        "birdies": 0,
        "aces": 0,
        "fantasy": 0,  # fantasy points earned (uncaptained, as a starter every round)
        "fedex": 0,
        "best": 0,  # best finish (0 = none yet)
    }


@dataclass
class Golfer:
    id: int
    name: str
    country: str
    owgr: int
    tour: str  # PGA / EUR / LIV / ASIA
    skill: float
    form: list[float] = field(default_factory=list)  # strokes a round above/below his skill
    stats: dict = field(default_factory=empty_stats)
    results: list = field(default_factory=list)  # [event index, position text] this season

    @property
    def surname(self) -> str:
        parts = self.name.split()
        if len(parts) > 1 and parts[-1] in ("III", "Jr.", "Jr"):
            return parts[-2]
        return parts[-1]

    @property
    def short(self) -> str:
        """'S. Scheffler' style name for leaderboards."""
        first = self.name.split()[0]
        return f"{first[0]}. {self.name[len(first) + 1 :]}" if " " in self.name else self.name

    @property
    def rating(self) -> int:
        """A 1-99 rating for the screens (the C64 way)."""
        return max(1, min(99, round(50 + 15 * self.skill)))

    @property
    def form_value(self) -> float:
        """Recent form in strokes a round: + is playing above his skill."""
        if not self.form:
            return 0.0
        return sum(self.form) / len(self.form)

    @property
    def form_bonus(self) -> float:
        """How much form changes his play this week (strokes a round, capped)."""
        return max(-0.5, min(0.5, 0.4 * self.form_value))

    @property
    def form_label(self) -> str:
        v = self.form_value
        if not self.form:
            return "OK"
        if v >= 1.2:
            return "HOT"
        if v >= 0.4:
            return "Good"
        if v <= -1.2:
            return "Cold"
        if v <= -0.4:
            return "Poor"
        return "OK"

    def add_form(self, value: float):
        self.form = (self.form + [round(value, 2)])[-FORM_EVENTS:]

    def scoring_average(self, par: int = 0) -> float:
        r = self.stats["rounds"]
        return self.stats["strokes"] / r if r else 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "owgr": self.owgr,
            "tour": self.tour,
            "skill": self.skill,
            "form": self.form,
            "stats": self.stats,
            "results": self.results,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Golfer:
        g = cls(d["id"], d["name"], d["country"], d["owgr"], d["tour"], d["skill"])
        g.form = list(d.get("form", []))
        g.stats = {**empty_stats(), **d.get("stats", {})}
        g.results = [list(r) for r in d.get("results", [])]
        return g

"""The whole game: a season of tournaments, your fantasy team and the rival
managers in your league, the FedExCup race, and saving and loading.
"""

from __future__ import annotations

import json
import math
import random
import zlib
from pathlib import Path

from . import data
from .database import load_golfers
from .fantasy import Team, ai_between_rounds, ai_pick
from .models import Golfer, empty_stats
from .scoring import (
    finishing_bonuses,
    golfer_round_points,
    round_breakdown,
    shared_fedex,
)
from .sim import Tournament, course_holes, finish_number, to_par

FIRST_SEASON = 2026
WITHDRAW_CHANCE = 0.003  # per golfer per round


class LineupError(Exception):
    pass


class Game:
    def __init__(self):
        self.manager = ""
        self.seed = 0
        self.season = FIRST_SEASON
        self.golfers: list[Golfer] = []
        self.teams: list[Team] = []
        self.event_index = 0
        self.tournament: Tournament | None = None
        self.fedex: dict[int, int] = {}
        self.results: list[dict] = []  # one summary per finished event this season
        self.news: list[str] = []
        self.history: list[dict] = []  # one per finished season
        self.records: dict = {}
        self.season_over = False
        self._bonus_cache: tuple[int, dict] | None = None

    # ================================================================ setup
    @classmethod
    def new(cls, manager: str, team_name: str, seed: int | None = None, golfers=None) -> Game:
        g = cls()
        g.manager = manager or "Manager"
        g.seed = seed if seed is not None else random.randrange(1_000_000)
        g.golfers = golfers if golfers is not None else load_golfers()
        g.teams = [Team(team_name or "My Team", g.manager, human=True)]
        g.teams += [Team(n, m, False, s) for n, m, s in data.RIVALS]
        g.news = [f"Welcome, {g.manager}! Pick six golfers for the {data.SCHEDULE[0].name}."]
        g.start_event()
        return g

    @property
    def me(self) -> Team:
        return self.teams[0]

    @property
    def event(self) -> data.Event:
        return data.SCHEDULE[self.event_index]

    @property
    def segment(self) -> int:
        return self.event.segment

    @property
    def t(self) -> Tournament:
        return self.tournament

    @property
    def pars(self) -> list[int]:
        return [p for p, _ in course_holes(self.event)]

    def rng(self, *salt) -> random.Random:
        # str hashes change every run, so use crc32 to keep a saved game's future the same
        return random.Random(zlib.crc32(repr((self.seed, self.season, self.event_index) + salt).encode()))

    # ================================================================ fields
    def priority(self, g: Golfer) -> float:
        """Who gets into the elevated events: this season's FedExCup points, plus a head
        start from the world ranking that matters most early in the season."""
        return self.fedex.get(g.id, 0) + max(0, 1500 - 12 * g.owgr)

    def make_field(self, ev: data.Event, rng: random.Random) -> list[int]:
        gs = self.golfers
        members = [g for g in gs if g.tour == "PGA"]
        if ev.kind == "playoff":
            ranked = sorted(members, key=lambda g: (-self.fedex.get(g.id, 0), g.owgr))
            return [g.id for g in ranked[: ev.field_size]]
        if ev.kind == "signature":
            ranked = sorted(members, key=lambda g: -self.priority(g))
            field = ranked[:50]
            rest = ranked[50:90]
            rng.shuffle(rest)
            field += rest[: ev.field_size - 50]
            return sorted(g.id for g in field)
        if ev.kind == "players":
            return sorted(g.id for g in members[: ev.field_size])
        if ev.kind == "major":
            if ev.short == "THE MASTERS":
                field = sorted(gs, key=lambda g: g.owgr)[: ev.field_size]
            else:
                field = [g for g in gs if g.owgr <= 120 or g.tour == "PGA" or rng.random() < 0.5]
            return sorted(g.id for g in field[: ev.field_size])
        # regular events: most tour members play, the stars pick and choose
        field = []
        for g in gs:
            if g.tour == "PGA":
                p = 0.45 if g.owgr <= 10 else 0.6 if g.owgr <= 30 else 0.82
            elif g.tour == "EUR":
                p = 0.9 if ev.short == "SCOTTISH OPEN" else 0.06
            elif g.tour == "ASIA":
                p = 0.04
            else:
                p = 0.0  # LIV golfers only play the majors
            if rng.random() < p:
                field.append(g.id)
        return sorted(field[: ev.field_size])

    def start_event(self):
        ev = self.event
        rng = self.rng("field")
        field = self.make_field(ev, rng)
        self.tournament = Tournament(self.event_index, field, rng.randrange(1_000_000_000))
        self._bonus_cache = None
        seg = ev.segment
        big_left = sum(
            1
            for i in data.segment_events(seg)
            if i > self.event_index and data.SCHEDULE[i].kind in ("signature", "players", "major", "playoff")
        )
        pick_rng = self.rng("ai")
        for team in self.teams:
            if team.human:
                team.clear_week()
            else:
                ai_pick(team, self.tournament, self.golfers, pick_rng, big_left)

    # ================================================================ your lineup
    def can_pick(self, g: int) -> tuple[bool, str]:
        me = self.me
        if g not in self.t.field:
            return False, "not playing this week"
        if g in me.picks:
            return True, ""
        if self.t.round_no > 0:
            return False, "the six are fixed once the event starts"
        if len(me.picks) >= data.ROSTER_SIZE:
            return False, f"you already have {data.ROSTER_SIZE} golfers"
        if me.starts_left(g, self.segment) <= 0:
            return False, f"no starts left for him in {data.SEGMENT_NAMES[self.segment]}"
        return True, ""

    def toggle_pick(self, g: int) -> str:
        """Add or drop a golfer from your six. Returns a message if it can't be done."""
        me = self.me
        if self.t.round_no > 0:
            return "Your six are fixed once the tournament starts."
        if g in me.picks:
            me.picks.remove(g)
            if g in me.starters:
                me.starters.remove(g)
            if me.captain == g:
                me.captain = me.starters[0] if me.starters else None
            return ""
        ok, why = self.can_pick(g)
        if not ok:
            return f"Can't pick {self.golfers[g].name}: {why}."
        me.picks.append(g)
        if len(me.starters) < data.STARTERS:
            me.starters.append(g)
        if me.captain is None and me.starters:
            me.captain = me.starters[0]
        return ""

    def toggle_starter(self, g: int) -> str:
        """Move a golfer between the starters and the bench."""
        me = self.me
        if g not in me.picks:
            return ""
        if g in me.starters:
            me.starters.remove(g)
            if me.captain == g:
                me.captain = me.starters[0] if me.starters else None
            return ""
        if self.t.round_no > 0 and g not in self.t.active():
            return f"{self.golfers[g].name} is out of the tournament."
        if not me.can_start(g, self.segment):
            return f"{self.golfers[g].name} has no starts left this segment."
        if len(me.starters) >= data.STARTERS:
            # swap him for the last non-captain starter
            out = next((s for s in reversed(me.starters) if s != me.captain), me.starters[-1])
            me.starters[me.starters.index(out)] = g
            if me.captain == out:
                me.captain = g
            return ""
        me.starters.append(g)
        return ""

    def set_captain(self, g: int) -> str:
        me = self.me
        if g not in me.picks:
            return ""
        if g not in me.starters:
            msg = self.toggle_starter(g)
            if msg:
                return msg
        me.captain = g
        return ""

    def auto_pick(self):
        """Fill the rest of your six with the best available golfers (keeps anyone you've picked)."""
        me = self.me
        if self.t.round_no > 0:
            return
        ranked = sorted(self.t.field, key=lambda g: -(self.golfers[g].skill + self.golfers[g].form_bonus))
        for g in ranked:
            if len(me.picks) >= data.ROSTER_SIZE:
                break
            if g not in me.picks and me.starts_left(g, self.segment) > 0:
                self.toggle_pick(g)
        me.starters = sorted(me.picks, key=lambda g: -self.golfers[g].skill)[: data.STARTERS]
        me.captain = me.starters[0] if me.starters else None

    def lineup_problem(self) -> str:
        me = self.me
        if len(me.picks) < data.ROSTER_SIZE:
            return f"Pick {data.ROSTER_SIZE - len(me.picks)} more golfer(s) - you need {data.ROSTER_SIZE}."
        if len(me.starters) < data.STARTERS:
            active = set(self.t.active())
            if sum(1 for g in me.picks if g in active and me.can_start(g, self.segment)) >= data.STARTERS:
                return f"Choose {data.STARTERS} starters."
        if me.captain not in me.starters:
            return "Choose a captain from your starters."
        return ""

    # ================================================================ playing
    def round_points(self, g: int, r: int) -> dict:
        t = self.t
        if t.complete:
            if self._bonus_cache is None or self._bonus_cache[0] != id(t):
                self._bonus_cache = (id(t), finishing_bonuses(t))
            bonuses = self._bonus_cache[1]
        else:
            bonuses = {}
        return golfer_round_points(t, g, r, self.pars, bonuses)

    def play_round(self) -> dict:
        """Play the next round of the current tournament. Returns what happened."""
        t = self.t
        if t.complete:
            raise LineupError("The tournament is over.")
        problem = self.lineup_problem()
        if problem:
            raise LineupError(problem)
        r = t.round_no
        seg = self.segment
        if r >= 2:
            for team in self.teams:
                if not team.human:
                    ai_between_rounds(team, t, self.golfers)
        for team in self.teams:
            team.lock_round(seg, t)
        leader_before = t.leaderboard()[0][0] if r else None
        t.play_round(self.golfers)
        for team in self.teams:
            team.score_round(t, r, self.pars, self.round_points)
        report = {"round": r + 1, "notes": [], "withdrawn": []}
        if not t.complete:
            wrng = self.rng("wd", r)
            for g in t.active():
                if wrng.random() < WITHDRAW_CHANCE:
                    t.withdrawn.append(g)
                    report["withdrawn"].append(g)
            before = len(self.me.notes)
            for team in self.teams:
                team.auto_swap(seg, t, self.golfers)
            report["notes"] = self.me.notes[before:]
        leader = t.leaderboard()[0][0]
        if r and leader != leader_before:
            report["new_leader"] = leader
        if t.complete:
            report["result"] = self.finish_event()
        return report

    def finish_event(self) -> dict:
        t, ev = self.t, self.event
        fx = shared_fedex(ev.kind, t.finish)
        field_avg = [
            sum(sum(t.scores[g][r]) for g in t.field if len(t.scores[g]) > r)
            / max(1, sum(1 for g in t.field if len(t.scores[g]) > r))
            for r in range(4)
        ]
        avg_skill = sum(self.golfers[g].skill for g in t.field) / len(t.field)
        for g in t.field:
            golfer = self.golfers[g]
            s = golfer.stats
            pos = t.finish[g]
            n = finish_number(pos)
            s["events"] += 1
            if golfer.tour == "PGA":
                self.fedex[g] = self.fedex.get(g, 0) + fx.get(g, 0)
                s["fedex"] += fx.get(g, 0)
            if pos not in ("MC", "WD"):
                s["cuts"] += 1
            if pos == "1":
                s["wins"] += 1
            if n <= 10:
                s["top10"] += 1
            if n < 999 and (not s["best"] or n < s["best"]):
                s["best"] = n
            resid = []
            for r, card in enumerate(t.scores[g]):
                s["rounds"] += 1
                s["strokes"] += sum(card) + ev.par
                s["eagles"] += sum(1 for h, p in zip(card, self.pars) if h <= -2 and not (h == -2 and p == 3))
                s["aces"] += sum(1 for h, p in zip(card, self.pars) if h == -2 and p == 3)
                s["birdies"] += sum(1 for h in card if h == -1)
                s["fantasy"] += self.round_points(g, r)["total"]
                resid.append((field_avg[r] - sum(card)) - (golfer.skill - avg_skill))
            if resid:
                golfer.add_form(sum(resid) / len(resid))
                s["sg"] = s.get("sg", 0.0) + sum(resid)
            golfer.results.append([self.event_index, pos])

        for team in self.teams:
            pts = team.event_total
            team.points += pts
            team.segment_points[ev.segment] += pts
            team.event_points[self.event_index] = pts

        winner = self.golfers[t.winner]
        best_team = max(self.teams, key=lambda tm: tm.event_total)
        mine = self.me.event_total
        rank = 1 + sum(1 for tm in self.teams if tm.event_total > mine)
        summary = {
            "event": self.event_index,
            "winner": t.winner,
            "score": t.total(t.winner),
            "my_points": mine,
            "my_rank": rank,
            "best_team": best_team.name,
            "best_points": best_team.event_total,
            "top": [g for g, _, _ in t.leaderboard()[:5]],
        }
        self.results.append(summary)
        self.news.insert(
            0,
            f"{winner.name} wins the {ev.name} at {to_par(t.total(t.winner))}. "
            f"{self.me.name} scored {mine} points ({_ordinal(rank)} in the league this week).",
        )
        if ev.real_winner and self.season == FIRST_SEASON:
            same = ev.real_winner == winner.name
            self.news.insert(
                1,
                f"In real life {ev.real_winner} won it in 2026" + (" - the same winner!" if same else "."),
            )
        self._update_records(summary)
        last_in_segment = self.event_index == max(data.segment_events(ev.segment))
        if last_in_segment:
            champ = max(self.teams, key=lambda tm: tm.segment_points[ev.segment])
            self.news.insert(0, f"{champ.name} win {data.SEGMENT_NAMES[ev.segment]} of the fantasy season!")
            summary["segment_winner"] = champ.name
        if self.event_index == len(data.SCHEDULE) - 1:
            self.season_over = True
        self.news = self.news[:40]
        return summary

    def _update_records(self, summary: dict):
        rec = self.records
        pts = summary["my_points"]
        if pts > rec.get("best_event", (-999,))[0]:
            rec["best_event"] = (pts, self.event.name, self.season)
        if pts < rec.get("worst_event", (9999,))[0]:
            rec["worst_event"] = (pts, self.event.name, self.season)
        for r in self.me.rounds:
            for g, p in r["points"].items():
                if p > rec.get("best_golfer_round", (-999,))[0]:
                    rec["best_golfer_round"] = (p, self.golfers[g].name, self.event.name, self.season)
        rec["weekly_wins"] = rec.get("weekly_wins", 0) + (1 if summary["my_rank"] == 1 else 0)

    def next_event(self):
        """Move on to the next tournament (or the next season)."""
        if not self.t.complete:
            return
        if self.season_over:
            self.new_season()
        else:
            self.event_index += 1
        self.start_event()

    # ================================================================ seasons
    def fedex_table(self) -> list[tuple[int, int]]:
        """[(golfer, points)] for tour members, best first."""
        members = [g for g in self.golfers if g.tour == "PGA"]
        ranked = sorted(members, key=lambda g: (-self.fedex.get(g.id, 0), g.owgr))
        return [(g.id, self.fedex.get(g.id, 0)) for g in ranked]

    def league_table(self, segment: int | None = None) -> list[Team]:
        if segment is None:
            return sorted(self.teams, key=lambda tm: -tm.points)
        return sorted(self.teams, key=lambda tm: -tm.segment_points[segment])

    def my_position(self, segment: int | None = None) -> int:
        return self.league_table(segment).index(self.me) + 1

    def new_season(self):
        table = self.league_table()
        fedex = self.fedex_table()
        entry = {
            "season": self.season,
            "position": self.my_position(),
            "points": self.me.points,
            "champion": table[0].name,
            "champion_points": table[0].points,
            "segments": [max(self.teams, key=lambda tm, s=s: tm.segment_points[s]).name for s in range(3)],
            "fedex_champion": self.golfers[fedex[0][0]].name,
            "majors": [
                (self.golfers[r["winner"]].name, data.SCHEDULE[r["event"]].short)
                for r in self.results
                if data.SCHEDULE[r["event"]].kind == "major"
            ],
        }
        self.history.append(entry)
        # golfers improve or decline with how they played, then the world ranking is redone
        rng = self.rng("season")
        for g in self.golfers:
            rounds = max(1, g.stats["rounds"])
            g.skill = round(
                max(-0.5, min(3.3, g.skill + 0.25 * g.stats.get("sg", 0.0) / rounds + rng.gauss(0, 0.15))), 2
            )
        for rank, g in enumerate(sorted(self.golfers, key=lambda g: -g.skill), 1):
            g.owgr = rank
        for g in self.golfers:
            g.stats = empty_stats()
            g.results = []
        for team in self.teams:
            team.points = 0
            team.segment_points = [0, 0, 0]
            team.event_points = {}
            team.usage = {0: {}, 1: {}, 2: {}}
            team.clear_week()
        self.fedex = {}
        self.results = []
        self.season += 1
        self.event_index = 0
        self.season_over = False
        self.news.insert(
            0, f"The {self.season} season starts in Hawaii. {entry['champion']} are the champions to beat."
        )

    # ================================================================ info for screens
    def win_chances(self) -> dict[int, float]:
        """A rough chance of winning for everyone in the field (for the odds column)."""
        field = self.t.field
        w = {g: math.exp(1.9 * (self.golfers[g].skill + self.golfers[g].form_bonus)) for g in field}
        total = sum(w.values())
        return {g: v / total for g, v in w.items()}

    def odds(self, g: int, chances: dict[int, float] | None = None) -> str:
        chances = chances or self.win_chances()
        p = chances.get(g, 0)
        if p <= 0:
            return "-"
        n = max(1, round(1 / p - 1))
        return f"{n}/1" if n < 1000 else "999/1"

    def status_label(self) -> str:
        t = self.t
        if t.complete:
            return "FINAL"
        if t.round_no == 0:
            return "LINEUPS OPEN"
        return f"AFTER ROUND {t.round_no}"

    def round_card_points(self, card: list[int]) -> int:
        b = round_breakdown(card, self.pars)
        return b["holes"] + b["streak"] + b["bogey_free"]

    # ================================================================ save / load
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "manager": self.manager,
            "seed": self.seed,
            "season": self.season,
            "golfers": [g.to_dict() for g in self.golfers],
            "teams": [t.to_dict() for t in self.teams],
            "event_index": self.event_index,
            "tournament": self.tournament.to_dict() if self.tournament else None,
            "fedex": {str(k): v for k, v in self.fedex.items()},
            "results": self.results,
            "news": self.news,
            "history": self.history,
            "records": self.records,
            "season_over": self.season_over,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Game:
        g = cls()
        g.manager = d["manager"]
        g.seed = d["seed"]
        g.season = d["season"]
        g.golfers = [Golfer.from_dict(x) for x in d["golfers"]]
        g.teams = [Team.from_dict(x) for x in d["teams"]]
        g.event_index = d["event_index"]
        g.tournament = Tournament.from_dict(d["tournament"]) if d.get("tournament") else None
        g.fedex = {int(k): v for k, v in d["fedex"].items()}
        g.results = d["results"]
        g.news = d["news"]
        g.history = d["history"]
        g.records = {k: tuple(v) if isinstance(v, list) else v for k, v in d.get("records", {}).items()}
        g.season_over = d.get("season_over", False)
        return g

    def save(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict()))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> Game:
        return cls.from_dict(json.loads(path.read_text()))


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def save_path() -> Path:
    return Path.home() / ".fantasy_pga" / "savegame.json"

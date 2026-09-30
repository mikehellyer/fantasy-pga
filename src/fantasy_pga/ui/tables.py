"""The information screens: league standings, schedule, FedExCup, golfers, records, rules."""

from __future__ import annotations

import pygame

from ..core import data
from ..core.fantasy import Team
from ..core.game import Game
from ..core.sim import to_par
from . import theme as T
from .app import Scene
from .screens import TOP, L, R, fit, is_back, ordinal
from .widgets import Table


class _Page(Scene):
    @property
    def g(self) -> Game:
        return self.app.game

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
            return
        if hasattr(self, "table"):
            self.table.handle(ev)


# ------------------------------------------------------------------ league
class StandingsScene(_Page):
    """Season table, each segment's table, and this week's scores. LEFT/RIGHT turns the page."""

    PAGES = ["SEASON", "SEGMENT 1", "SEGMENT 2", "SEGMENT 3", "THIS WEEK"]

    def __init__(self, app):
        super().__init__(app)
        self.page = 0
        self.table = Table(
            [
                ("Pos", 26, "r"),
                ("Team", 40, "l"),
                ("Manager", 250, "l"),
                ("Points", 470, "r"),
                ("Behind", 560, "r"),
            ],
            L,
            TOP + 20,
            580,
            visible=12,
            line_h=17,
            on_activate=lambda tm: app.push(TeamScene(app, tm)),
            sound=app.sound,
        )
        self.refresh()

    def score(self, tm: Team) -> int:
        if self.page == 0:
            return tm.points
        if self.page <= 3:
            return tm.segment_points[self.page - 1]
        return tm.event_total

    def refresh(self):
        teams = sorted(self.g.teams, key=lambda tm: -self.score(tm))
        top = self.score(teams[0])
        rows = []
        for tm in teams:
            s = self.score(tm)
            pos = 1 + sum(1 for o in teams if self.score(o) > s)
            behind = "-" if s == top else str(s - top)
            rows.append(
                ([str(pos), tm.name, tm.manager, str(s), behind], T.YELLOW if tm.human else T.WHITE, tm)
            )
        self.table.set_rows(rows)

    def handle(self, ev):
        turn = 0
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_LEFT, pygame.K_RIGHT):
            turn = -1 if ev.key == pygame.K_LEFT else 1
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and ev.pos[1] < TOP:
            turn = 1
        if turn:
            self.page = (self.page + turn) % len(self.PAGES)
            self.refresh()
            self.app.sound.play("blip")
            return
        super().handle(ev)

    def draw(self, surf):
        g = self.g
        T.frame(surf)
        T.header(surf, f"LEAGUE STANDINGS - {self.PAGES[self.page]}", f"{g.season}  < LEFT / RIGHT >")
        sub = {0: "All 32 tournaments", 4: f"{g.event.name} ({g.status_label().lower()})"}.get(
            self.page, f"{len(data.segment_events(self.page - 1))} tournaments - a prize of its own"
        )
        T.text(surf, sub, (L, TOP), T.CYAN, size=11)
        self.table.draw(surf)
        T.footer(surf, "LEFT/RIGHT: turn page   RETURN: see that team's golfers this week   ESC: back")


class TeamScene(_Page):
    """A team's six golfers this week, and how many starts each has used."""

    def __init__(self, app, team: Team):
        super().__init__(app)
        self.team = team

    def draw(self, surf):
        g, tm = self.g, self.team
        t = g.t
        T.frame(surf)
        T.header(surf, tm.name.upper(), f"Manager: {tm.manager}")
        y = TOP
        if tm is not g.me and t.round_no == 0:
            T.text(surf, "Rivals' lineups are secret until the tournament starts!", (L, y + 20), T.LIGHT_RED)
            T.footer(surf, "ESC: back")
            return
        T.text(surf, f"THIS WEEK - {g.event.name.upper()}", (L, y), T.YELLOW, bold=True)
        T.text(surf, "Pos  To par  R1  R2  R3  R4   Tot", (R, y), T.LIGHT_GREY, size=11, right=True)
        y += 18
        board = {gid: (p, tot) for gid, p, tot in t.leaderboard()} if t.round_no else {}
        active = set(t.active())
        for gid in sorted(tm.picks, key=lambda p: (p != tm.captain, p not in tm.starters, g.golfers[p].owgr)):
            gf = g.golfers[gid]
            role = "C" if gid == tm.captain else "S" if gid in tm.starters else "b"
            col = T.YELLOW if role == "C" else T.WHITE if role == "S" else T.LIGHT_GREY
            T.text(surf, role, (L, y), col, bold=True)
            T.text(surf, fit(gf.name, 24), (L + 16, y), col)
            if gid in board:
                p, tot = board[gid]
                if gid not in active:
                    p = t.finish.get(gid) or ("WD" if gid in t.withdrawn else "MC")
                T.text(surf, p, (R - 218, y), T.WHITE, right=True)
                T.text(surf, to_par(tot), (R - 170, y), T.score_colour(tot), right=True)
            total = 0
            for r in range(4):
                if r < len(tm.rounds) and gid in tm.rounds[r]["points"]:
                    pts = tm.rounds[r]["points"][gid]
                    total += pts
                    cap = tm.rounds[r]["captain"] == gid
                    T.text(surf, str(pts), (R - 120 + r * 28, y), T.YELLOW if cap else T.CYAN, right=True)
            T.text(surf, str(total), (R, y), T.WHITE, right=True)
            y += 16
        T.text(surf, f"Points this week: {tm.event_total}", (L, y + 6), T.LIGHT_GREEN, bold=True)
        # most-used golfers this segment
        seg = g.segment
        used = sorted(tm.usage[seg].items(), key=lambda kv: -kv[1])
        y += 34
        T.text(surf, f"STARTS USED IN {data.SEGMENT_NAMES[seg].upper()}", (L, y), T.YELLOW, bold=True)
        y += 16
        line = (
            ", ".join(f"{g.golfers[gid].surname} {n}/{data.STARTS_PER_SEGMENT}" for gid, n in used)
            or "None yet"
        )
        for i, part in enumerate(T.wrap(line, 84)[:5]):
            T.text(surf, part, (L, y + i * 14), T.WHITE, size=11)
        T.footer(surf, "C = captain, S = starter, b = bench.  Yellow points were doubled.   ESC: back")


# ------------------------------------------------------------------ schedule
class ScheduleScene(_Page):
    def __init__(self, app):
        super().__init__(app)
        self.table = Table(
            [
                ("Date", 0, "l"),
                ("Tournament", 60, "l"),
                ("", 200, "l"),
                ("Winner / course", 250, "l"),
                ("Score", 440, "r"),
                ("Pts", 490, "r"),
                ("Wk", 530, "r"),
            ],
            L,
            TOP,
            560,
            visible=18,
            sound=app.sound,
        )
        g = self.g
        done = {r["event"]: r for r in g.results}
        rows = []
        for i, ev in enumerate(data.SCHEDULE):
            r = done.get(i)
            tag = {"major": "MAJOR", "signature": "SIG", "players": "FLAG", "playoff": "PLAYOFF"}.get(
                ev.kind, ""
            )
            if r:
                pts, place = g.week_points(r)
                cells = [ev.date, ev.short, tag, fit(g.golfers[r["winner"]].name, 22), to_par(r["score"]),
                         str(pts), ordinal(place)]  # fmt: skip
                col = T.WHITE
            elif i == g.event_index:
                cells = [ev.date, ev.short, tag, "<< THIS WEEK >>", "", "", ""]
                col = T.YELLOW
            else:
                cells = [ev.date, ev.short, tag, fit(ev.course, 24), "", "", ""]
                col = T.LIGHT_GREY
            rows.append((cells, col, i))
        self.table.set_rows(rows)
        self.table.index = g.event_index
        self.table._scroll()

    def draw(self, surf):
        g = self.g
        T.frame(surf)
        T.header(surf, f"SCHEDULE & RESULTS {g.season}", "Pts / Wk = your points and league place that week")
        self.table.draw(surf)
        T.footer(
            surf, "Segment 1: Hawaii to THE PLAYERS   Segment 2: to the Memorial   Segment 3: to East Lake"
        )


# ------------------------------------------------------------------ FedExCup
class FedExScene(_Page):
    def __init__(self, app):
        super().__init__(app)
        self.table = Table(
            [
                ("Pos", 26, "r"),
                ("Golfer", 36, "l"),
                ("", 230, "l"),
                ("Points", 330, "r"),
                ("Ev", 370, "r"),
                ("Wins", 410, "r"),
                ("Top10", 460, "r"),
                ("", 480, "l"),
            ],  # fmt: skip
            L,
            TOP + 16,
            580,
            visible=17,
            sound=app.sound,
        )
        g = self.g
        me = g.me
        rows = []
        for i, (gid, pts) in enumerate(g.fedex_table()):
            gf = g.golfers[gid]
            s = gf.stats
            note = "(playoffs)" if i == 69 else "(BMW)" if i == 49 else "(East Lake)" if i == 29 else ""
            rows.append(
                (
                    [
                        str(i + 1),
                        fit(gf.name, 22),
                        gf.country,
                        str(pts),
                        str(s["events"]),
                        str(s["wins"]),
                        str(s["top10"]),
                        note,
                    ],  # fmt: skip
                    T.YELLOW if gid in me.picks else T.WHITE,
                    gid,
                )
            )
        self.table.set_rows(rows)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, "FEDEXCUP STANDINGS", "PGA TOUR members only")
        T.text(surf, "Top 70 reach the playoffs, top 50 the BMW, top 30 East Lake", (L, TOP), T.CYAN, size=11)
        self.table.draw(surf)
        T.footer(surf, "Yellow = in your team this week   ESC: back")


# ------------------------------------------------------------------ golfers
class GolfersScene(_Page):
    SORTS = [
        ("world rank", lambda g: g.owgr),
        ("fantasy points", lambda g: -g.stats["fantasy"]),
        ("wins", lambda g: (-g.stats["wins"], -g.stats["top10"])),
        ("scoring average", lambda g: g.scoring_average() or 999),
        ("form", lambda g: -g.form_value),
    ]

    def __init__(self, app):
        super().__init__(app)
        self.sort = 0
        self.table = Table(
            [
                ("Rk", 22, "r"),
                ("Golfer", 30, "l"),
                ("Tour", 196, "l"),
                ("Rtg", 256, "r"),
                ("Form", 266, "l"),
                ("Ev", 330, "r"),
                ("W", 356, "r"),
                ("T10", 390, "r"),
                ("Avg", 440, "r"),
                ("FPts", 490, "r"),
                ("Used", 540, "r"),
            ],  # fmt: skip
            L,
            TOP + 16,
            580,
            visible=17,
            on_activate=lambda gid: app.push(GolferScene(app, gid)),
            sound=app.sound,
        )
        self.refresh()

    def refresh(self):
        g = self.g
        seg = g.segment
        key = self.SORTS[self.sort][1]
        rows = []
        for gf in sorted(g.golfers, key=key):
            s = gf.stats
            avg = f"{gf.scoring_average():.2f}" if s["rounds"] else "-"
            used = g.me.starts_used(gf.id, seg)
            rows.append(
                (
                    [
                        str(gf.owgr),
                        fit(gf.name, 20),
                        gf.tour,
                        str(gf.rating),
                        gf.form_label,
                        str(s["events"]),
                        str(s["wins"]),
                        str(s["top10"]),
                        avg,
                        str(s["fantasy"]),
                        f"{used}/{data.STARTS_PER_SEGMENT}",
                    ],  # fmt: skip
                    T.YELLOW if gf.id in g.me.picks else T.WHITE,
                    gf.id,
                )
            )
        self.table.set_rows(rows)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_o:
            self.sort = (self.sort + 1) % len(self.SORTS)
            self.table.index = 0
            self.refresh()
            return
        super().handle(ev)

    def draw(self, surf):
        g = self.g
        T.frame(surf)
        T.header(surf, "GOLFER STATS", f"{g.season} season")
        T.text(surf, f"Sorted by {self.SORTS[self.sort][0]}", (L, TOP), T.CYAN, size=11)
        T.text(
            surf,
            f"Used = your starts in {data.SEGMENT_NAMES[g.segment]}",
            (R, TOP),
            T.LIGHT_GREY,
            size=11,
            right=True,
        )
        self.table.draw(surf)
        T.footer(surf, "O: change sort   RETURN: golfer's season   FPts = fantasy points   ESC: back")


class GolferScene(_Page):
    def __init__(self, app, gid: int):
        super().__init__(app)
        self.gid = gid

    def draw(self, surf):
        g = self.g
        gf = g.golfers[self.gid]
        s = gf.stats
        T.frame(surf)
        T.header(
            surf,
            gf.name.upper(),
            f"{data.COUNTRY_NAMES.get(gf.country, gf.country)}  -  {data.TOUR_NAMES[gf.tour]}",
        )
        x, y = L, TOP + 4
        facts = [
            ("World ranking", str(gf.owgr)),
            ("Rating", f"{gf.rating}  ({gf.skill:+.2f} strokes a round)"),
            ("Form", gf.form_label),
            ("Events / cuts made", f"{s['events']} / {s['cuts']}"),
            ("Wins / top 10s", f"{s['wins']} / {s['top10']}"),
            ("Best finish", str(s["best"] or "-")),
            ("Scoring average", f"{gf.scoring_average():.2f}" if s["rounds"] else "-"),
            ("Eagles / birdies / aces", f"{s['eagles']} / {s['birdies']} / {s['aces']}"),
            ("FedExCup points", str(g.fedex.get(gf.id, 0)) if gf.tour == "PGA" else "not a member"),
            ("Fantasy points", str(s["fantasy"])),
        ]
        for label, val in facts:
            T.text(surf, label, (x, y), T.LIGHT_GREY)
            T.text(surf, val, (x + 190, y), T.form_colour(val) if label == "Form" else T.WHITE)
            y += 16
        T.text(
            surf,
            "Your starts: " + "  ".join(f"S{k + 1} {g.me.starts_used(gf.id, k)}/3" for k in range(3)),
            (x, y + 6),
            T.YELLOW,
        )
        # results this season
        x, y = 400, TOP + 4
        T.text(surf, "THIS SEASON", (x, y), T.YELLOW, bold=True)
        y += 16
        for ev_i, pos in gf.results[-16:]:
            T.text(surf, data.SCHEDULE[ev_i].short, (x, y), T.WHITE, size=11)
            T.text(surf, pos, (R, y), T.CYAN if pos not in ("MC", "WD") else T.GREY, size=11, right=True)
            y += 13
        if not gf.results:
            T.text(surf, "No events yet", (x, y), T.LIGHT_GREY, size=11)
        T.footer(surf, "ESC: back")


# ------------------------------------------------------------------ records
class RecordsScene(_Page):
    def draw(self, surf):
        g = self.g
        T.frame(surf)
        T.header(surf, "RECORDS & HISTORY", g.manager)
        x, y = L, TOP
        T.text(surf, "YOUR RECORDS", (x, y), T.YELLOW, bold=True)
        y += 16
        rec = g.my_records()
        lines = []
        if "best_event" in rec:
            p, name, season = rec["best_event"][:3]
            lines.append(f"Best week: {p} pts, {name} {season}")
        if "worst_event" in rec:
            p, name, season = rec["worst_event"][:3]
            lines.append(f"Worst week: {p} pts, {name} {season}")
        if "best_golfer_round" in rec:
            p, who, name, season = rec["best_golfer_round"][:4]
            lines.append(f"Best round by one golfer: {p} pts, {who} ({name} {season})")
        lines.append(f"Weeks won in the league: {rec.get('weekly_wins', 0)}")
        for line in lines:
            T.text(surf, line, (x, y), T.WHITE, size=11)
            y += 14
        y += 10
        T.text(surf, "PAST SEASONS", (x, y), T.YELLOW, bold=True)
        y += 16
        if not g.history:
            T.text(surf, "Your first season is still going.", (x, y), T.LIGHT_GREY, size=11)
        for h in g.history[-8:]:
            pos, pts = h["position"], h["points"]
            names = [row[0] for row in h.get("table", [])]
            if g.me.name in names:
                pos, pts = names.index(g.me.name) + 1, h["table"][names.index(g.me.name)][1]
            T.text(
                surf,
                f"{h['season']}: you {ordinal(pos)} ({pts} pts). "
                f"Champions: {h['champion']}. FedExCup: {h['fedex_champion']}",
                (x, y),
                T.WHITE,
                size=11,
            )
            y += 13
            majors = ", ".join(f"{m[1].title()}: {m[0]}" for m in h.get("majors", []))
            if majors:
                T.text(surf, "   " + fit(majors, 84), (x, y), T.LIGHT_GREY, size=10)
                y += 13
        # this season's major winners
        majors = [(data.SCHEDULE[r["event"]].name, g.golfers[r["winner"]].name, r["score"]) for r in g.results
                  if data.SCHEDULE[r["event"]].kind in ("major", "players")]  # fmt: skip
        if majors:
            y += 8
            T.text(surf, f"{g.season} MAJORS", (x, y), T.YELLOW, bold=True)
            y += 16
            for name, who, score in majors:
                T.text(surf, f"{name}: {who} ({to_par(score)})", (x, y), T.WHITE, size=11)
                y += 13
        T.footer(surf, "ESC: back")


class RulesScene(_Page):
    def draw(self, surf):
        T.frame(surf)
        T.header(surf, "SCORING & RULES", "as in PGA TOUR Fantasy Golf")
        x, y = L, TOP
        rules = [
            f"Pick {data.ROSTER_SIZE} golfers each week. {data.STARTERS} start each round and score; 2 sit on the bench.",
            "Your CAPTAIN must be a starter and scores DOUBLE, finishing bonus included.",
            f"Any golfer can start only {data.STARTS_PER_SEGMENT} times per segment (bench weeks don't count).",
            "Between rounds you can swap starters and bench and change your captain.",
            "Starters who miss the cut or withdraw are auto-swapped for bench golfers.",
        ]
        for line in rules:
            T.text(surf, line, (x, y), T.WHITE, size=11)
            y += 14
        y += 8
        T.text(surf, "POINTS", (x, y), T.YELLOW, bold=True)
        y += 16
        hp = data.HOLE_POINTS
        pts = [
            ("Albatross", hp[-3]), ("Eagle", hp[-2]), ("Birdie", hp[-1]), ("Par", hp[0]), ("Bogey", hp[1]),
            ("Double bogey or worse", data.DOUBLE_OR_WORSE), ("Hole-in-one bonus", data.HOLE_IN_ONE_BONUS),
            ("3+ birdies in a row (once a round)", data.BIRDIE_STREAK), ("Bogey-free round", data.BOGEY_FREE),
            ("All 4 rounds under 70", data.ALL_ROUNDS_UNDER_70),
        ]  # fmt: skip
        for i, (label, v) in enumerate(pts):
            cx = x + (i // 5) * 300
            cy = y + (i % 5) * 14
            T.text(surf, label, (cx, cy), T.LIGHT_GREY, size=11)
            T.text(surf, f"{v:+d}", (cx + 280, cy), T.CYAN, size=11, right=True)
        y += 5 * 14 + 10
        T.text(
            surf,
            "FINISHING BONUS = the golfer's FedExCup points / 10, added to round 4:",
            (x, y),
            T.WHITE,
            size=11,
        )
        y += 14
        T.text(
            surf,
            "winner 50 (regular event), 70 (signature, playoffs), 75 (majors, THE PLAYERS).",
            (x, y),
            T.WHITE,
            size=11,
        )
        y += 22
        T.text(surf, "SEGMENTS", (x, y), T.YELLOW, bold=True)
        y += 16
        for s in range(3):
            evs = data.segment_events(s)
            first, last = data.SCHEDULE[evs[0]].short, data.SCHEDULE[evs[-1]].short
            T.text(
                surf,
                f"{data.SEGMENT_NAMES[s]}: {len(evs)} events, {first.title()} to {last.title()}",
                (x, y),
                T.WHITE,
                size=11,
            )
            y += 14
        T.footer(surf, "Point values live in core/data.py if you want to change them.   ESC: back")

"""After a tournament: the champion, your team's points, and the season's end."""

from __future__ import annotations

import pygame

from ..core import data
from ..core.game import Game
from ..core.sim import to_par
from . import theme as T
from .app import Scene
from .screens import TOP, L, R, fit, is_back, ordinal


class EventResultScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        app.sound.play("applause")

    @property
    def g(self) -> Game:
        return self.app.game

    def handle(self, ev):
        if (
            is_back(ev)
            or (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_SPACE))
            or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1)
        ):
            self.app.pop()
            if self.g.season_over and not any(isinstance(s, SeasonEndScene) for s in self.app.scenes):
                self.app.push(SeasonEndScene(self.app))

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        g = self.g
        t, ev, me = g.t, g.event, g.me
        T.frame(surf, T.YELLOW if int(self.t * 3) % 2 == 0 and self.t < 2 else T.FG)
        T.header(surf, f"{ev.name.upper()} - FINAL", f"{ev.course}")
        winner = g.golfers[t.winner]
        T.big_text(
            surf, winner.name.upper(), (T.CANVAS_W // 2, TOP + 2), T.YELLOW, 2, center=True, shadow=T.BLACK
        )
        T.text(
            surf,
            f"wins at {to_par(t.total(t.winner))} ({sum(t.round_strokes(t.winner, r) for r in range(4))} strokes)",
            (T.CANVAS_W // 2, TOP + 34),
            T.WHITE,
            center=True,
        )
        y = TOP + 50
        if t.playoff:
            T.text(surf, fit(t.playoff[-1], 80), (T.CANVAS_W // 2, y), T.CYAN, center=True, size=11)
            y += 13
        if ev.real_winner and g.season == 2026:
            same = ev.real_winner == winner.name
            line = f"Real 2026 winner: {ev.real_winner}" + ("  - THE SAME!" if same else "")
            T.text(
                surf,
                line,
                (T.CANVAS_W // 2, y),
                T.LIGHT_GREEN if same else T.LIGHT_GREY,
                center=True,
                size=11,
            )
        # top ten
        y = TOP + 72
        T.text(surf, "TOP 10", (L, y), T.YELLOW, bold=True)
        y += 16
        for gid, pos, tot in t.leaderboard()[:10]:
            col = T.YELLOW if gid in me.picks else T.WHITE
            T.text(surf, pos, (L + 24, y), col, size=11, right=True)
            T.text(surf, fit(g.golfers[gid].name, 22), (L + 32, y), col, size=11)
            T.text(surf, to_par(tot), (L + 230, y), T.score_colour(tot, col), size=11, right=True)
            y += 13

        # your team
        x, y = 280, TOP + 72
        T.text(surf, f"{me.name.upper()}", (x, y), T.YELLOW, bold=True)
        T.text(surf, "R1  R2  R3  R4  TOT", (R, y), T.LIGHT_GREY, size=11, right=True)
        y += 16
        for gid in sorted(me.picks, key=lambda p: g.golfers[p].owgr):
            gf = g.golfers[gid]
            T.text(surf, t.finish.get(gid, "-"), (x + 24, y), T.WHITE, size=11, right=True)
            T.text(surf, fit(gf.name, 16), (x + 30, y), T.WHITE, size=11)
            tot = 0
            for r in range(4):
                lock = me.rounds[r] if r < len(me.rounds) else None
                cx = R - 132 + r * 28
                if lock and gid in lock["points"]:
                    p = lock["points"][gid]
                    tot += p
                    cap = lock["captain"] == gid
                    T.text(surf, str(p), (cx + 14, y), T.YELLOW if cap else T.CYAN, size=11, right=True)
                else:
                    T.text(surf, "-", (cx + 14, y), T.DARK_GREY, size=11, right=True)
            T.text(surf, str(tot), (R, y), T.WHITE, size=11, right=True)
            y += 13
        T.text(surf, "Yellow = captain (doubled)", (x, y + 2), T.YELLOW, size=10)
        T.text(surf, f"TOTAL {me.event_total}", (R, y + 2), T.LIGHT_GREEN, bold=True, right=True)

        # the league this week
        y += 22
        week = sorted(g.teams, key=lambda tm: -tm.event_total)
        T.text(surf, f"This week: {ordinal(week.index(me) + 1)} of 12", (x, y), T.CYAN)
        T.text(surf, f"Top: {fit(week[0].name, 18)} {week[0].event_total}", (x, y + 14), T.WHITE, size=11)
        T.text(surf, f"Season: {ordinal(g.my_position())}  ({me.points} pts)", (x, y + 28), T.WHITE, size=11)
        last = g.results[-1] if g.results else {}
        if last.get("segment_winner"):
            T.text(
                surf,
                f"{data.SEGMENT_NAMES[ev.segment]} winners: {last['segment_winner']}",
                (L, T.CANVAS_H - T.BORDER - 34),
                T.YELLOW,
                bold=True,
            )
        T.footer(surf, "Press any key to continue")


class SeasonEndScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        app.sound.play("roar")

    @property
    def g(self) -> Game:
        return self.app.game

    def handle(self, ev):
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.pop()

    def update(self, dt):
        self.t += dt

    def draw(self, surf):
        g = self.g
        table = g.league_table()
        me = g.me
        T.frame(surf)
        T.header(surf, f"THE {g.season} SEASON IS OVER", "FINAL LEAGUE TABLE")
        champ = table[0]
        col = [T.YELLOW, T.WHITE, T.CYAN, T.LIGHT_GREEN][int(self.t * 4) % 4]
        T.big_text(surf, champ.name.upper(), (T.CANVAS_W // 2, TOP + 2), col, 2, center=True, shadow=T.BLACK)
        T.text(
            surf,
            f"are the champions with {champ.points} points",
            (T.CANVAS_W // 2, TOP + 34),
            T.WHITE,
            center=True,
        )
        y = TOP + 56
        for i, tm in enumerate(table):
            c = T.YELLOW if tm is me else T.WHITE
            T.text(surf, f"{i + 1:>2}.", (L + 60, y), c)
            T.text(surf, tm.name, (L + 90, y), c)
            T.text(surf, tm.manager, (L + 300, y), T.LIGHT_GREY if tm is not me else c, size=11)
            T.text(surf, str(tm.points), (L + 520, y), c, right=True)
            y += 15
        fedex = g.fedex_table()[0]
        T.text(
            surf,
            f"FedExCup champion: {g.golfers[fedex[0]].name} ({fedex[1]} pts)",
            (T.CANVAS_W // 2, y + 6),
            T.CYAN,
            center=True,
        )
        T.footer(surf, "Press any key - then choose 'Start Next Season' from the menu")

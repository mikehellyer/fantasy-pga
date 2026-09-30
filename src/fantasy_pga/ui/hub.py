"""The main menu between rounds and tournaments."""

from __future__ import annotations

import pygame

from ..core import data
from ..core.game import Game, LineupError, save_path
from ..core.sim import to_par
from . import theme as T
from .app import Scene
from .screens import TOP, L, MessageScene, autosave, fit, open_update, ordinal
from .widgets import Menu

WIND_WORDS = ["CALM", "BREEZY", "WINDY", "BLOWING A GALE"]


class HubScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.build_menu()

    @property
    def g(self) -> Game:
        return self.app.game

    def build_menu(self):
        from .lineup import PickScene
        from .tables import (
            FedExScene,
            GolfersScene,
            RecordsScene,
            RulesScene,
            ScheduleScene,
            StandingsScene,
        )

        app, g = self.app, self.g
        t = g.t
        items = []
        if t.complete:
            items.append(("Tournament Result", self.show_result))
            nxt = "Start Next Season" if g.season_over else "Next Tournament"
            items.append((nxt, self.next_event))
        elif t.round_no == 0:
            items.append(("Pick Your Team", lambda: app.push(PickScene(app))))
            items.append(("Tee Off - Round 1", self.play))
        else:
            items.append((f"Lineup for Round {t.round_no + 1}", lambda: app.push(PickScene(app))))
            items.append((f"Play Round {t.round_no + 1}", self.play))
        from .leaderboard import LeaderboardScene

        items += [
            ("Leaderboard", lambda: app.push(LeaderboardScene(app))),
            ("League Standings", lambda: app.push(StandingsScene(app))),
            ("Schedule & Results", lambda: app.push(ScheduleScene(app))),
            ("FedExCup Standings", lambda: app.push(FedExScene(app))),
            ("Golfer Stats", lambda: app.push(GolfersScene(app))),
            ("Records & History", lambda: app.push(RecordsScene(app))),
            ("Scoring & Rules", lambda: app.push(RulesScene(app))),
            ("Save Game", self.save),
            ("Quit to Title", self.quit),
        ]
        if app.update_info:
            items.append(
                (f"U. UPDATE TO v{app.update_info['version']}", lambda: open_update(app), True, "alert")
            )
        self.menu = Menu(items, T.CANVAS_W - 222, TOP + 6, w=200, line_h=18, sound=app.sound)
        self._had_update = bool(app.update_info)
        self._state = (g.season, g.event_index, t.round_no)

    # -------------------------------------------------------------- actions
    def play(self):
        from .live import LiveRoundScene

        g = self.g
        problem = g.lineup_problem()
        if problem:
            from .lineup import PickScene

            self.app.push(
                MessageScene(
                    self.app,
                    "YOUR LINEUP ISN'T READY",
                    [problem, "", "Pick it yourself, or let your caddie fill the gaps?"],
                    on_yes=lambda: self.app.push(PickScene(self.app)),
                    on_no=self._caddie_and_play,
                    yes_label="Pick team",
                    no_label="Caddie picks",
                )
            )
            return
        try:
            report = g.play_round()
        except LineupError as exc:
            self.app.push(MessageScene(self.app, "CAN'T PLAY YET", [str(exc)]))
            return
        autosave(self.app)
        self.app.push(LiveRoundScene(self.app, report))

    def _caddie_and_play(self):
        g = self.g
        if g.t.round_no == 0:
            g.auto_pick()
        else:
            me = g.me
            for p in me.picks:
                if len(me.starters) < data.STARTERS and p not in me.starters:
                    g.toggle_starter(p)
            if me.captain not in me.starters and me.starters:
                me.captain = me.starters[0]
        if not g.lineup_problem():
            self.play()

    def show_result(self):
        from .results import EventResultScene

        self.app.push(EventResultScene(self.app))

    def next_event(self):
        self.g.next_event()
        autosave(self.app)
        self.build_menu()
        self.app.push(
            MessageScene(
                self.app,
                self.g.event.name.upper(),
                [
                    f"{self.g.event.course}, {self.g.event.location}.",
                    f"{len(self.g.t.field)} golfers in the field. Time to pick your team!",
                ],
            )
        )

    def save(self):
        try:
            self.g.save(save_path())
            self.app.push(MessageScene(self.app, "GAME SAVED", [f"Saved to {save_path()}"]))
        except OSError as exc:
            self.app.push(MessageScene(self.app, "SAVE FAILED", [str(exc)]))

    def quit(self):
        from .intro import TitleScene

        autosave(self.app)
        self.app.reset(TitleScene(self.app))

    # -------------------------------------------------------------- loop
    def on_enter(self):
        self.build_menu()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.quit()
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_u and self.app.update_info:
            open_update(self.app)
            return
        self.menu.handle(ev)

    def update(self, dt):
        g = self.g
        if (self.app.update_info and not self._had_update) or self._state != (
            g.season,
            g.event_index,
            g.t.round_no,
        ):
            self.build_menu()

    def draw(self, surf):
        g = self.g
        me, t, ev = g.me, g.t, g.event
        T.frame(surf)
        T.header(surf, me.name.upper(), f"{g.season} SEASON  -  {data.SEGMENT_NAMES[ev.segment].upper()}")

        x, y = L, TOP + 4
        T.text(surf, f"Manager: {g.manager}", (x, y), T.LIGHT_GREY)
        pos, seg_pos = g.my_position(), g.my_position(ev.segment)
        T.text(surf, f"League: {ordinal(pos)} of 12   {me.points} pts", (x, y + 15), T.WHITE)
        T.text(
            surf,
            f"{data.SEGMENT_NAMES[ev.segment]}: {ordinal(seg_pos)}   {me.segment_points[ev.segment]} pts",
            (x, y + 30),
            T.WHITE,
        )

        # this week's tournament
        y += 52
        box = pygame.Rect(x - 4, y, 390, 60)
        pygame.draw.rect(surf, T.BLACK, box)
        kind = data.KIND_LABEL[ev.kind]
        T.text(
            surf, f"EVENT {g.event_index + 1}/32  {ev.date.upper()}", (x + 4, y + 4), T.LIGHT_GREY, size=11
        )
        if kind:
            T.text(surf, kind, (box.right - 6, y + 4), T.YELLOW, size=11, right=True)
        T.text(surf, ev.name.upper(), (x + 4, y + 18), T.CYAN, bold=True)
        T.text(surf, fit(f"{ev.course}, par {ev.par}", 48), (x + 4, y + 34), T.WHITE, size=11)
        status = g.status_label()
        if t.round_no and not t.complete:
            lead = t.leaderboard()[0]
            status += f"   Leader: {g.golfers[lead[0]].short} {to_par(lead[2])}"
        elif t.complete:
            status += f"   Winner: {g.golfers[t.winner].short} {to_par(t.total(t.winner))}"
        T.text(surf, fit(status, 56), (x + 4, y + 46), T.LIGHT_GREEN, size=11)

        # your team
        y += 68
        T.text(surf, "YOUR TEAM", (x, y), T.YELLOW, bold=True)
        if t.round_no:
            T.text(surf, f"{me.event_total} pts this week", (x + 386, y), T.WHITE, right=True)
        y += 16
        if not me.picks:
            T.text(surf, "No golfers picked yet - choose 'Pick Your Team'.", (x, y), T.LIGHT_RED)
        board = {gid: (p, tot) for gid, p, tot in t.leaderboard()} if t.round_no else {}
        active = set(t.active())
        for gid in sorted(me.picks, key=lambda p: (p not in me.starters, g.golfers[p].owgr)):
            golfer = g.golfers[gid]
            role = "C" if gid == me.captain else "S" if gid in me.starters else "b"
            col = T.YELLOW if role == "C" else T.WHITE if role == "S" else T.LIGHT_GREY
            T.text(surf, role, (x, y), col, bold=True)
            T.text(surf, fit(golfer.name, 22), (x + 16, y), col)
            left = me.starts_left(gid, ev.segment)
            T.text(surf, f"{left} left", (x + 200, y), T.LIGHT_GREY, size=11)
            if gid in board:
                p, tot = board[gid]
                if gid not in active:
                    p = t.finish.get(gid) or ("WD" if gid in t.withdrawn else "MC")
                T.text(surf, p, (x + 290, y), T.WHITE, right=True)
                T.text(surf, to_par(tot), (x + 330, y), T.score_colour(tot), right=True)
                pts = sum(r["points"].get(gid, 0) for r in me.rounds)
                T.text(surf, f"{pts}", (x + 386, y), T.CYAN, right=True)
            y += 14

        # news
        if g.news:
            lines = T.wrap(g.news[0], 88)[:2]
            for i, line in enumerate(lines):
                T.text(surf, line, (L, T.CANVAS_H - T.BORDER - 46 + i * 13), T.LIGHT_GREEN, size=11)
        self.menu.draw(surf)
        T.footer(surf, "Number keys, arrows + RETURN, or mouse.  F11: fullscreen   ESC: save & quit to title")

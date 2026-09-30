"""Picking your six golfers, your four starters and your captain."""

from __future__ import annotations

import pygame

from ..core import data
from ..core.game import Game
from ..core.sim import to_par
from . import theme as T
from .app import Scene
from .screens import TOP, L, R, autosave, fit, is_back
from .widgets import Table

SORTS = [("World rank", "rank"), ("Odds", "odds"), ("Form", "form"), ("Fantasy pts", "pts")]


class PickScene(Scene):
    """Before round 1: choose six from the whole field. Between rounds: only your six,
    to move golfers between the starters and the bench and pick a captain."""

    def __init__(self, app):
        super().__init__(app)
        self.message = ""
        self.sort = 0
        self.mine_only = self.g.t.round_no > 0
        self.chances = self.g.win_chances()
        self.table = Table(
            [
                ("Rk", 22, "r"),
                ("Golfer", 30, "l"),
                ("", 190, "l"),
                ("Rtg", 244, "r"),
                ("Form", 252, "l"),
                ("Odds", 340, "r"),
                ("Left", 378, "r"),
                ("", 386, "l"),
            ],
            L,
            TOP + 18,
            400,
            visible=16,
            line_h=15,
            on_activate=self.activate,
            sound=app.sound,
            click_activates=True,
        )
        if self.locked:
            self.table.columns[4] = ("Pos", 252, "l")
            self.table.columns[5] = ("Score", 340, "r")
        self.refresh()

    @property
    def g(self) -> Game:
        return self.app.game

    @property
    def locked(self) -> bool:
        return self.g.t.round_no > 0

    def refresh(self):
        g = self.g
        me, t = g.me, g.t
        seg = g.segment
        field = list(me.picks) if self.mine_only else list(t.field)
        key = SORTS[self.sort][1]
        if key == "rank":
            field.sort(key=lambda x: g.golfers[x].owgr)
        elif key == "odds":
            field.sort(key=lambda x: -self.chances.get(x, 0))
        elif key == "form":
            field.sort(key=lambda x: -g.golfers[x].form_value)
        else:
            field.sort(key=lambda x: -g.golfers[x].stats["fantasy"])
        board = {gid: (p, tot) for gid, p, tot in t.leaderboard()} if t.round_no else {}
        active = set(t.active())
        rows = []
        for gid in field:
            gf = g.golfers[gid]
            left = me.starts_left(gid, seg)
            mark = ""
            if gid in me.picks:
                mark = "C" if gid == me.captain else "S" if gid in me.starters else "b"
            form, odds = gf.form_label, g.odds(gid, self.chances)
            if gid in board:  # between rounds: where he is on the leaderboard instead
                p, tot = board[gid]
                form, odds = (p, to_par(tot)) if gid in active else ("WD" if gid in t.withdrawn else "MC", "")
            colour = T.WHITE
            if gid in me.picks:
                colour = T.YELLOW
            elif left <= 0 or (self.locked and gid not in active):
                colour = T.GREY
            rows.append(
                (
                    [
                        str(gf.owgr),
                        fit(gf.name, 20),
                        gf.country,
                        str(gf.rating),
                        form,
                        odds,
                        str(left),
                        mark,
                    ],
                    colour,
                    gid,
                )
            )
        self.table.set_rows(rows)

    # -------------------------------------------------------------- actions
    def activate(self, gid):
        if gid is None:
            return
        g = self.g
        if self.locked:
            self.message = g.toggle_starter(gid)
        else:
            self.message = g.toggle_pick(gid)
        self.app.sound.play("select" if not self.message else "blip")
        self.refresh()

    def starter(self):
        gid = self.table.current
        if gid is not None and gid in self.g.me.picks:
            self.message = self.g.toggle_starter(gid)
            self.refresh()

    def captain(self):
        gid = self.table.current
        if gid is not None and gid in self.g.me.picks:
            self.message = self.g.set_captain(gid)
            self.refresh()

    def handle(self, ev):
        if is_back(ev):
            autosave(self.app)
            self.app.pop()
            league = getattr(self.app, "league", None)
            if league and not league.commissioner and not self.g.t.complete:
                from .screens import BusyScene

                self.app.push(BusyScene(self.app, "Sending your lineup", league.submit_lineup))
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_s:
                self.starter()
                return
            if ev.key == pygame.K_c:
                self.captain()
                return
            if ev.key == pygame.K_a and not self.locked:
                self.g.auto_pick()
                self.message = "Your caddie has filled the gaps with the best available golfers."
                self.refresh()
                return
            if ev.key == pygame.K_m and not self.locked:
                self.mine_only = not self.mine_only
                self.table.index = 0
                self.refresh()
                return
            if ev.key == pygame.K_o:
                self.sort = (self.sort + 1) % len(SORTS)
                self.table.index = 0
                self.refresh()
                return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            # click a name in the "your team" panel to jump to him in the table
            x, y = ev.pos
            if x > 440 and TOP + 34 <= y < TOP + 34 + 6 * 16:
                i = (y - TOP - 34) // 16
                picks = self._panel_order()
                if i < len(picks):
                    for k, row in enumerate(self.table.rows):
                        if row[2] == picks[i]:
                            self.table.index = k
                            self.table._scroll()
                    return
        self.table.handle(ev)

    def _panel_order(self):
        me = self.g.me
        return sorted(me.picks, key=lambda p: (p != me.captain, p not in me.starters, self.g.golfers[p].owgr))

    # -------------------------------------------------------------- drawing
    def draw(self, surf):
        g = self.g
        me, ev, t = g.me, g.event, g.t
        T.frame(surf)
        title = "PICK YOUR TEAM" if not self.locked else f"LINEUP FOR ROUND {t.round_no + 1}"
        T.header(surf, f"{title} - {ev.short}", f"{data.SEGMENT_NAMES[ev.segment]}  -  field {len(t.field)}")
        sub = "Your six" if self.mine_only else f"The field, by {SORTS[self.sort][0].lower()}"
        T.text(surf, sub, (L, TOP), T.CYAN)
        T.text(surf, "Left = starts left", (L + 400, TOP), T.LIGHT_GREY, size=11, right=True)
        self.table.draw(surf)

        # your team panel
        x = 446
        pygame.draw.rect(surf, T.BLACK, (x - 6, TOP, R - x + 10, 200))
        T.text(surf, f"YOUR TEAM {len(me.picks)}/{data.ROSTER_SIZE}", (x, TOP + 4), T.YELLOW, bold=True)
        T.text(surf, "C=captain S=starter b=bench", (x, TOP + 19), T.LIGHT_GREY, size=10)
        y = TOP + 34
        for gid in self._panel_order():
            gf = g.golfers[gid]
            role = "C" if gid == me.captain else "S" if gid in me.starters else "b"
            col = T.YELLOW if role == "C" else T.WHITE if role == "S" else T.LIGHT_GREY
            T.text(surf, role, (x, y), col, bold=True)
            T.text(surf, fit(gf.name, 17), (x + 14, y), col)
            y += 16
        for _ in range(data.ROSTER_SIZE - len(me.picks)):
            T.text(surf, "-  (empty)", (x, y), T.DARK_GREY)
            y += 16
        problem = g.lineup_problem()
        y = TOP + 34 + 6 * 16 + 6
        if problem:
            for i, line in enumerate(T.wrap(problem, 24)[:3]):
                T.text(surf, line, (x, y + i * 13), T.LIGHT_RED, size=11)
        else:
            T.text(surf, "LINEUP READY", (x, y), T.LIGHT_GREEN, bold=True)
            if self.locked:
                T.text(surf, f"{me.event_total} pts so far", (x, y + 16), T.WHITE, size=11)

        # the highlighted golfer
        gid = self.table.current
        if gid is not None:
            gf = g.golfers[gid]
            y = TOP + 206
            T.text(surf, fit(gf.name, 24), (x - 4, y), T.CYAN, bold=True)
            T.text(surf, f"{data.TOUR_NAMES[gf.tour]}  {gf.country}", (x - 4, y + 15), T.LIGHT_GREY, size=11)
            s = gf.stats
            T.text(
                surf,
                f"{s['events']} ev  {s['wins']} W  {s['top10']} top-10",
                (x - 4, y + 28),
                T.WHITE,
                size=11,
            )
            T.text(surf, f"Form: {gf.form_label}", (x - 4, y + 41), T.form_colour(gf.form_label), size=11)
            if s["events"]:
                T.text(surf, f"Fantasy pts: {s['fantasy']}", (x + 84, y + 41), T.WHITE, size=11)

        if self.message:
            T.text(surf, fit(self.message, 88), (L, T.CANVAS_H - T.BORDER - 32), T.LIGHT_RED, size=11)
        if self.locked:
            hint = "RETURN/click: starter<->bench   C: captain   ESC: done"
        else:
            hint = (
                "RETURN/click: pick/drop  S: start/bench  C: captain  A: auto  M: my six  O: sort  ESC: done"
            )
        T.footer(surf, hint)

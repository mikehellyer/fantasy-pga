"""The tournament leaderboard and each golfer's hole-by-hole scorecard."""

from __future__ import annotations

import pygame

from ..core import data
from ..core.game import Game
from ..core.sim import course_holes, to_par
from . import theme as T
from .app import Scene
from .screens import TOP, L, R, fit, is_back
from .widgets import Table


class LeaderboardScene(Scene):
    def __init__(self, app, event_index: int | None = None):
        super().__init__(app)
        self.mine_only = False
        self.table = Table(
            [
                ("Pos", 26, "r"),
                ("Player", 34, "l"),
                ("", 210, "l"),
                ("R1", 270, "r"),
                ("R2", 300, "r"),
                ("R3", 330, "r"),
                ("R4", 360, "r"),
                ("Tot", 400, "r"),
                ("+/-", 452, "r"),
                ("Pts", 500, "r"),
                ("", 510, "l"),
            ],
            L,
            TOP + 16,
            590,
            visible=17,
            on_activate=self.open_card,
            sound=app.sound,
        )
        self.refresh()

    @property
    def g(self) -> Game:
        return self.app.game

    def refresh(self):
        g = self.g
        t = g.t
        me = g.me
        rows = []
        if t.round_no == 0:
            self.table.set_rows([])
            return
        active = set(t.active())
        for gid, pos, tot in t.leaderboard():
            if self.mine_only and gid not in me.picks:
                continue
            gf = g.golfers[gid]
            rounds = [str(t.round_strokes(gid, r)) for r in range(len(t.scores[gid]))]
            rounds += [""] * (4 - len(rounds))
            if gid not in active:
                pos = t.finish.get(gid) or ("WD" if gid in t.withdrawn else "MC")
            strokes = sum(t.round_strokes(gid, r) for r in range(len(t.scores[gid])))
            pts = sum(g.round_points(gid, r)["total"] for r in range(len(t.scores[gid])))
            mark = ""
            if gid in me.picks:
                mark = "C" if gid == me.captain else "S" if gid in me.starters else "b"
            colour = T.YELLOW if gid in me.picks else (T.WHITE if gid in active else T.GREY)
            rows.append(
                (
                    [pos, fit(gf.name, 22), gf.country, *rounds, str(strokes), to_par(tot), str(pts), mark],
                    colour,
                    gid,
                )
            )
        self.table.set_rows(rows)

    def open_card(self, gid):
        if gid is not None:
            self.app.push(ScorecardScene(self.app, gid))

    def handle(self, ev):
        if is_back(ev):
            self.app.pop()
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_m:
            self.mine_only = not self.mine_only
            self.table.index = 0
            self.refresh()
            return
        self.table.handle(ev)

    def draw(self, surf):
        g = self.g
        t, ev = g.t, g.event
        T.frame(surf)
        T.header(surf, f"LEADERBOARD - {ev.name.upper()}", g.status_label())
        if t.round_no == 0:
            T.text(surf, "The tournament hasn't started yet.", (T.CANVAS_W // 2, 150), T.WHITE, center=True)
        else:
            info = f"Par {ev.par}"
            if t.cut_score is not None:
                info += f"   Cut: {to_par(t.cut_score)} ({len(t.cut_made)} made it)"
            elif ev.cut == 0:
                info += "   No cut"
            if t.wind:
                info += "   Wind: " + " ".join(str(w) for w in t.wind)
            T.text(surf, info, (L, TOP), T.CYAN, size=11)
            if t.playoff:
                T.text(surf, fit(t.playoff[0], 50), (R, TOP), T.YELLOW, size=11, right=True)
            self.table.draw(surf)
        T.footer(surf, "RETURN: scorecard   M: only your golfers   Pts = fantasy points   ESC: back")


class ScorecardScene(Scene):
    def __init__(self, app, gid: int):
        super().__init__(app)
        self.gid = gid

    @property
    def g(self) -> Game:
        return self.app.game

    def handle(self, ev):
        if is_back(ev) or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN):
            self.app.pop()

    def draw(self, surf):
        g = self.g
        t, ev = g.t, g.event
        gf = g.golfers[self.gid]
        T.frame(surf)
        T.header(surf, f"SCORECARD - {gf.name.upper()}", f"{ev.short}  {data.TOUR_NAMES[gf.tour]}")
        holes = course_holes(ev)
        x0, y = L + 34, TOP + 8
        cw = 25
        T.text(surf, "Hole", (L, y), T.LIGHT_GREY, size=11)
        T.text(surf, "Par", (L, y + 14), T.LIGHT_GREY, size=11)
        for h, (par, _) in enumerate(holes):
            cx = x0 + h * cw + (8 if h >= 9 else 0)
            T.text(surf, str(h + 1), (cx + 10, y), T.LIGHT_GREY, size=11, center=True)
            T.text(surf, str(par), (cx + 10, y + 14), T.WHITE, size=11, center=True)
        T.text(surf, "Tot", (x0 + 18 * cw + 30, y), T.LIGHT_GREY, size=11, right=True)
        T.text(surf, "Pts", (x0 + 18 * cw + 70, y), T.LIGHT_GREY, size=11, right=True)
        y += 34
        me = g.me
        for r, card in enumerate(t.scores[self.gid]):
            T.text(surf, f"R{r + 1}", (L, y + 3), T.YELLOW)
            for h, (s, (par, _)) in enumerate(zip(card, holes)):
                cx = x0 + h * cw + (8 if h >= 9 else 0)
                strokes = par + s
                cell = pygame.Rect(cx, y, 21, 19)
                if s <= -2:
                    pygame.draw.circle(surf, T.YELLOW, cell.center, 10)
                    col = T.BLACK
                elif s == -1:
                    pygame.draw.circle(surf, T.LIGHT_RED, cell.center, 10, 2)
                    col = T.WHITE
                elif s == 1:
                    pygame.draw.rect(surf, T.LIGHT_BLUE, cell, 1)
                    col = T.WHITE
                elif s >= 2:
                    pygame.draw.rect(surf, T.LIGHT_BLUE, cell, 1)
                    pygame.draw.rect(surf, T.LIGHT_BLUE, cell.inflate(-4, -4), 1)
                    col = T.WHITE
                else:
                    col = T.LIGHT_GREY
                T.text(surf, str(strokes), (cell.centerx, y + 3), col, center=True)
            T.text(surf, str(t.round_strokes(self.gid, r)), (x0 + 18 * cw + 30, y + 3), T.WHITE, right=True)
            pts = g.round_points(self.gid, r)
            T.text(surf, str(pts["total"]), (x0 + 18 * cw + 70, y + 3), T.CYAN, right=True)
            y += 26
        if not t.scores[self.gid]:
            T.text(surf, "No rounds played yet.", (L, y), T.WHITE)
        # the points breakdown
        y = max(y + 6, TOP + 150)
        T.text(surf, "FANTASY POINTS", (L, y), T.YELLOW, bold=True)
        y += 16
        for r in range(len(t.scores[self.gid])):
            b = g.round_points(self.gid, r)
            parts = [f"holes {b['holes']}"]
            if b["streak"]:
                parts.append(f"birdie streak {b['streak']}")
            if b["bogey_free"]:
                parts.append(f"bogey-free {b['bogey_free']}")
            if b["finish"]:
                parts.append(f"finish bonus {b['finish']}")
            if b["under70"]:
                parts.append(f"all rounds under 70 {b['under70']}")
            role = ""
            if r < len(me.rounds) and self.gid in me.rounds[r]["starters"]:
                role = "  (your captain - doubled)" if me.rounds[r]["captain"] == self.gid else "  (started)"
            elif self.gid in me.picks:
                role = "  (on your bench)"
            T.text(
                surf, f"R{r + 1}: " + ", ".join(parts) + f" = {b['total']}{role}", (L, y), T.WHITE, size=11
            )
            y += 14
        pos = t.finish.get(self.gid)
        if pos:
            T.text(surf, f"Finished: {pos}", (L, y + 6), T.CYAN, bold=True)
        T.footer(surf, "Red circle birdie, yellow eagle, box bogey, double box double bogey+   ESC: back")

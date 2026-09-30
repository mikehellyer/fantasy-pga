"""Live scoring: watch a round unfold hole by hole, C64 style.

The round has already been played by the engine; this screen reveals it through
the day. Everyone starts at their tee time, and your golfers' big moments are
shown on the little hole view with the crowd reacting.
"""

from __future__ import annotations

import math
from collections import deque

import pygame

from ..core.game import Game
from ..core.scoring import hole_points
from ..core.sim import course_holes, score_word, to_par
from . import theme as T
from .app import Scene
from .screens import TOP, L, R, fit, ordinal

DAY_SECONDS = 45.0  # how long a round takes to watch at normal speed
FAST = 5.0
SPAN = 0.55  # share of the day each golfer takes to play 18 holes
SHOT_SECONDS = 2.0
WIND_WORDS = ["CALM", "BREEZY", "WINDY", "BLOWING A GALE"]


class LiveRoundScene(Scene):
    def __init__(self, app, report: dict):
        super().__init__(app)
        g = self.g
        self.report = report
        self.r = report["round"] - 1
        t = g.t
        self.holes = course_holes(g.event)
        self.players = [p for p in t.scores if len(t.scores[p]) > self.r]
        self.before = {p: t.total(p, self.r) for p in self.players}
        self.tee = t.tee[self.r]
        self.cards = {p: t.scores[p][self.r] for p in self.players}
        self.thru = dict.fromkeys(self.players, 0)
        lock = g.me.rounds[self.r]
        self.starters, self.captain = lock["starters"], lock["captain"]
        self.mine = [p for p in g.me.picks if p in self.cards]
        self.clock = 0.0
        self.fast = False
        self.done = False
        self.ticker: deque = deque(maxlen=4)
        self.shots: deque = deque(maxlen=2)
        self.shot = None  # (golfer, hole, score, started)
        self.leader = None
        self.flash = 0.0
        self.t = 0.0
        wind = t.wind[self.r]
        self.ticker.append((f"Round {self.r + 1} under way. Wind: {WIND_WORDS[wind].lower()}.", T.LIGHT_GREY))

    @property
    def g(self) -> Game:
        return self.app.game

    def on_enter(self):
        self.app.sound.play("crowd", loops=-1, volume=0.25)

    def _leave(self):
        self.app.sound.stop("crowd", 400)
        self.app.pop()
        if "result" in self.report:
            from .results import EventResultScene

            self.app.push(EventResultScene(self.app))

    # -------------------------------------------------------------- the clock
    def live_total(self, p: int) -> int:
        return self.before[p] + sum(self.cards[p][: self.thru[p]])

    def _advance(self, announce=True):
        for p in self.players:
            n = max(0, min(18, int((self.clock - self.tee[p]) / SPAN * 18)))
            while self.thru[p] < n:
                h = self.thru[p]
                self.thru[p] += 1
                if announce:
                    self._hole_event(p, h, self.cards[p][h])
        if announce:
            self._check_leader()

    def _hole_event(self, p: int, h: int, s: int):
        g = self.g
        name = g.golfers[p].surname.upper()
        par = self.holes[h][0]
        word = score_word(s, par)
        sound = self.app.sound
        if p in self.mine:
            if s < 0:
                self.ticker.append((f"{name} {word} AT THE {ordinal(h + 1)}!", T.LIGHT_GREEN))
                sound.play("roar" if s <= -2 else "applause", volume=0.8)
                if p in self.starters:
                    self.shots.append((p, h, s))
            elif s > 0:
                self.ticker.append((f"{name} {word} at the {ordinal(h + 1)}", T.LIGHT_RED))
                sound.play("ooh", volume=0.6)
        elif s == -2 and par == 3:
            self.ticker.append(
                (f"HOLE-IN-ONE! {g.golfers[p].name.upper()} ACES THE {ordinal(h + 1)}!", T.YELLOW)
            )
            sound.play("roar")
            self.shots.append((p, h, s))
            self.flash = 1.0
        elif s <= -2:
            self.ticker.append((f"{name} makes {word.lower()} at the {ordinal(h + 1)}", T.CYAN))
            sound.play("polite", volume=0.6)

    def _check_leader(self):
        started = [p for p in self.players if self.thru[p] > 0]
        if not started:
            return
        best = min(started, key=self.live_total)
        low = self.live_total(best)
        leaders = [p for p in started if self.live_total(p) == low]
        if self.leader not in leaders:
            self.leader = best
            if len(leaders) == 1:
                gf = self.g.golfers[best]
                self.ticker.append((f"{gf.name} takes the lead at {to_par(low)}", T.YELLOW))

    def skip(self):
        self.clock = 1.0
        self._advance(announce=False)
        self.shot = None
        self.shots.clear()
        self._finish()

    def _finish(self):
        if not self.done:
            self.done = True
            self.app.sound.play("applause")

    # -------------------------------------------------------------- loop
    def handle(self, ev):
        if self.done:
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self._leave()
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_SPACE:
                self.fast = not self.fast
            elif ev.key == pygame.K_ESCAPE:
                self.skip()
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 3:
                self.skip()
            else:
                self.fast = not self.fast

    def update(self, dt):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        if self.done:
            return
        # your golfers' big moments are shown one at a time on the hole view
        if self.shot is None and self.shots:
            p, h, s = self.shots.popleft()
            self.shot = (p, h, s, self.t)
            if s < 0:
                self.app.sound.play("swing", volume=0.7)
        if self.shot and self.t - self.shot[3] > SHOT_SECONDS / (2 if self.fast else 1):
            self.shot = None
        self.clock += dt / DAY_SECONDS * (FAST if self.fast else 1.0)
        self._advance()
        if (
            self.clock >= 1.0
            and all(v == 18 for v in self.thru.values())
            and not self.shots
            and not self.shot
        ):
            self._finish()

    # -------------------------------------------------------------- drawing
    def draw(self, surf):
        g = self.g
        ev, t = g.event, g.t
        T.frame(surf, T.GREEN if self.flash <= 0 else T.YELLOW)
        minutes = int(7 * 60 + min(1.0, self.clock) * 12.5 * 60)
        T.header(
            surf,
            f"ROUND {self.r + 1} - {ev.name.upper()}",
            f"WIND: {WIND_WORDS[t.wind[self.r]]}   {minutes // 60:02d}:{minutes % 60:02d}",
        )
        self._draw_board(surf)
        self._draw_team(surf)
        self._draw_hole(surf)
        # ticker
        y = T.CANVAS_H - T.BORDER - 16 - 4 * 13 - 4
        pygame.draw.rect(surf, T.BLACK, (T.BORDER, y - 2, T.CANVAS_W - 2 * T.BORDER, 4 * 13 + 4))
        for i, (line, col) in enumerate(self.ticker):
            T.text(surf, fit(line, 86), (L, y + i * 13), col, size=11)
        if self.done:
            self._draw_summary(surf)
            T.footer(surf, "Press any key to continue")
        else:
            T.footer(
                surf,
                "SPACE/click: fast forward " + ("(ON)" if self.fast else "(off)") + "   ESC: skip to the end",
            )

    def _draw_board(self, surf):
        g = self.g
        x, y = L, TOP
        pygame.draw.rect(surf, T.WHITE, (x - 4, y - 2, 262, 15 * 13 + 22))
        pygame.draw.rect(surf, T.GREEN, (x - 4, y - 2, 262, 16))
        T.text(surf, "LEADERS", (x + 2, y), T.WHITE, bold=True)
        T.text(surf, "TOT  THRU", (x + 252, y), T.WHITE, right=True)
        order = sorted(self.players, key=lambda p: (self.live_total(p), -self.thru[p]))
        totals = [self.live_total(p) for p in order]
        y += 18
        for i, p in enumerate(order[:15]):
            tot = totals[i]
            pos = totals.index(tot) + 1
            tied = totals.count(tot) > 1
            gf = g.golfers[p]
            col = T.BLUE if p in self.mine else T.BLACK
            T.text(surf, f"{'T' if tied else ''}{pos}", (x + 24, y), T.BLACK, size=11, right=True)
            T.text(surf, fit(gf.short.upper(), 18), (x + 30, y), col, size=11, bold=p in self.mine)
            T.text(
                surf, to_par(tot), (x + 212, y), (200, 30, 30) if tot < 0 else T.BLACK, size=11, right=True
            )
            th = self.thru[p]
            thru = "F" if th == 18 else str(th) if th else "-"
            T.text(surf, thru, (x + 252, y), T.BLACK, size=11, right=True)
            y += 13

    def _draw_team(self, surf):
        g = self.g
        x, y = 290, TOP
        pygame.draw.rect(surf, T.BLACK, (x - 4, y - 2, R - x + 8, 118))
        T.text(surf, "YOUR TEAM", (x, y), T.YELLOW, bold=True)
        T.text(surf, "TODAY THRU  PTS", (R, y), T.LIGHT_GREY, size=11, right=True)
        y += 16
        total = 0
        for p in sorted(self.mine, key=lambda p: (p != self.captain, p not in self.starters)):
            gf = g.golfers[p]
            role = "C" if p == self.captain else "S" if p in self.starters else "b"
            played = self.cards[p][: self.thru[p]]
            today = sum(played)
            pts = sum(hole_points(s, par) for s, (par, _) in zip(played, self.holes))
            if self.thru[p] == 18 or self.done:
                pts = g.round_points(p, self.r)["total"]
            if p == self.captain:
                pts *= 2
            if p in self.starters:
                total += pts
            col = T.YELLOW if role == "C" else T.WHITE if role == "S" else T.GREY
            T.text(surf, role, (x, y), col, bold=True)
            T.text(surf, fit(gf.name, 18), (x + 14, y), col, size=11)
            if self.thru[p]:
                T.text(surf, to_par(today), (R - 84, y), T.score_colour(today, col), size=11, right=True)
                th = self.thru[p]
                T.text(surf, "F" if th == 18 else str(th), (R - 48, y), col, size=11, right=True)
            else:
                start = int(7 * 60 + self.tee[p] * 12.5 * 60)
                T.text(surf, f"{start // 60:02d}:{start % 60:02d}", (R - 48, y), T.GREY, size=11, right=True)
            T.text(surf, str(pts), (R, y), T.CYAN if p in self.starters else T.GREY, size=11, right=True)
            y += 14
        T.text(surf, f"ROUND POINTS: {total}", (x, TOP + 102), T.LIGHT_GREEN, bold=True)

    def _draw_hole(self, surf):
        """A little side-on view of the hole for your starters' birdies and eagles."""
        x, y, w, h = 290, TOP + 124, R - 290 + 4, 96
        pygame.draw.rect(surf, T.CYAN, (x - 4, y, w, h))  # sky
        pygame.draw.rect(surf, T.GREEN, (x - 4, y + h - 30, w, 30))  # rough
        pygame.draw.rect(surf, T.LIGHT_GREEN, (x + 10, y + h - 26, w - 30, 8))  # fairway
        gx = x + w - 60  # the green and the flag
        pygame.draw.ellipse(surf, T.LIGHT_GREEN, (gx - 30, y + h - 28, 60, 10))
        pygame.draw.ellipse(surf, T.BLACK, (gx - 3, y + h - 25, 6, 3))
        pygame.draw.line(surf, T.WHITE, (gx, y + h - 24), (gx, y + h - 60))
        wave = int(math.sin(self.t * 6) * 2)
        pygame.draw.polygon(
            surf, (220, 40, 40), [(gx, y + h - 60), (gx + 14, y + h - 55 + wave), (gx, y + h - 50)]
        )
        # a tree or two
        for tx in (x + 30, x + 60):
            pygame.draw.rect(surf, T.BROWN, (tx, y + h - 44, 3, 16))
            pygame.draw.circle(surf, T.GREEN, (tx + 1, y + h - 48), 8)
        if not self.shot:
            T.text(surf, "YOUR GOLFERS' BIG MOMENTS", (x + w // 2 - 4, y + 6), T.BLUE, size=11, center=True)
            return
        p, hole, s, started = self.shot
        par = self.holes[hole][0]
        k = min(1.0, (self.t - started) / (SHOT_SECONDS * (0.5 if self.fast else 1)) * 1.4)
        gf = self.g.golfers[p]
        T.text(surf, f"{gf.surname.upper()}  -  HOLE {hole + 1}  PAR {par}", (x + 2, y + 4), T.BLUE, size=11)
        ground = y + h - 24
        sx = x + 20 if (par == 3 or s <= -2) else x + w // 2 - 20
        if s < 0:
            end = gx + (0 if k >= 0.99 else 6)
        else:
            end = gx + 26  # misses the green
        if k < 0.7:  # flight
            f = k / 0.7
            bx = sx + (end + 10 - sx) * f
            by = ground - math.sin(f * math.pi) * 40
        else:  # land and roll
            f = (k - 0.7) / 0.3
            bx = end + 10 - 10 * f
            by = ground
        if s < 0 and k >= 1.0:
            by = ground + 2  # in the hole
        pygame.draw.circle(surf, T.WHITE, (int(bx), int(by) - 2), 2)
        if k >= 0.7:
            word = score_word(s, par) + ("!" if s < 0 else "")
            col = (220, 40, 40) if s < 0 else T.BLUE
            T.big_text(
                surf, word, (x + w // 2 - 4, y + 22), col, scale=2, size=11, center=True, shadow=T.WHITE
            )

    def _draw_summary(self, surf):
        g = self.g
        t = g.t
        me = g.me
        lines = []
        lead = t.leaderboard()[0] if not t.complete else None
        if t.complete:
            lines.append(f"{g.golfers[t.winner].name} wins at {to_par(t.total(t.winner))}!")
        else:
            lines.append(f"Leader: {g.golfers[lead[0]].name} {to_par(lead[2])}")
        pts = me.rounds[self.r]["total"]
        lines.append(f"Your team scored {pts} points this round ({me.event_total} this week).")
        others = sorted(g.teams, key=lambda tm: -tm.event_total)
        lines.append(f"You're {ordinal(others.index(me) + 1)} of 12 in the league this week.")
        if self.r == 1 and t.cut_score is not None:
            lines.append(
                f"The cut fell at {to_par(t.cut_score)}: {len(t.cut_made)} golfers play the weekend."
            )
            gone = [g.golfers[p].surname for p in me.picks if p not in t.cut_made]
            if gone:
                lines.append("Missed the cut: " + ", ".join(gone))
        for p in self.report.get("withdrawn", []):
            lines.append(f"{g.golfers[p].name} has withdrawn injured.")
        lines += self.report.get("notes", [])
        wrapped = []
        for line in lines:
            wrapped += T.wrap(line, 50)
        box = pygame.Rect(T.CANVAS_W // 2 - 220, 120, 440, 50 + 15 * len(wrapped))
        pygame.draw.rect(surf, T.BLACK, box.move(4, 4))
        pygame.draw.rect(surf, T.BLUE, box)
        pygame.draw.rect(surf, T.YELLOW, box, 2)
        title = "FINAL ROUND COMPLETE" if t.complete else f"ROUND {self.r + 1} COMPLETE"
        T.text(surf, title, (box.centerx, box.y + 10), T.YELLOW, bold=True, center=True)
        for i, line in enumerate(wrapped):
            T.text(surf, line, (box.x + 16, box.y + 32 + i * 15), T.WHITE)

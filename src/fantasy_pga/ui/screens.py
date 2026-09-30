"""Shared screen bits: layout constants, message boxes, and the new-game screen."""

from __future__ import annotations

import webbrowser

import pygame

from ..core.game import Game, save_path
from . import theme as T
from .app import Scene
from .widgets import Menu, TextInput

L = T.BORDER + 10  # left margin
TOP = T.BORDER + 30
R = T.CANVAS_W - T.BORDER - 10  # right margin


def is_back(ev) -> bool:
    return (ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE)) or (
        ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3
    )


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def open_update(app):
    """Only runs when the player chooses Update: fetch this platform's installer in the
    browser (or open the release page if there's no installer for this system)."""
    info = app.update_info or {}
    target = info.get("download") or info.get("url")
    if target:
        webbrowser.open(target)


def autosave(app):
    league = getattr(app, "league", None)
    if league is not None:  # online games are kept in the league's own file
        try:
            league._save_cache()
        except OSError:
            pass
        return
    try:
        app.game.save(save_path())
    except OSError:
        pass  # a failed autosave shouldn't stop play; "Save Game" reports errors


def fit(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "."


class MessageScene(Scene):
    """Modal message box. Optional yes/no."""

    def __init__(
        self, app, title, lines, on_yes=None, on_no=None, yes_label="Yes", no_label="No", on_close=None
    ):
        super().__init__(app)
        self.title, self.lines = title, []
        for line in lines:
            self.lines += T.wrap(line, 52) or [""]
        self.on_yes, self.on_no, self.on_close = on_yes, on_no, on_close
        self.under = app.scenes[-1] if app.scenes else None
        h = 64 + len(self.lines) * 15 + (40 if on_yes else 0)
        self.rect = pygame.Rect(T.CANVAS_W // 2 - 230, T.CANVAS_H // 2 - h // 2, 460, h)
        self.menu = None
        if on_yes:
            w = max(160, 8 * max(len(yes_label), len(no_label)) + 50)
            self.menu = Menu(
                [(f"{yes_label} (Y)", self._yes), (f"{no_label} (N)", self._no)],
                self.rect.centerx - w // 2,
                self.rect.bottom - 48,
                w=w,
                sound=app.sound,
                numbered=False,
            )

    def _yes(self):
        self.app.pop()
        self.on_yes()

    def _no(self):
        self.app.pop()
        if self.on_no:
            self.on_no()

    def handle(self, ev):
        if self.menu:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_y:
                self._yes()
            elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_n, pygame.K_ESCAPE):
                self._no()
            else:
                self.menu.handle(ev)
        elif ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.pop()
            if self.on_close:
                self.on_close()

    def draw(self, surf):
        if self.under:
            self.under.draw(surf)
        r = self.rect
        pygame.draw.rect(surf, T.BLACK, r.move(4, 4))
        pygame.draw.rect(surf, T.BLUE, r)
        pygame.draw.rect(surf, T.YELLOW, r, 2)
        T.text(surf, self.title, (r.centerx, r.y + 10), T.YELLOW, bold=True, center=True)
        for i, line in enumerate(self.lines):
            T.text(surf, line, (r.x + 16, r.y + 34 + i * 15), T.WHITE)
        if self.menu:
            self.menu.draw(surf)
        else:
            T.text(surf, "Press any key", (r.centerx, r.bottom - 20), T.LIGHT_GREY, size=11, center=True)


class BusyScene(Scene):
    """Shows 'CONNECTING...' while fn() talks to the league server, then hands over
    to on_done(result). A connection problem is shown as a message."""

    def __init__(self, app, label, fn, on_done=None, on_error=None):
        super().__init__(app)
        self.label, self.fn, self.on_done, self.on_error = label, fn, on_done, on_error
        self.under = app.scenes[-1] if app.scenes else None
        self.frames = 0

    def update(self, dt):
        from ..core.game import LineupError
        from ..core.online import OnlineError

        self.frames += 1
        if self.frames != 3:  # let "CONNECTING" appear on screen first
            return
        try:
            result = self.fn()
        except (OnlineError, LineupError, OSError) as exc:
            self.app.pop()
            if self.on_error:
                self.on_error(exc)
            else:
                self.app.push(MessageScene(self.app, "LEAGUE SERVER PROBLEM", [str(exc)]))
            return
        self.app.pop()
        if self.on_done:
            self.on_done(result)

    def draw(self, surf):
        if self.under:
            self.under.draw(surf)
        r = pygame.Rect(T.CANVAS_W // 2 - 150, T.CANVAS_H // 2 - 24, 300, 48)
        pygame.draw.rect(surf, T.BLACK, r.move(4, 4))
        pygame.draw.rect(surf, T.BLUE, r)
        pygame.draw.rect(surf, T.CYAN, r, 2)
        dots = "." * (1 + (pygame.time.get_ticks() // 300) % 3)
        T.text(surf, self.label.upper() + dots, (r.centerx, r.y + 16), T.WHITE, bold=True, center=True)


# --------------------------------------------------------------------------- new game
class NewGameScene(Scene):
    PROMPTS = ["What's your name, manager?", "And what's your fantasy team called?"]

    def __init__(self, app):
        super().__init__(app)
        self.step = 0
        self.inputs = [TextInput(L + 150, 120, 260, "", 20), TextInput(L + 150, 120, 260, "", 22)]

    def handle(self, ev):
        if is_back(ev) and not (ev.type == pygame.KEYDOWN and ev.key == pygame.K_BACKSPACE):
            if self.step == 0:
                self.app.pop()
            else:
                self.step -= 1
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.app.sound.play("select")
            if self.step == 0:
                self.step = 1
                if not self.inputs[1].value:
                    name = self.inputs[0].value.strip().split(" ")[0] or "My"
                    self.inputs[1].value = f"{name}'s Tee Party"[:22]
            else:
                self.start()
            return
        self.inputs[self.step].handle(ev)

    def start(self):
        from .hub import HubScene

        game = Game.new(self.inputs[0].value.strip() or "Manager", self.inputs[1].value.strip() or "My Team")
        self.app.game = game
        autosave(self.app)
        self.app.reset(HubScene(self.app))
        self.app.push(
            MessageScene(
                self.app,
                f"WELCOME TO THE {game.season} SEASON",
                [
                    f"{game.me.name} have joined a private league with 11 rival managers.",
                    "",
                    "Every week pick SIX golfers from the real field. FOUR start each round "
                    "and score points; the other two sit on your bench. Your CAPTAIN scores double.",
                    "",
                    "You can start any golfer only THREE times in each of the three segments, "
                    "so save some of your stars for the majors!",
                    "",
                    "Between rounds you can swap starters and bench and change your captain.",
                ],
            )
        )

    def update(self, dt):
        self.inputs[self.step].update(dt)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, "NEW GAME", "FANTASY PGA")
        T.big_text(surf, "NEW SEASON", (T.CANVAS_W // 2, TOP + 10), T.YELLOW, 2, center=True, shadow=T.BLACK)
        T.text(surf, self.PROMPTS[self.step], (L + 150, 98), T.CYAN)
        self.inputs[self.step].draw(surf)
        if self.step == 1:
            T.text(surf, f"Manager: {self.inputs[0].value or 'Manager'}", (L + 150, 150), T.LIGHT_GREY)
        lines = [
            "Real golfers.  Real 2026 PGA TOUR schedule.  Every round played by the computer.",
            "32 tournaments in three segments, from Hawaii to the TOUR Championship.",
        ]
        for i, line in enumerate(lines):
            T.text(surf, line, (T.CANVAS_W // 2, 220 + i * 16), T.LIGHT_GREEN, center=True, size=11)
        T.footer(surf, "Type, then RETURN.   ESC: back")

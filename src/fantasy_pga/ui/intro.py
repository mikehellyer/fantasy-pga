"""Intro: a fake C64 boot/load sequence, then a demo-scene style title screen."""

from __future__ import annotations

import math
import random

import pygame

from .. import __version__
from ..core.game import Game, save_path
from . import theme as T
from .app import Scene
from .widgets import Menu

BOOT_LINES = [
    "",
    "    **** COMMODORE 64 BASIC V2 ****",
    "",
    " 64K RAM SYSTEM  38911 BASIC BYTES FREE",
    "",
    "READY.",
]


class BootScene(Scene):
    """READY. LOAD"FANTASY PGA",8,1 ... with flashing loading stripes."""

    CMD = 'LOAD"FANTASY PGA",8,1'

    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self.rng = random.Random()

    def handle(self, ev):
        if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.replace(TitleScene(self.app))

    def update(self, dt):
        self.t += dt
        if self.t > 6.2:
            self.app.replace(TitleScene(self.app))

    def draw(self, surf):
        t = self.t
        loading = 3.0 < t < 6.0
        if loading:
            # classic tape/disk loading stripes in the border
            surf.fill(T.BLACK)
            y = 0
            while y < T.CANVAS_H:
                h = self.rng.randint(2, 9)
                pygame.draw.rect(surf, self.rng.choice(T.PALETTE), (0, y, T.CANVAS_W, h))
                y += h
            pygame.draw.rect(surf, T.BLUE, (32, 28, T.CANVAS_W - 64, T.CANVAS_H - 56))
        else:
            T.frame(surf, T.LIGHT_BLUE, T.BLUE)
            pygame.draw.rect(surf, T.LIGHT_BLUE, (0, 0, T.CANVAS_W, 28))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (0, T.CANVAS_H - 28, T.CANVAS_W, 28))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (0, 0, 32, T.CANVAS_H))
            pygame.draw.rect(surf, T.LIGHT_BLUE, (T.CANVAS_W - 32, 0, 32, T.CANVAS_H))
        lines = list(BOOT_LINES)
        typed = int(max(0, t - 1.0) * 18)
        if t > 1.0:
            lines.append(self.CMD[:typed])
        if t > 2.4:
            lines += ["", "SEARCHING FOR FANTASY PGA"]
        if t > 3.0:
            lines += ["LOADING"]
        if t > 5.6:
            lines += ["READY.", "RUN"]
        for i, line in enumerate(lines):
            T.text(surf, line, (40, 34 + i * 14), T.LIGHT_BLUE)
        # blinking cursor
        if int(t * 2.5) % 2 == 0:
            cy = 34 + len(lines) * 14 - (14 if t > 1.0 and typed < len(self.CMD) + 4 else 0)
            cx = 40 + (T.font().size(lines[-1])[0] + 2 if t > 1.0 and typed < len(self.CMD) + 4 else 0)
            pygame.draw.rect(surf, T.LIGHT_BLUE, (cx, cy, 8, 13))


SCROLL_TEXT = (
    "*** WELCOME TO FANTASY PGA ***   FANTASY GOLF WITH THE REAL STARS OF THE TOUR ... "
    "PICK SIX GOLFERS EVERY WEEK, START FOUR, NAME YOUR CAPTAIN AND WATCH EVERY ROUND UNFOLD HOLE BY HOLE ... "
    "32 TOURNAMENTS FROM HAWAII TO EAST LAKE, WITH THE MASTERS, THE PGA, THE U.S. OPEN AND THE OPEN ... "
    "ONLY THREE STARTS PER GOLFER PER SEGMENT, SO SAVE YOUR STARS FOR THE BIG ONES ... "
    "CAN YOU BEAT ELEVEN RIVAL MANAGERS TO THE TITLE?   ...   PRESS SPACE OR CLICK TO TEE OFF   ...   "
)

RASTER_COLOURS = [
    [T.DARK_GREY, T.GREEN, T.LIGHT_GREEN, T.WHITE, T.LIGHT_GREEN, T.GREEN, T.DARK_GREY],
    [T.BROWN, T.ORANGE, T.YELLOW, T.WHITE, T.YELLOW, T.ORANGE, T.BROWN],
    [T.BLUE, T.LIGHT_BLUE, T.CYAN, T.WHITE, T.CYAN, T.LIGHT_BLUE, T.BLUE],
    [T.GREEN, T.LIGHT_GREEN, T.YELLOW, T.WHITE, T.YELLOW, T.LIGHT_GREEN, T.GREEN],
]
TITLE_CYCLE = [T.WHITE, T.YELLOW, T.LIGHT_GREEN, T.CYAN, T.LIGHT_BLUE, T.PURPLE, T.LIGHT_RED, T.ORANGE]


def _letter_images(word, scale, size=16):
    imgs = []
    for ch in word:
        base = T.font(size, True).render(ch, False, T.WHITE)
        imgs.append(pygame.transform.scale(base, (base.get_width() * scale, base.get_height() * scale)))
    return imgs


_tint_cache: dict = {}


def _tint(img, color):
    key = (id(img), color)
    if key not in _tint_cache:
        mask = pygame.mask.from_surface(img)
        _tint_cache[key] = mask.to_surface(setcolor=color, unsetcolor=(0, 0, 0, 0))
    return _tint_cache[key]


class TitleScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self.show_menu = False
        self.title1 = _letter_images("FANTASY", 4)
        self.title2 = _letter_images("PGA", 4)
        self.scroll_imgs = {}
        self.flag = self._make_flag()
        self.stars = [
            (random.randint(0, T.CANVAS_W), random.randint(0, T.CANVAS_H), random.choice([1, 2, 3]))
            for _ in range(70)
        ]
        self._build_menu()
        self.message = ""

    def _build_menu(self):
        has_save = save_path().exists()
        items = [
            ("New Game", self.new_game),
            ("Continue Saved Game", self.load_game, has_save),
            ("Online League", self.online),
            ("Quit", self.quit),
        ]
        info = self.app.update_info
        if info:
            items.insert(0, (f"UPDATE TO v{info['version']}", self.download_update, True, "alert"))
        self.menu = Menu(items, T.CANVAS_W // 2 - 110, 222 - (18 if info else 0), w=220, sound=self.app.sound)
        self._menu_has_update = bool(info)

    def download_update(self):
        from .screens import open_update

        open_update(self.app)

    def on_enter(self):
        self.app.sound.play("tune", loops=-1)

    def _make_flag(self):
        w, h = 44, 28
        s = pygame.Surface((w, h))
        s.fill((220, 40, 40))
        pygame.draw.rect(s, T.YELLOW, (0, 0, w, 4))
        pygame.draw.rect(s, T.YELLOW, (0, h - 4, w, 4))
        T.text(s, "18", (w // 2 - 7, h // 2 - 7), T.WHITE, bold=True)
        return s

    def new_game(self):
        from .screens import NewGameScene

        self.app.sound.stop("tune")
        self.app.push(NewGameScene(self.app))

    def online(self):
        from .online_ui import OnlineMenuScene

        self.app.sound.stop("tune")
        self.app.push(OnlineMenuScene(self.app))

    def load_game(self):
        from .hub import HubScene

        try:
            self.app.game = Game.load(save_path())
        except Exception as exc:  # corrupt or old save
            self.message = f"Can't load: {exc}"[:78]
            return
        self.app.sound.stop("tune")
        self.app.reset(HubScene(self.app))

    def quit(self):
        self.app.running = False

    def handle(self, ev):
        if not self.show_menu:
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                if getattr(ev, "key", None) == pygame.K_ESCAPE:
                    self.quit()
                    return
                self.show_menu = True
                self.app.sound.play("select")
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.show_menu = False
            return
        self.menu.handle(ev)

    def update(self, dt):
        self.t += dt
        if self.app.update_info and not self._menu_has_update:
            self._build_menu()  # the background update check has just found a new version

    def draw(self, surf):
        t = self.t
        surf.fill(T.BLACK)

        # starfield
        for x, y, sp in self.stars:
            xx = (x - t * 20 * sp) % T.CANVAS_W
            surf.set_at((int(xx), y), [T.DARK_GREY, T.GREY, T.WHITE][sp - 1])

        # rasterbars
        for i, cols in enumerate(RASTER_COLOURS):
            cy = 110 + math.sin(t * 1.7 + i * 0.9) * 70
            for j, c in enumerate(cols):
                pygame.draw.rect(surf, c, (0, int(cy) + j * 3, T.CANVAS_W, 3))

        # big bouncing title
        total = sum(img.get_width() for img in self.title1) + 8 * (len(self.title1) - 1)
        x = T.CANVAS_W // 2 - total // 2
        for i, img in enumerate(self.title1):
            y = 16 + math.sin(t * 3 + i * 0.7) * 5
            col = TITLE_CYCLE[int(t * 8 + i) % len(TITLE_CYCLE)]
            surf.blit(_tint(img, T.BLACK), (x + 4, y + 4))
            surf.blit(_tint(img, col), (x, y))
            x += img.get_width() + 8
        total = sum(img.get_width() for img in self.title2) + 4 * (len(self.title2) - 1)
        x = T.CANVAS_W // 2 - total // 2
        for i, img in enumerate(self.title2):
            y = 98 + math.sin(t * 3 + i * 0.5 + 2) * 3
            surf.blit(_tint(img, T.BLACK), (x + 3, y + 3))
            surf.blit(_tint(img, T.WHITE), (x, y))
            x += img.get_width() + 4

        T.text(
            surf,
            "FANTASY GOLF  -  THE REAL GOLFERS, PLAYED BY THE COMPUTER",
            (T.CANVAS_W // 2, 186),
            T.YELLOW,
            center=True,
        )

        # the 18th green with a waving pin flag
        gx, gy = 58, 272
        pygame.draw.ellipse(surf, T.GREEN, (gx - 50, gy - 12, 100, 24))
        pygame.draw.ellipse(surf, T.LIGHT_GREEN, (gx - 40, gy - 9, 80, 18))
        pygame.draw.ellipse(surf, T.BLACK, (gx - 4, gy - 2, 8, 4))
        pygame.draw.rect(surf, T.WHITE, (gx - 1, gy - 72, 2, 72))
        fx, fy = gx + 1, gy - 72
        for col in range(self.flag.get_width()):
            dy = math.sin(t * 5 - col * 0.2) * (col * 0.09)
            surf.blit(self.flag, (fx + col, fy + dy), (col, 0, 1, self.flag.get_height()))

        # a golf ball chipped in from the right: flies, bounces, rolls, drops - again and again
        cycle = t % 5.0
        cx = T.CANVAS_W - 70
        if cycle < 1.6:  # in the air
            k = cycle / 1.6
            bx = cx - 40 * k
            by = 276 - math.sin(k * math.pi) * 70
        elif cycle < 2.4:  # a little bounce
            k = (cycle - 1.6) / 0.8
            bx = cx - 40 - 20 * k
            by = 276 - math.sin(k * math.pi) * 12
        else:  # sits there, spinning
            bx, by = cx - 60, 276
        pygame.draw.ellipse(surf, T.GREEN, (cx - 110, 278, 130, 10))
        pygame.draw.ellipse(surf, T.DARK_GREY, (bx - 5, 279, 10, 3))
        pygame.draw.circle(surf, T.WHITE, (int(bx), int(by)), 5)
        pygame.draw.circle(surf, T.LIGHT_GREY, (int(bx) + 1, int(by) + 1), 1)

        if self.show_menu:
            box = pygame.Rect(T.CANVAS_W // 2 - 124, self.menu.y - 10, 248, len(self.menu.items) * 18 + 14)
            pygame.draw.rect(surf, T.BLUE, box)
            pygame.draw.rect(surf, T.LIGHT_BLUE, box, 2)
            self.menu.draw(surf)
            if self.message:
                T.text(surf, self.message, (T.CANVAS_W // 2, 316), T.LIGHT_RED, center=True, size=11)
        elif int(t * 1.5) % 2 == 0:
            T.big_text(
                surf, "PRESS SPACE", (T.CANVAS_W // 2, 240), T.WHITE, scale=2, center=True, shadow=T.BLUE
            )

        # sine scroller
        self._draw_scroller(surf, t)
        T.text(surf, f"v{__version__}", (T.CANVAS_W - 6, 4), T.DARK_GREY, size=10, right=True)
        info = self.app.update_info
        if info and int(t * 2.5) % 2 == 0:  # flashing, so it can't be missed
            T.text(
                surf, f"NEW VERSION v{info['version']} AVAILABLE!", (6, 4), (230, 50, 50), size=11, bold=True
            )

    def _draw_scroller(self, surf, t):
        char_w = 16
        offset = t * 90
        start = int(offset // char_w)
        base_y = 322
        for i in range(T.CANVAS_W // char_w + 2):
            ch = SCROLL_TEXT[(start + i) % len(SCROLL_TEXT)]
            if ch not in self.scroll_imgs:
                img = T.font(13, True).render(ch, False, T.WHITE)
                self.scroll_imgs[ch] = pygame.transform.scale(
                    img, (img.get_width() * 2, img.get_height() * 2)
                )
            x = i * char_w - offset % char_w
            y = base_y + math.sin(t * 4 + x * 0.03) * 8
            col = TITLE_CYCLE[int(x / 40 + t * 4) % len(TITLE_CYCLE)]
            surf.blit(_tint(self.scroll_imgs[ch], col), (x, y))

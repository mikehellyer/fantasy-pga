"""Online league screens: your leagues, creating and joining one, and the lobby."""

from __future__ import annotations

import pygame

from ..core import online
from ..core.online import League
from . import theme as T
from .app import Scene
from .screens import TOP, BusyScene, L, MessageScene, R, fit, is_back
from .widgets import Menu, TextInput

POLL_SECONDS = 8.0


def enter_league(app, league: League):
    """Open a league: the lobby if it hasn't started, otherwise the main menu."""
    from .hub import HubScene

    app.league = league
    if league.game is None:
        app.push(LobbyScene(app, league))
        return
    app.game = league.game
    app.reset(HubScene(app))


class OnlineMenuScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.backend = online.default_backend()
        self.build()

    def build(self):
        self.profiles = online.load_profiles()
        items = []
        for p in self.profiles:
            role = " (commissioner)" if p.get("commissioner") else ""
            items.append((fit(f"{p['code']}  {p['name']}{role}", 40), lambda p=p: self.open(p)))
        items += [
            ("Create a new league", lambda: self.app.push(CreateLeagueScene(self.app, self.backend))),
            ("Join a league with a code", lambda: self.app.push(JoinLeagueScene(self.app, self.backend))),
            ("Back", self.app.pop),
        ]
        self.menu = Menu(items, L + 60, TOP + 60, w=440, line_h=19, sound=self.app.sound)

    def on_enter(self):
        self.build()

    def open(self, profile):
        league = League(self.backend, profile)

        def done(_):
            enter_league(self.app, league)

        def offline(exc):
            if league.game is not None:  # play on with the copy saved on this computer
                enter_league(self.app, league)
                self.app.push(
                    MessageScene(self.app, "WORKING OFFLINE", [str(exc), "", "Showing your last saved copy."])
                )
            else:
                self.app.push(MessageScene(self.app, "LEAGUE SERVER PROBLEM", [str(exc)]))

        self.app.push(BusyScene(self.app, "Connecting", league.sync, done, offline))

    def forget(self):
        i = self.menu.index
        if i >= len(self.profiles):
            return
        p = self.profiles[i]

        def yes():
            online.forget(p["code"])
            self.build()

        self.app.push(
            MessageScene(
                self.app,
                f"REMOVE {p['code']}?",
                [
                    f"Remove '{p['name']}' from this computer?",
                    "(The league itself carries on for everyone else.)",
                ],
                on_yes=yes,
            )
        )

    def handle(self, ev):
        if self.backend is None:
            if is_back(ev) or ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self.app.pop()
            return
        if is_back(ev):
            self.app.pop()
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_d, pygame.K_DELETE):
            self.forget()
            return
        self.menu.handle(ev)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, "ONLINE LEAGUES", "play with your friends")
        if self.backend is None:
            T.text(
                surf,
                "Online play isn't set up in this version yet.",
                (T.CANVAS_W // 2, 140),
                T.LIGHT_RED,
                center=True,
            )
            T.footer(surf, "Press any key")
            return
        T.text(
            surf,
            "Everyone picks their team on their own computer. The commissioner",
            (L, TOP),
            T.WHITE,
            size=11,
        )
        T.text(
            surf,
            "plays each round when the lineups are in, and everyone watches it.",
            (L, TOP + 14),
            T.WHITE,
            size=11,
        )
        if self.profiles:
            T.text(surf, "YOUR LEAGUES", (L + 60, TOP + 42), T.YELLOW, bold=True)
        self.menu.draw(surf)
        T.footer(surf, "RETURN: open   D: remove a league from this computer   ESC: back")


class _NameForm(Scene):
    """Asks a few questions one at a time."""

    TITLE = ""
    FIELDS: list[tuple[str, int]] = []

    def __init__(self, app, backend):
        super().__init__(app)
        self.backend = backend
        self.step = 0
        self.inputs = [TextInput(L + 150, 130, 260, "", n) for _, n in self.FIELDS]
        self.message = ""

    def handle(self, ev):
        if is_back(ev) and not (ev.type == pygame.KEYDOWN and ev.key == pygame.K_BACKSPACE):
            if self.step == 0:
                self.app.pop()
            else:
                self.step -= 1
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if not self.inputs[self.step].value.strip():
                self.message = "Please type something first."
                return
            self.message = ""
            self.app.sound.play("select")
            if self.step < len(self.FIELDS) - 1:
                self.step += 1
            else:
                self.submit([i.value.strip() for i in self.inputs])
            return
        self.inputs[self.step].handle(ev)

    def submit(self, values):
        raise NotImplementedError

    def update(self, dt):
        self.inputs[self.step].update(dt)

    def draw(self, surf):
        T.frame(surf)
        T.header(surf, self.TITLE, f"step {self.step + 1} of {len(self.FIELDS)}")
        T.text(surf, self.FIELDS[self.step][0], (L + 150, 108), T.CYAN)
        self.inputs[self.step].draw(surf)
        for i in range(self.step):
            T.text(
                surf,
                f"{self.FIELDS[i][0].split('?')[0]}? {self.inputs[i].value}",
                (L + 150, 170 + i * 14),
                T.LIGHT_GREY,
                size=11,
            )
        if self.message:
            T.text(surf, self.message, (L + 150, 240), T.LIGHT_RED, size=11)
        T.footer(surf, "Type, then RETURN.   ESC: back")


class CreateLeagueScene(_NameForm):
    TITLE = "CREATE A LEAGUE"
    FIELDS = [("What's your name?", 20), ("What's your team called?", 22), ("What's the league called?", 24)]

    def submit(self, values):
        manager, team, name = values

        def create():
            return League.create(self.backend, name, manager, team)

        def done(league):
            self.app.pop()
            enter_league(self.app, league)

        self.app.push(BusyScene(self.app, "Creating the league", create, done))


class JoinLeagueScene(_NameForm):
    TITLE = "JOIN A LEAGUE"
    FIELDS = [("What's the league code?", 6), ("What's your name?", 20), ("What's your team called?", 22)]

    def submit(self, values):
        code, manager, team = values

        def join():
            return League.join(self.backend, code, manager, team)

        def done(league):
            self.app.pop()
            enter_league(self.app, league)

        self.app.push(BusyScene(self.app, "Joining", join, done))


class LobbyScene(Scene):
    """Before the season: share the code, watch friends join, and (commissioner) start."""

    def __init__(self, app, league: League):
        super().__init__(app)
        self.league = league
        self.timer = POLL_SECONDS  # check straight away
        self.checking = False
        players = len(league.info.get("players", [])) or 1
        self.ai = 12 - players
        self.build()

    def build(self):
        items = []
        if self.league.commissioner:
            items.append(("Start the season!", self.start))
            items.append((f"Computer managers: {self.ai}  < >", self._more_ai))
        items.append(("Back", self.back))
        self.menu = Menu(items, L + 330, TOP + 150, w=250, line_h=19, sound=self.app.sound, numbered=False)

    def _more_ai(self):
        most = 12 - len(self.league.info.get("players", []))
        self.ai = 0 if self.ai >= most else self.ai + 1
        self._relabel()

    def _relabel(self):
        if self.league.commissioner:
            self.menu.items[1][0] = f"Computer managers: {self.ai}  < >"

    def back(self):
        self.app.league = None
        self.app.pop()

    def start(self):
        league = self.league
        n = len(league.info.get("players", []))
        if n < 2:
            self.app.push(
                MessageScene(
                    self.app,
                    "NO FRIENDS YET",
                    [
                        "Nobody else has joined yet. Start anyway?",
                        "(No one can join once the season starts.)",
                    ],
                    on_yes=self._start,
                )
            )
            return
        self._start()

    def _start(self):
        def go():
            self.league.start_season(max(0, min(self.ai, 12 - len(self.league.info.get("players", [])))))

        def done(_):
            self.app.pop()
            enter_league(self.app, self.league)

        self.app.push(BusyScene(self.app, "Starting the season", go, done))

    def handle(self, ev):
        if is_back(ev):
            self.back()
            return
        if (
            ev.type == pygame.KEYDOWN
            and ev.key in (pygame.K_LEFT, pygame.K_RIGHT)
            and self.league.commissioner
        ):
            most = 12 - len(self.league.info.get("players", []))
            self.ai = max(0, min(most, self.ai + (1 if ev.key == pygame.K_RIGHT else -1)))
            self._relabel()
            self.app.sound.play("blip")
            return
        self.menu.handle(ev)

    def update(self, dt):
        league = self.league
        self.timer += dt
        if self.timer >= POLL_SECONDS and not league._polling:
            self.timer = 0
            league.poll_async()
        if league.take_update() and self.app.scene is self:
            self.app.pop()
            enter_league(self.app, league)
        most = 12 - len(league.info.get("players", []))
        if self.ai > max(0, most):
            self.ai = max(0, most)
            self._relabel()

    def draw(self, surf):
        league = self.league
        T.frame(surf)
        T.header(surf, f"LEAGUE LOBBY - {league.profile['name'].upper()}", "waiting to tee off")
        T.text(surf, "Give your friends this code:", (L, TOP), T.WHITE)
        T.big_text(surf, league.code, (L + 10, TOP + 18), T.YELLOW, scale=4, shadow=T.BLACK)
        T.text(
            surf,
            "They choose Online League > Join a league with a code.",
            (L, TOP + 84),
            T.LIGHT_GREY,
            size=11,
        )
        y = TOP + 108
        players = league.info.get("players", [])
        T.text(surf, f"MANAGERS ({len(players)}/12)", (L, y), T.YELLOW, bold=True)
        y += 16
        for p in players[:12]:
            tag = "  (commissioner)" if p["player_id"] == 0 else ""
            col = T.CYAN if p["player_id"] == league.profile["player_id"] else T.WHITE
            T.text(surf, fit(f"{p['manager']} - {p['team']}{tag}", 44), (L, y), col, size=11)
            y += 13
        if league.commissioner:
            T.text(surf, "Computer managers fill the", (L + 330, TOP + 110), T.CYAN, size=11)
            T.text(surf, "empty places (up to 12 teams)", (L + 330, TOP + 124), T.CYAN, size=11)
        else:
            T.text(surf, "Waiting for the commissioner", (L + 330, TOP + 110), T.CYAN, size=11)
            T.text(surf, "to start the season...", (L + 330, TOP + 124), T.CYAN, size=11)
        if league.poll_error:
            T.text(surf, fit(league.poll_error, 86), (L, T.CANVAS_H - T.BORDER - 32), T.LIGHT_RED, size=11)
        self.menu.draw(surf)
        T.footer(surf, "The list updates by itself.   ESC: back")


class LeagueInfoScene(Scene):
    """The league code and who has sent in a lineup for the next round."""

    def __init__(self, app):
        super().__init__(app)

    def handle(self, ev):
        if is_back(ev) or ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.pop()

    def draw(self, surf):
        league = self.app.league
        g = self.app.game
        T.frame(surf)
        T.header(surf, f"{league.profile['name'].upper()}", f"code {league.code}")
        y = TOP
        T.text(
            surf,
            f"Next: {g.event.name}, " + ("round 1" if g.t.round_no == 0 else f"round {g.t.round_no + 1}"),
            (L, y),
            T.CYAN,
        )
        y += 20
        sent = league.submitted() if not g.t.complete else {}
        T.text(surf, "MANAGER", (L, y), T.YELLOW, bold=True)
        T.text(surf, "LINEUP FOR THE NEXT ROUND", (R, y), T.YELLOW, bold=True, right=True)
        y += 16
        for t in g.teams:
            if not t.human:
                continue
            boss = "  (commissioner)" if t.player_id == 0 else ""
            T.text(surf, fit(f"{t.manager} - {t.name}{boss}", 50), (L, y), T.WHITE, size=11)
            if g.t.complete:
                status, col = "-", T.GREY
            elif t.player_id == 0:
                status, col = "on the commissioner's computer", T.LIGHT_GREY
            elif sent.get(t.player_id):
                status, col = "SENT", T.LIGHT_GREEN
            else:
                status, col = "not yet", T.LIGHT_RED
            T.text(surf, status, (R, y), col, size=11, right=True)
            y += 14
        ai = sum(1 for t in g.teams if not t.human)
        if ai:
            T.text(surf, f"Plus {ai} computer managers.", (L, y + 8), T.LIGHT_GREY, size=11)
        T.text(
            surf,
            "Friends who don't send a lineup get their caddie's picks before round 1,",
            (L, y + 34),
            T.WHITE,
            size=11,
        )
        T.text(surf, "or keep the lineup they had between rounds.", (L, y + 48), T.WHITE, size=11)
        if league.unsynced:
            T.text(
                surf,
                "Your last round hasn't reached the server yet - use Sync Now.",
                (L, y + 74),
                T.LIGHT_RED,
                size=11,
            )
        T.footer(surf, "Press any key")

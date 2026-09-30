"""Online leagues: play a season with friends, each on their own computer.

How it works: the commissioner's computer is the only one that plays the golf.
After every round it uploads the whole game to a small Supabase database. Friends
download it, watch the round, pick their lineup and send just that lineup back.
Before the next round the commissioner's computer collects everyone's lineups.

The database is reached through the Postgres functions in supabase/schema.sql.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

from .. import __version__
from .game import Game

STATE_FORMAT = 2  # Game.to_dict()["version"] this build understands


class OnlineError(Exception):
    pass


# ------------------------------------------------------------------ backends
class SupabaseBackend:
    def __init__(self, url: str, key: str, timeout: float = 15.0):
        self.url = url.rstrip("/")
        self.key = key
        self.timeout = timeout

    def call(self, fn: str, **params):
        from ..updater import ssl_context

        headers = {
            "apikey": self.key,
            "Content-Type": "application/json",
            "User-Agent": f"Fantasy-PGA/{__version__}",
        }
        if not self.key.startswith("sb_"):  # an older "anon" key is a JWT and goes here too
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(
            f"{self.url}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=ssl_context()) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read()).get("message") or str(exc)
            except (ValueError, AttributeError):
                msg = str(exc)
            raise OnlineError(msg) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise OnlineError(f"Can't reach the league server ({getattr(exc, 'reason', exc)})") from exc
        return json.loads(body) if body else None


class FakeBackend:
    """An in-memory copy of the database functions, for tests."""

    def __init__(self):
        self.leagues: dict[str, dict] = {}
        self.players: dict[str, list[dict]] = {}
        self.lineups: dict[str, dict[int, dict]] = {}
        self.fail = False  # pretend the internet is down
        self._n = 0

    def _token(self) -> str:
        self._n += 1
        return f"token-{self._n}"

    def call(self, fn: str, **p):
        if self.fail:
            raise OnlineError("Can't reach the league server (test)")
        return json.loads(json.dumps(getattr(self, fn)(**p)))  # same JSON round trip as the real one

    def _league(self, code):
        league = self.leagues.get(code.strip().upper())
        if not league:
            raise OnlineError(f"No league with the code {code.strip().upper()}")
        return league

    def fpga_create_league(self, p_name, p_manager, p_team, p_game_version):
        code = f"TEST{len(self.leagues) + 1:02d}"
        token = self._token()
        self.leagues[code] = {"code": code, "name": p_name or "Fantasy League", "token": token,
                              "status": "lobby", "version": 0, "state": None, "game_version": p_game_version}  # fmt: skip
        self.players[code] = [{"player_id": 0, "token": token, "manager": p_manager, "team": p_team}]
        self.lineups[code] = {}
        return {"code": code, "token": token}

    def fpga_join_league(self, p_code, p_manager, p_team):
        league = self._league(p_code)
        if league["status"] != "lobby":
            raise OnlineError("That league has already started")
        players = self.players[league["code"]]
        if len(players) >= 12:
            raise OnlineError("That league is full (12 managers)")
        token = self._token()
        players.append({"player_id": len(players), "token": token, "manager": p_manager, "team": p_team})
        return {"player_id": len(players) - 1, "token": token}

    def fpga_league_info(self, p_code):
        league = self._league(p_code)
        code = league["code"]
        return {
            "code": code,
            "name": league["name"],
            "status": league["status"],
            "version": league["version"],
            "game_version": league["game_version"],
            "players": [{k: v for k, v in p.items() if k != "token"} for p in self.players[code]],
            "lineups": [{k: v for k, v in x.items() if k != "lineup"} for x in self.lineups[code].values()],
        }

    def fpga_get_state(self, p_code):
        league = self._league(p_code)
        return {"version": league["version"], "state": league["state"]}

    def fpga_submit_lineup(self, p_code, p_player, p_token, p_season, p_event, p_round, p_lineup):
        league = self._league(p_code)
        if not any(
            p["player_id"] == p_player and p["token"] == p_token for p in self.players[league["code"]]
        ):
            raise OnlineError("Not a manager in this league")
        self.lineups[league["code"]][p_player] = {"player_id": p_player, "season": p_season,
            "event_index": p_event, "round": p_round, "lineup": p_lineup}  # fmt: skip

    def fpga_get_lineups(self, p_code, p_token):
        league = self._league(p_code)
        if league["token"] != p_token:
            raise OnlineError("Only the commissioner can do that")
        return list(self.lineups[league["code"]].values())

    def fpga_save_state(self, p_code, p_token, p_state, p_expected):
        league = self._league(p_code)
        if league["token"] != p_token:
            raise OnlineError("Only the commissioner can do that")
        if league["version"] != p_expected:
            raise OnlineError("The league was changed somewhere else - reload it first")
        league.update(state=p_state, version=league["version"] + 1, status="active")
        return league["version"]


def default_backend():
    """The league server this build talks to, or None if online play isn't set up."""
    from .. import online_config

    url = os.environ.get("FANTASY_PGA_SUPABASE_URL") or online_config.SUPABASE_URL
    key = os.environ.get("FANTASY_PGA_SUPABASE_KEY") or online_config.SUPABASE_KEY
    return SupabaseBackend(url, key) if url and key else None


# ------------------------------------------------------------------ this computer's leagues
def online_dir() -> Path:
    return Path.home() / ".fantasy_pga" / "online"


def load_profiles() -> list[dict]:
    try:
        return json.loads((online_dir() / "leagues.json").read_text())
    except (OSError, ValueError):
        return []


def save_profiles(profiles: list[dict]):
    d = online_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "leagues.tmp"
    tmp.write_text(json.dumps(profiles, indent=1))
    tmp.replace(d / "leagues.json")


def _remember(profile: dict):
    profiles = [p for p in load_profiles() if p["code"] != profile["code"]]
    save_profiles([profile, *profiles])


def forget(code: str):
    save_profiles([p for p in load_profiles() if p["code"] != code])
    (online_dir() / f"{code}.json").unlink(missing_ok=True)


class League:
    """One online league, as seen from this computer."""

    def __init__(self, backend, profile: dict):
        self.backend = backend
        self.profile = profile  # code, name, player_id, token, manager, team, commissioner, watched
        self.info: dict = {}
        self.version = -1
        self.game: Game | None = None
        self.unsynced = False  # the commissioner has changes the server hasn't got yet
        self._pending: tuple[int, dict] | None = None
        self._polling = False
        self.poll_error = ""
        self._load_cache()

    # -------------------------------------------------------------- joining
    @classmethod
    def create(cls, backend, name: str, manager: str, team: str) -> League:
        res = backend.call("fpga_create_league", p_name=name, p_manager=manager, p_team=team,
                           p_game_version=__version__)  # fmt: skip
        profile = {"code": res["code"], "name": name or "Fantasy League", "player_id": 0, "token": res["token"],
                   "manager": manager, "team": team, "commissioner": True, "watched": None}  # fmt: skip
        _remember(profile)
        league = cls(backend, profile)
        league.refresh_info()
        return league

    @classmethod
    def join(cls, backend, code: str, manager: str, team: str) -> League:
        code = code.strip().upper()
        res = backend.call("fpga_join_league", p_code=code, p_manager=manager, p_team=team)
        info = backend.call("fpga_league_info", p_code=code)
        profile = {"code": code, "name": info["name"], "player_id": res["player_id"], "token": res["token"],
                   "manager": manager, "team": team, "commissioner": False, "watched": None}  # fmt: skip
        _remember(profile)
        league = cls(backend, profile)
        league.info = info
        return league

    @property
    def code(self) -> str:
        return self.profile["code"]

    @property
    def commissioner(self) -> bool:
        return bool(self.profile.get("commissioner"))

    @property
    def started(self) -> bool:
        return self.info.get("status") == "active" or self.game is not None

    # -------------------------------------------------------------- local copy
    def _cache_path(self) -> Path:
        return online_dir() / f"{self.code}.json"

    def _load_cache(self):
        try:
            d = json.loads(self._cache_path().read_text())
            self._set_game(d["version"], d["state"])
            self.unsynced = d.get("unsynced", False)
        except (OSError, ValueError, KeyError):
            pass

    def _save_cache(self):
        if self.game is None:
            return
        online_dir().mkdir(parents=True, exist_ok=True)
        tmp = self._cache_path().with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"version": self.version, "state": self.game.to_dict(), "unsynced": self.unsynced})
        )
        tmp.replace(self._cache_path())

    def _set_game(self, version: int, state: dict):
        if state.get("version", 1) > STATE_FORMAT:
            raise OnlineError("This league needs a newer version of Fantasy PGA - please update.")
        game = Game.from_dict(state)
        game.me_index = game.team_index(self.profile["player_id"])
        self.game, self.version = game, version

    # -------------------------------------------------------------- talking to the server
    def refresh_info(self) -> dict:
        info = self.backend.call("fpga_league_info", p_code=self.code)
        if not info:
            raise OnlineError(f"The league {self.code} no longer exists.")
        self.info = info
        return info

    def sync(self) -> bool:
        """Bring this computer up to date. Returns True if the game changed."""
        if self.unsynced and self.commissioner:
            self.upload()  # send what the server missed first
        info = self.refresh_info()
        if info["version"] > self.version and info["status"] == "active":
            res = self.backend.call("fpga_get_state", p_code=self.code)
            self._set_game(res["version"], res["state"])
            self._save_cache()
            return True
        return False

    def poll_async(self):
        """Check the server in the background (take_update() picks up the result)."""
        if self._polling:
            return
        self._polling = True

        def work():
            try:
                info = self.backend.call("fpga_league_info", p_code=self.code)
                if info:
                    self.info = info
                    if info["version"] > self.version and info["status"] == "active":
                        res = self.backend.call("fpga_get_state", p_code=self.code)
                        self._pending = (res["version"], res["state"])
                self.poll_error = ""
            except Exception as exc:  # stay quiet in the background; show it on screen
                self.poll_error = str(exc)
            finally:
                self._polling = False

        threading.Thread(target=work, daemon=True).start()

    def take_update(self) -> bool:
        """Use a newer game found by poll_async(). Call from the main thread."""
        pending, self._pending = self._pending, None
        if pending and pending[0] > self.version and not (self.commissioner and self.unsynced):
            self._set_game(*pending)
            self._save_cache()
            return True
        return False

    def upload(self):
        """Commissioner: save the game to the server."""
        try:
            self.version = self.backend.call("fpga_save_state", p_code=self.code, p_token=self.profile["token"],
                                             p_state=self.game.to_dict(), p_expected=self.version)  # fmt: skip
            self.unsynced = False
        except OnlineError:
            self.unsynced = True
            raise
        finally:
            self._save_cache()

    # -------------------------------------------------------------- lineups
    def lineup_key(self) -> tuple[int, int, int]:
        g = self.game
        return g.season, g.event_index, g.t.round_no

    def submitted(self) -> dict[int, bool]:
        """Which human managers have sent in a lineup for the next round."""
        season, event, rnd = self.lineup_key()
        sent = {
            x["player_id"]
            for x in self.info.get("lineups", [])
            if (x["season"], x["event_index"], x["round"]) == (season, event, rnd)
        }
        return {t.player_id: t.player_id in sent for t in self.game.teams if t.human}

    def submit_lineup(self):
        season, event, rnd = self.lineup_key()
        self.backend.call("fpga_submit_lineup", p_code=self.code, p_player=self.profile["player_id"],
                          p_token=self.profile["token"], p_season=season, p_event=event, p_round=rnd,
                          p_lineup=self.game.lineup_of())  # fmt: skip
        try:
            self.refresh_info()
        except OnlineError:
            pass

    # -------------------------------------------------------------- the commissioner's jobs
    def start_season(self, ai_rivals: int, seed: int | None = None):
        info = self.refresh_info()
        players = [(p["manager"], p["team"]) for p in sorted(info["players"], key=lambda p: p["player_id"])]
        self.game = Game.new_league(players, ai_rivals, info["name"], seed=seed)
        self.game.me_index = 0
        self.version = info["version"]
        self.upload()

    def play_round(self) -> dict:
        g = self.game
        season, event, rnd = self.lineup_key()
        for x in self.backend.call("fpga_get_lineups", p_code=self.code, p_token=self.profile["token"]):
            if x["player_id"] == self.profile["player_id"]:
                continue  # the commissioner's own lineup is the one on this computer
            if (x["season"], x["event_index"], x["round"]) != (season, event, rnd):
                continue  # an old one: they keep the lineup they had
            try:
                team = g.teams[g.team_index(x["player_id"])]
            except StopIteration:
                continue
            g.apply_lineup(team, x["lineup"])
        report = g.play_round()
        self.mark_watched()
        try:
            self.upload()
        except OnlineError:
            pass  # kept as unsynced; sent next time
        return report

    def next_event(self):
        self.game.next_event()
        self.mark_watched()
        try:
            self.upload()
        except OnlineError:
            pass

    # -------------------------------------------------------------- watching rounds
    def unwatched(self) -> list[dict]:
        """Round reports of the current tournament this computer hasn't shown yet."""
        g = self.game
        w = self.profile.get("watched")
        if not w or (w[0], w[1]) != (g.season, g.event_index):
            done = 0
        else:
            done = w[2]
        return [r for r in g.reports if r["round"] > done]

    def missed_event(self) -> dict | None:
        """If the commissioner moved on before we saw the end of the last tournament, its summary."""
        g = self.game
        if not g.results:
            return None
        last = g.results[-1]
        w = self.profile.get("watched") or [0, -1, 0]
        if g.event_index != last["event"] and tuple(w) < (g.season, last["event"], 4):
            return last
        return None

    def mark_watched(self):
        g = self.game
        self.profile["watched"] = [g.season, g.event_index, g.t.round_no]
        _remember(self.profile)


def open_league(profile: dict, backend=None) -> League:
    backend = backend or default_backend()
    if backend is None:
        raise OnlineError("Online play isn't set up in this version of the game.")
    return League(backend, profile)

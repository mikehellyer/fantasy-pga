"""Draw every screen (headless) - catches crashes such as a missing setting."""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")


def _draw(scene, app, frames=1):
    for _ in range(frames):
        scene.update(1 / 60)
        scene.draw(app.canvas)


def test_every_screen_draws(tmp_path, monkeypatch):
    from fantasy_pga.core import game as gm
    from fantasy_pga.ui import hub, intro, leaderboard, lineup, live, results, screens, tables
    from fantasy_pga.ui import theme as T
    from fantasy_pga.ui.app import App

    monkeypatch.setattr(T, "_fonts", {})
    save = tmp_path / "savegame.json"
    for module in (gm, screens, hub, intro):
        monkeypatch.setattr(module, "save_path", lambda: save, raising=False)

    app = App()
    g = gm.Game.new("Test", "Test Team", seed=5)
    app.game = g
    app.push(hub.HubScene(app))
    _draw(lineup.PickScene(app), app)
    _draw(leaderboard.LeaderboardScene(app), app)
    g.auto_pick()
    _draw(hub.HubScene(app), app)
    for _ in range(4):
        report = g.play_round()
        scene = live.LiveRoundScene(app, report)
        _draw(scene, app, 30)
        scene.skip()
        _draw(scene, app)
        _draw(lineup.PickScene(app), app)
    board = leaderboard.LeaderboardScene(app)
    _draw(board, app)
    _draw(leaderboard.ScorecardScene(app, g.me.picks[0]), app)
    _draw(results.EventResultScene(app), app)
    standings = tables.StandingsScene(app)
    for _ in standings.PAGES:
        _draw(standings, app)
        standings.page = (standings.page + 1) % len(standings.PAGES)
        standings.refresh()
    for scene in (
        tables.TeamScene(app, g.teams[3]),
        tables.ScheduleScene(app),
        tables.FedExScene(app),
        tables.GolfersScene(app),
        tables.GolferScene(app, g.t.winner),
        tables.RecordsScene(app),
        tables.RulesScene(app),
        results.SeasonEndScene(app),
        hub.HubScene(app),
        screens.NewGameScene(app),
    ):
        _draw(scene, app)
    pygame.quit()


def test_intro_survives_an_update_being_found(tmp_path, monkeypatch):
    from fantasy_pga import updater
    from fantasy_pga.ui import intro
    from fantasy_pga.ui import theme as T
    from fantasy_pga.ui.app import App

    monkeypatch.setattr(T, "_fonts", {})  # fonts from an earlier test die with its pygame.quit()
    monkeypatch.setattr(updater, "check_async", lambda callback: None)
    monkeypatch.setattr(intro, "save_path", lambda: tmp_path / "savegame.json")
    app = App()
    app.push(intro.BootScene(app))
    info = {"version": "99.0.0", "url": "", "notes": "", "download": ""}
    for frame in range(400):
        if frame == 30:
            app.update_info = info
        app.scene.update(1 / 60)
        app.scene.draw(app.canvas)
    assert isinstance(app.scene, intro.TitleScene)
    assert "UPDATE TO v99.0.0" in [item[0] for item in app.scene.menu.items]
    pygame.quit()

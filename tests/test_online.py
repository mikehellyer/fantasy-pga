import pytest

from fantasy_pga.core import online
from fantasy_pga.core.online import FakeBackend, League, OnlineError


@pytest.fixture(autouse=True)
def local_files(tmp_path, monkeypatch):
    monkeypatch.setattr(online, "online_dir", lambda: tmp_path / "online")


def setup_league(friends=2, ai=3):
    backend = FakeBackend()
    boss = League.create(backend, "The Friday Four", "Mike", "Tee Party")
    pals = [League.join(backend, boss.code, f"Pal {i}", f"Pal Team {i}") for i in range(friends)]
    boss.start_season(ai_rivals=ai, seed=4)
    for pal in pals:
        assert pal.sync()
    return backend, boss, pals


def test_create_join_and_start():
    backend, boss, pals = setup_league()
    g = boss.game
    assert [t.manager for t in g.teams if t.human] == ["Mike", "Pal 0", "Pal 1"]
    assert len(g.teams) == 6  # 3 managers + 3 computer rivals
    assert g.me.name == "Tee Party"
    assert pals[1].game.me.name == "Pal Team 1" and pals[1].game.me_index == 2
    with pytest.raises(OnlineError, match="already started"):
        League.join(backend, boss.code, "Late", "Latecomers")


def test_bad_code_and_tokens():
    backend = FakeBackend()
    with pytest.raises(OnlineError, match="No league"):
        League.join(backend, "NOPE99", "A", "B")
    boss = League.create(backend, "L", "Mike", "T")
    pal = League.join(backend, boss.code, "Pal", "P")
    boss.start_season(0, seed=1)
    pal.sync()
    pal.profile["commissioner"] = True  # a friend can't pretend to be the commissioner
    with pytest.raises(OnlineError, match="Only the commissioner"):
        pal.play_round()


def test_a_tournament_with_friends():
    backend, boss, pals = setup_league()
    # a friend picks and submits their team; the other forgets
    pal = pals[0]
    pg = pal.game
    picks = sorted(pg.t.field, key=lambda x: pg.golfers[x].owgr)[10:16]
    for gid in picks:
        pg.toggle_pick(gid)
    pg.set_captain(picks[2])
    pal.submit_lineup()
    boss.refresh_info()
    assert boss.submitted() == {0: False, 1: True, 2: False}

    boss.game.auto_pick()
    report = boss.play_round()
    assert report["round"] == 1
    g = boss.game
    assert sorted(g.teams[1].picks) == sorted(picks) and g.teams[1].rounds[0]["captain"] == picks[2]
    assert len(g.teams[2].picks) == 6  # the forgetful friend's caddie picked for them
    assert any("caddie" in n for n in g.news)

    # friends get the round and can watch it
    for p in pals:
        assert p.sync()
        assert [r["round"] for r in p.unwatched()] == [1]
        p.mark_watched()
        assert p.unwatched() == []
    # between rounds a friend changes captain
    new_captain = next(x for x in pal.game.me.starters if x != picks[2])
    pal.game.set_captain(new_captain)
    pal.submit_lineup()
    boss.play_round()
    assert boss.game.teams[1].rounds[1]["captain"] == new_captain
    boss.play_round()
    boss.play_round()
    assert boss.game.t.complete
    pals[1].sync()
    assert [r["round"] for r in pals[1].unwatched()] == [2, 3, 4]
    # the commissioner moves on before pal 1 watches: they're told what they missed
    boss.next_event()
    pals[1].sync()
    missed = pals[1].missed_event()
    assert missed and missed["event"] == 0
    assert pals[1].game.week_points(missed)[0] == boss.game.teams[2].event_points[0]


def test_commissioner_keeps_playing_when_offline():
    backend, boss, pals = setup_league(friends=1, ai=0)
    boss.game.auto_pick()
    backend.fail = True
    with pytest.raises(OnlineError):  # can't collect the friends' lineups: nothing is played
        boss.play_round()
    assert boss.game.t.round_no == 0
    backend.fail = False
    real_save = backend.fpga_save_state

    def down(**kw):
        raise OnlineError("Can't reach the league server (test)")

    backend.fpga_save_state = down  # the connection drops just after the round is played
    boss.play_round()
    assert boss.unsynced and boss.game.t.round_no == 1
    backend.fpga_save_state = real_save
    pals[0].sync()
    assert pals[0].game.t.round_no == 0  # the server hasn't got it yet
    boss.sync()  # sends it
    assert not boss.unsynced
    assert pals[0].sync() and pals[0].game.t.round_no == 1


def test_leagues_are_remembered_on_this_computer():
    backend, boss, pals = setup_league(friends=1, ai=0)
    profiles = online.load_profiles()
    assert {p["code"] for p in profiles} == {boss.code}
    again = League(backend, boss.profile)  # reopened later: the cached game is there straight away
    assert again.game is not None and again.version == boss.version
    online.forget(boss.code)
    assert online.load_profiles() == []


def test_background_polling():
    backend, boss, pals = setup_league(friends=1, ai=0)
    boss.game.auto_pick()
    boss.play_round()
    pal = pals[0]
    pal.poll_async()
    import time

    for _ in range(100):
        if not pal._polling:
            break
        time.sleep(0.01)
    assert pal.take_update() and pal.game.t.round_no == 1

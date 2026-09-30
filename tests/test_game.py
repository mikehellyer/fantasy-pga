import json

import pytest

from fantasy_pga.core import data
from fantasy_pga.core.game import Game, LineupError


def new_game(seed=7):
    return Game.new("Tester", "Test Team", seed=seed)


def test_new_game_sets_up_a_league_and_the_first_event():
    g = new_game()
    assert len(g.teams) == 12 and g.me.human
    assert g.event.name == "Sony Open in Hawaii"
    assert len(g.t.field) > 80
    for team in g.teams[1:]:
        assert team.lineup_ready()  # the rivals have picked


def test_you_need_a_full_lineup_to_play():
    g = new_game()
    with pytest.raises(LineupError):
        g.play_round()
    g.auto_pick()
    assert g.me.lineup_ready()
    g.play_round()
    assert g.t.round_no == 1


def test_picking_rules():
    g = new_game()
    field = sorted(g.t.field, key=lambda x: g.golfers[x].owgr)
    for gid in field[:6]:
        assert g.toggle_pick(gid) == ""
    assert "already have 6" in g.toggle_pick(field[6])
    assert len(g.me.starters) == 4 and g.me.captain == field[0]
    g.set_captain(field[5])  # a bench golfer: he's moved into the starters
    assert g.me.captain == field[5] and field[5] in g.me.starters and len(g.me.starters) == 4
    g.toggle_pick(field[5])  # dropping the captain hands it on
    assert g.me.captain in g.me.starters


def test_three_starts_per_segment():
    g = new_game()
    star = min(g.t.field, key=lambda x: g.golfers[x].owgr)
    used = 0
    while g.segment == 0 and not g.season_over:
        if star in g.t.field and g.me.starts_left(star, 0) > 0:
            g.toggle_pick(star)
            g.set_captain(star)
        g.auto_pick()
        if star in g.me.starters:
            used += 1
        while not g.t.complete:
            g.play_round()
        g.next_event()
        if star in g.t.field and g.segment == 0:
            ok, why = g.can_pick(star)
            if used >= data.STARTS_PER_SEGMENT:
                assert not ok and "no starts left" in why
    assert used == data.STARTS_PER_SEGMENT
    assert g.segment == 1 and g.me.starts_left(star, 1) == data.STARTS_PER_SEGMENT


def test_points_add_up_and_captain_doubles():
    g = new_game()
    g.auto_pick()
    while not g.t.complete:
        g.play_round()
    me = g.me
    for r, lock in enumerate(me.rounds):
        for gid, pts in lock["points"].items():
            base = g.round_points(gid, r)["total"]
            assert pts == (base * 2 if gid == lock["captain"] else base)
    assert me.points == me.event_total == sum(r["total"] for r in me.rounds)
    assert g.results[-1]["my_points"] == me.event_total


def test_missed_cut_starters_are_swapped_out():
    for seed in range(30):
        g = new_game(seed)
        # start the six weakest golfers so someone misses the cut
        weakest = sorted(g.t.field, key=lambda x: -g.golfers[x].owgr)[:6]
        for gid in weakest:
            g.toggle_pick(gid)
        g.play_round()
        g.play_round()
        me = g.me
        missed = [p for p in me.picks if p not in g.t.active()]
        bench_ok = [p for p in me.bench if p in g.t.active()]
        if missed and bench_ok:
            assert me.notes
            live_starters = [p for p in me.starters if p in g.t.active()]
            assert len(live_starters) == min(4, len([p for p in me.picks if p in g.t.active()]))
            return
    pytest.fail("no auto-swap happened in 30 tries")


def test_whole_season_and_save_load():
    g = new_game(11)
    while True:
        g.auto_pick()
        while not g.t.complete:
            g.play_round()
        if g.season_over:
            break
        if g.event_index == 15:
            g = Game.from_dict(json.loads(json.dumps(g.to_dict())))  # survives a save mid-season
        g.next_event()
    assert len(g.results) == 32
    assert data.SCHEDULE[g.event_index].kind == "playoff" and len(g.t.field) == 30
    assert sum(tm.points for tm in g.teams) == sum(sum(tm.segment_points) for tm in g.teams)
    fedex_leader = g.fedex_table()[0]
    assert fedex_leader[1] > 2000
    g.next_event()
    assert g.season == 2027 and g.event_index == 0
    assert g.history[0]["season"] == 2026
    assert all(tm.points == 0 for tm in g.teams)


def test_same_seed_same_game():
    a, b = new_game(5), new_game(5)
    for g in (a, b):
        g.auto_pick()
        while not g.t.complete:
            g.play_round()
    assert a.t.winner == b.t.winner and a.me.event_total == b.me.event_total

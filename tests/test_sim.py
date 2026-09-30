import random
import statistics

from fantasy_pga.core import data
from fantasy_pga.core.database import load_golfers
from fantasy_pga.core.sim import BASE_MEAN, Tournament, course_holes, hole_score


def test_golfer_database():
    golfers = load_golfers()
    assert len(golfers) == 200
    assert golfers[0].name == "Scottie Scheffler" and golfers[0].owgr == 1
    assert golfers[0].skill > golfers[50].skill > golfers[199].skill
    assert {g.tour for g in golfers} == {"PGA", "EUR", "LIV", "ASIA"}


def test_schedule_matches_the_fantasy_segments():
    assert len(data.SCHEDULE) == 32
    assert [len(data.segment_events(s)) for s in range(3)] == [9, 11, 12]
    majors = [e.short for e in data.SCHEDULE if e.kind == "major"]
    assert majors == ["THE MASTERS", "PGA CHAMP", "U.S. OPEN", "THE OPEN"]


def test_courses_have_the_right_par():
    for ev in data.SCHEDULE:
        holes = course_holes(ev)
        assert len(holes) == 18
        assert sum(p for p, _ in holes) == ev.par
        assert holes == course_holes(ev)  # always the same layout


def test_hole_scores_average_what_was_asked():
    rng = random.Random(1)
    for par in (3, 4, 5):
        for shift in (-0.2, 0.0, 0.2):
            target = BASE_MEAN[par] + shift
            avg = statistics.mean(hole_score(par, target, rng) for _ in range(20000))
            assert abs(avg - target) < 0.03


def event(short):
    return next(i for i, e in enumerate(data.SCHEDULE) if e.short == short)


def _play(event_index, field, seed):
    golfers = load_golfers()
    t = Tournament(event_index, field, seed)
    for _ in range(4):
        t.play_round(golfers)
    return t


def test_a_tournament_is_realistic():
    golfers = load_golfers()
    field = [g.id for g in golfers if g.tour == "PGA"][:125]
    wins = []
    for seed in range(12):
        t = _play(event("JOHN DEERE"), field, seed)  # lots of birdies
        assert t.complete and t.winner in t.cut_made
        assert t.finish[t.winner] == "1"
        assert 60 <= len(t.cut_made) <= 85  # top 65 and ties
        assert all(t.finish[g] == "MC" for g in field if g not in t.cut_made)
        wins.append(t.total(t.winner))
    assert -32 < statistics.mean(wins) < -17  # the real tournament is won at about -20


def test_no_cut_events_keep_everyone():
    golfers = load_golfers()
    field = [g.id for g in golfers if g.tour == "PGA"][:72]
    t = _play(event("HERITAGE"), field, 3)  # no cut
    assert t.cut_made is None
    assert all(len(t.scores[g]) == 4 for g in field)


def test_tournament_save_round_trip():
    golfers = load_golfers()
    t = _play(0, list(range(0, 120)), 9)
    t2 = Tournament.from_dict(t.to_dict())
    assert t2.leaderboard() == t.leaderboard()
    assert t2.finish == t.finish
    del golfers

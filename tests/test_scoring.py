from fantasy_pga.core import data
from fantasy_pga.core.scoring import hole_points, round_breakdown, shared_fedex


def test_hole_points():
    assert hole_points(-1, 4) == data.HOLE_POINTS[-1]
    assert hole_points(0, 4) == data.HOLE_POINTS[0]
    assert hole_points(3, 4) == data.DOUBLE_OR_WORSE
    assert hole_points(-2, 3) == data.HOLE_POINTS[-2] + data.HOLE_IN_ONE_BONUS  # an ace
    assert hole_points(-2, 5) == data.HOLE_POINTS[-2]


def test_round_bonuses():
    pars = [4] * 18
    card = [-1, -1, -1] + [0] * 15  # three birdies in a row, no bogeys
    b = round_breakdown(card, pars)
    assert b["streak"] == data.BIRDIE_STREAK
    assert b["bogey_free"] == data.BOGEY_FREE
    assert b["holes"] == 3 * data.HOLE_POINTS[-1] + 15 * data.HOLE_POINTS[0]
    b = round_breakdown([-1, 0, -1, 1] + [0] * 14, pars)
    assert b["streak"] == 0 and b["bogey_free"] == 0


def test_tied_golfers_share_fedex_points():
    finish = {1: "1", 2: "T2", 3: "T2", 4: "4", 5: "MC"}
    pts = shared_fedex("regular", finish)
    assert pts[1] == 500
    assert pts[2] == pts[3] == round(500 * (0.6 + 0.38) / 2)
    assert pts[4] == round(500 * 0.27)
    assert pts[5] == 0

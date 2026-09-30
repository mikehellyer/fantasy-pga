"""Fixed game data: the fantasy schedule, courses, and the scoring tables.

The schedule is the real 2026 PGA TOUR season as used by PGA TOUR Fantasy Golf:
32 events in three segments (opposite-field events and the Zurich team event
don't count). Each season of the game replays this schedule.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------- fantasy rules
ROSTER_SIZE = 6  # golfers picked each week
STARTERS = 4  # of whom this many score each round
STARTS_PER_SEGMENT = 3  # how often you can start any one golfer in a segment
CAPTAIN_MULTIPLIER = 2

# Points for each hole, by score relative to par
HOLE_POINTS = {-3: 8, -2: 5, -1: 2, 0: 1, 1: -1}  # anything worse than bogey: DOUBLE_OR_WORSE
DOUBLE_OR_WORSE = -3
HOLE_IN_ONE_BONUS = 10  # on top of the eagle points
BIRDIE_STREAK = 3  # 3 or more birdies-or-better in a row (once per round)
BOGEY_FREE = 3  # a full round without a bogey or worse
ALL_ROUNDS_UNDER_70 = 5  # all four rounds under 70 strokes (added to round 4)

# FedExCup points for the winner, by event type (the playoffs are worth four times a
# regular event, as on the real tour)
FEDEX_WINNER = {"regular": 500, "signature": 700, "players": 750, "major": 750, "playoff": 2000}
# Fantasy finishing bonus = FedExCup points / 10, but the playoffs use the signature scale
BONUS_SCALE = {"regular": 500, "signature": 700, "players": 750, "major": 750, "playoff": 700}
# Share of the winner's FedExCup points for 2nd..10th; after that they tail off
FEDEX_TOP10 = [1.0, 0.6, 0.38, 0.27, 0.22, 0.2, 0.18, 0.17, 0.16, 0.15]

SEGMENT_NAMES = ["Segment 1", "Segment 2", "Segment 3"]


@dataclass(frozen=True)
class Event:
    name: str
    short: str  # up to 12 letters, for tables
    course: str
    location: str
    par: int
    difficulty: float  # typical scoring vs par for an average tour player, per round
    wind: int  # how windy it tends to be, 0 (calm) to 3 (links in a gale)
    kind: str  # regular / signature / players / major / playoff
    segment: int  # 0, 1, 2
    date: str  # final-round day
    real_winner: str  # who actually won in 2026
    cut: int = 65  # top N and ties after 36 holes; 0 = no cut
    field_size: int = 144


def _e(*args, **kw) -> Event:
    return Event(*args, **kw)


# fmt: off
SCHEDULE: list[Event] = [
    # ------------------------------------------------------------- segment 1
    _e('Sony Open in Hawaii', 'SONY OPEN', 'Waialae Country Club', 'Honolulu, Hawaii', 70, -1.2, 2, 'regular', 0, '18 Jan', 'Chris Gotterup'),
    _e('The American Express', 'AMEX', 'PGA West Stadium Course', 'La Quinta, California', 72, -2.6, 0, 'regular', 0, '25 Jan', 'Scottie Scheffler'),
    _e('Farmers Insurance Open', 'FARMERS', 'Torrey Pines (South)', 'San Diego, California', 72, 1.2, 1, 'regular', 0, '1 Feb', 'Justin Rose'),
    _e('WM Phoenix Open', 'PHOENIX', 'TPC Scottsdale (Stadium)', 'Scottsdale, Arizona', 71, -1.5, 0, 'regular', 0, '8 Feb', 'Chris Gotterup'),
    _e('AT&T Pebble Beach Pro-Am', 'PEBBLE BEACH', 'Pebble Beach Golf Links', 'Pebble Beach, California', 72, -0.2, 2, 'signature', 0, '15 Feb', 'Collin Morikawa', cut=0, field_size=80),
    _e('The Genesis Invitational', 'GENESIS', 'Riviera Country Club', 'Pacific Palisades, California', 71, 0.4, 1, 'signature', 0, '22 Feb', 'Jacob Bridgeman', cut=50, field_size=72),
    _e('Cognizant Classic', 'COGNIZANT', 'PGA National (Champion)', 'Palm Beach Gardens, Florida', 71, 0.3, 2, 'regular', 0, '1 Mar', 'Nico Echavarria'),
    _e('Arnold Palmer Invitational', 'BAY HILL', 'Bay Hill Club & Lodge', 'Orlando, Florida', 72, 1.3, 1, 'signature', 0, '8 Mar', 'Akshay Bhatia', cut=50, field_size=72),
    _e('THE PLAYERS Championship', 'THE PLAYERS', 'TPC Sawgrass (Stadium)', 'Ponte Vedra Beach, Florida', 72, 0.4, 1, 'players', 0, '15 Mar', 'Cameron Young'),
    # ------------------------------------------------------------- segment 2
    _e('Valspar Championship', 'VALSPAR', 'Innisbrook (Copperhead)', 'Palm Harbor, Florida', 71, 0.8, 1, 'regular', 1, '22 Mar', 'Matt Fitzpatrick'),
    _e("Texas Children's Houston Open", 'HOUSTON', 'Memorial Park Golf Course', 'Houston, Texas', 70, 0.4, 1, 'regular', 1, '29 Mar', 'Gary Woodland'),
    _e('Valero Texas Open', 'VALERO', 'TPC San Antonio (Oaks)', 'San Antonio, Texas', 72, 0.9, 2, 'regular', 1, '5 Apr', 'J.J. Spaun'),
    _e('Masters Tournament', 'THE MASTERS', 'Augusta National Golf Club', 'Augusta, Georgia', 72, 1.4, 1, 'major', 1, '12 Apr', 'Rory McIlroy', cut=50, field_size=90),
    _e('RBC Heritage', 'HERITAGE', 'Harbour Town Golf Links', 'Hilton Head Island, S. Carolina', 71, -0.4, 2, 'signature', 1, '19 Apr', 'Matt Fitzpatrick', cut=0, field_size=72),
    _e('Cadillac Championship', 'CADILLAC', 'Trump National Doral (Blue Monster)', 'Doral, Florida', 72, 0.9, 2, 'signature', 1, '3 May', 'Cameron Young', cut=0, field_size=72),
    _e('Truist Championship', 'TRUIST', 'Quail Hollow Club', 'Charlotte, North Carolina', 71, 1.0, 1, 'signature', 1, '10 May', 'Kristoffer Reitan', cut=0, field_size=72),
    _e('PGA Championship', 'PGA CHAMP', 'Aronimink Golf Club', 'Newtown Square, Pennsylvania', 70, 1.0, 1, 'major', 1, '17 May', 'Aaron Rai', cut=70, field_size=156),
    _e('THE CJ CUP Byron Nelson', 'BYRON NELSON', 'TPC Craig Ranch', 'McKinney, Texas', 71, -2.6, 1, 'regular', 1, '24 May', 'Wyndham Clark'),
    _e('Charles Schwab Challenge', 'COLONIAL', 'Colonial Country Club', 'Fort Worth, Texas', 70, -0.1, 2, 'regular', 1, '31 May', 'Russell Henley', field_size=120),
    _e('the Memorial Tournament', 'MEMORIAL', 'Muirfield Village Golf Club', 'Dublin, Ohio', 72, 1.2, 1, 'signature', 1, '7 Jun', 'J.T. Poston', cut=50, field_size=72),
    # ------------------------------------------------------------- segment 3
    _e('RBC Canadian Open', 'CANADIAN OPEN', 'TPC Toronto (North)', 'Caledon, Ontario', 70, -0.6, 1, 'regular', 2, '14 Jun', 'Bud Cauley', field_size=156),
    _e('U.S. Open', 'U.S. OPEN', 'Shinnecock Hills Golf Club', 'Southampton, New York', 70, 2.8, 2, 'major', 2, '21 Jun', 'Wyndham Clark', cut=60, field_size=156),
    _e('Travelers Championship', 'TRAVELERS', 'TPC River Highlands', 'Cromwell, Connecticut', 70, -1.8, 1, 'signature', 2, '28 Jun', 'Viktor Hovland', cut=0, field_size=72),
    _e('John Deere Classic', 'JOHN DEERE', 'TPC Deere Run', 'Silvis, Illinois', 71, -2.5, 1, 'regular', 2, '5 Jul', 'Chris Gotterup', field_size=156),
    _e('Genesis Scottish Open', 'SCOTTISH OPEN', 'The Renaissance Club', 'North Berwick, Scotland', 70, -0.4, 3, 'regular', 2, '12 Jul', 'Tom Kim', field_size=156),
    _e('The Open Championship', 'THE OPEN', 'Royal Birkdale Golf Club', 'Southport, England', 70, 1.6, 3, 'major', 2, '19 Jul', 'Ryan Fox', cut=70, field_size=156),
    _e('3M Open', '3M OPEN', 'TPC Twin Cities', 'Blaine, Minnesota', 71, -1.8, 1, 'regular', 2, '26 Jul', 'Jackson Koivun', field_size=156),
    _e('Rocket Classic', 'ROCKET', 'Detroit Golf Club', 'Detroit, Michigan', 72, -2.4, 1, 'regular', 2, '2 Aug', 'Michael Thorbjornsen', field_size=156),
    _e('Wyndham Championship', 'WYNDHAM', 'Sedgefield Country Club', 'Greensboro, North Carolina', 70, -2.0, 1, 'regular', 2, '9 Aug', 'Michael Brennan', field_size=156),
    _e('FedEx St. Jude Championship', 'ST. JUDE', 'TPC Southwind', 'Memphis, Tennessee', 70, -0.5, 1, 'playoff', 2, '16 Aug', 'Scottie Scheffler', cut=0, field_size=70),
    _e('BMW Championship', 'BMW CHAMP', 'Bellerive Country Club', 'St. Louis, Missouri', 71, 0.3, 1, 'playoff', 2, '23 Aug', 'Wyndham Clark', cut=0, field_size=50),
    _e('TOUR Championship', 'TOUR CHAMP', 'East Lake Golf Club', 'Atlanta, Georgia', 70, -0.3, 1, 'playoff', 2, '30 Aug', 'Scottie Scheffler', cut=0, field_size=30),
]
# fmt: on

KIND_LABEL = {
    "regular": "",
    "signature": "SIGNATURE EVENT",
    "players": "FLAGSHIP EVENT",
    "major": "MAJOR CHAMPIONSHIP",
    "playoff": "FEDEXCUP PLAYOFFS",
}

# The rival managers in your private league (all fictional)
RIVALS = [
    ("Big Hitters GC", "Dougie Baird", "chalk"),
    ("Fore Play", "Sandra Kwan", "balanced"),
    ("Grip It & Rip It", "Tony Varga", "longshot"),
    ("The Bunker Mentality", "Morag Reid", "saver"),
    ("Albatross United", "Pete Okafor", "balanced"),
    ("Sunday Red", "Linda Frost", "chalk"),
    ("Three-Putt Thunder", "Gary Hollis", "longshot"),
    ("Hole In Won", "Priya Shah", "saver"),
    ("Dogleg Dynamos", "Frank Munro", "balanced"),
    ("Mulligan Stew", "Carol Byrne", "longshot"),
    ("The Back Nine", "Hamish Todd", "chalk"),
]

COUNTRY_NAMES = {
    "USA": "United States",
    "NIR": "Northern Ireland",
    "ENG": "England",
    "NOR": "Norway",
    "KOR": "South Korea",
    "ESP": "Spain",
    "SWE": "Sweden",
    "SCO": "Scotland",
    "NZL": "New Zealand",
    "JPN": "Japan",
    "AUS": "Australia",
    "AUT": "Austria",
    "CHI": "Chile",
    "IRL": "Ireland",
    "DEN": "Denmark",
    "CAN": "Canada",
    "COL": "Colombia",
    "RSA": "South Africa",
    "FIN": "Finland",
    "GER": "Germany",
    "BEL": "Belgium",
    "TPE": "Chinese Taipei",
    "PHI": "Philippines",
    "ARG": "Argentina",
    "CHN": "China",
    "MEX": "Mexico",
    "ZIM": "Zimbabwe",
    "FRA": "France",
    "NED": "Netherlands",
}

TOUR_NAMES = {"PGA": "PGA TOUR", "EUR": "DP World Tour", "LIV": "LIV Golf", "ASIA": "Japan/Asia"}


def segment_events(segment: int) -> list[int]:
    return [i for i, e in enumerate(SCHEDULE) if e.segment == segment]

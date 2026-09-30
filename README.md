# Fantasy PGA

Fantasy golf in the style of the classic **C64 Football Manager 2**. The rules follow
**PGA TOUR Fantasy Golf** and the golfers are the real players from the world rankings. The
computer plays every round hole by hole, so you pick your team and then watch how it goes.

> Unofficial fan project, not affiliated with or endorsed by the PGA TOUR, the DP World Tour,
> LIV Golf, any golfer, or Commodore.

## How to play

- **The season** is the real 2026 PGA TOUR schedule as used by PGA TOUR Fantasy: 32 tournaments
  from the Sony Open in Hawaii to the TOUR Championship. There are no opposite-field events and
  no team event. The tournaments come in three **segments** (9, 11 and 12 events).
- **Every week** pick **six golfers** from that week's real field. **Four start** each round and
  score points. The other two sit on your **bench**. One starter is your **captain**, who scores
  **double**.
- **Usage limit:** you can start any golfer only **three times per segment**. Picking a golfer for
  the bench doesn't use a start, but starting him in any round of a tournament does. Save some
  stars for the majors!
- **Between rounds** you can swap starters and bench golfers and change your captain. Your six are
  fixed once round 1 starts.
- **Auto-swap:** if a starter misses the cut or withdraws, a bench golfer who's still playing
  takes his place (and the captaincy, if he had it).
- **Your league:** you play against 11 rival managers, each with a different picking style. There
  are three segment titles and the season championship. Rivals' teams stay secret until round 1
  tees off.

### Points

| | |
|---|---|
| Albatross / eagle / birdie / par | +8 / +5 / +2 / +1 |
| Bogey / double bogey or worse | -1 / -3 |
| Hole-in-one bonus | +10 |
| 3+ birdies in a row (once a round) | +3 |
| Bogey-free round | +3 |
| All four rounds under 70 | +5 |
| Finishing bonus | the golfer's FedExCup points ÷ 10 (a win is worth 50 at a regular event, 70 at a signature event or in the playoffs, 75 at a major or THE PLAYERS) |

All the point values are in `src/fantasy_pga/core/data.py`, so they're easy to change.

### The golf

- **Golfers:** the top 200 in the Official World Golf Ranking of 27 September 2026, each with
  the tour they play on (`src/fantasy_pga/core/golfers.json`). A golfer's skill comes from his
  ranking: world No. 1 plays about 3 shots a round better than an average tour player. Form
  (HOT / Good / OK / Poor / Cold) comes from how he's played against that skill in his last
  five events, and it moves his play up or down a little.
- **Fields:** at regular events most PGA TOUR members play, while the stars pick and choose.
  Signature events take the top 50 plus a few more. The playoffs are the top 70, then 50, then 30
  in the game's own FedExCup standings. DP World Tour players turn up at the majors and the
  Scottish Open, and LIV golfers play only the majors.
- **Every hole is played:** each golfer's score on a hole comes from realistic tour odds for
  eagles, birdies, pars and bogeys. Those odds shift with his skill, his form, his luck on the
  day, how hard the course is, the wind, and whether he tees off early or late. Winning scores
  come out like the real thing: about -20 at the John Deere and around level par at a U.S. Open.
- **Cuts, playoffs, withdrawals:** 36-hole cuts use each event's real rule (top 65 and ties,
  top 50 at the Masters, no cut at most signature events). A tie for the lead goes to a
  sudden-death playoff, and now and then a golfer withdraws injured.
- In the first season, each result screen also shows who really won that tournament in 2026.

## Online leagues: play with your friends

Choose **Online League** on the title screen.

1. **The commissioner** (whoever sets it up) chooses *Create a new league*. The game shows a
   six-letter **league code**.
2. **Friends** install the game, choose *Join a league with a code* and type it in. The lobby
   shows everyone as they join.
3. The commissioner decides how many **computer managers** fill the empty places (a league has
   up to 12 teams) and starts the season. Nobody can join after that.
4. **Every week** each manager picks their team on their own computer. Leaving the pick screen
   sends your lineup. The menu shows who has sent one in.
5. **The commissioner plays each round** when the lineups are in (or plays anyway, and anyone
   missing gets their caddie's picks before round 1, or keeps their lineup between rounds).
6. Everyone's game picks up the new round by itself within a few seconds. **WATCH ROUND N!**
   flashes on the menu so you can see it play out live, and then you set your lineup for the
   next round.

Only the commissioner's computer plays the golf. It uploads the whole league after every round
and friends download it, so everyone sees exactly the same tournament. Friends only ever send
their lineups. If the commissioner's internet drops just after a round, the round is kept and
sent next time (or with **Sync Now**).

The league lives in a free [Supabase](https://supabase.com) database set up with
`supabase/schema.sql`, and the game finds it through `src/fantasy_pga/online_config.py`. Supabase
pauses a free project after a week with no activity. If that happens, press **Restore** in the
Supabase dashboard.

## Screens

- **Pick Your Team:** the whole field with world rank, rating, form, betting odds and the starts
  you have left. RETURN or a click picks or drops a golfer. **S** moves him between starters
  and bench, **C** makes him captain, **A** lets your caddie fill the gaps, **M** shows just your
  six and **O** changes the sort order.
- **Live round:** the day unfolds from the first tee time to the last group. You get a live
  leaderboard, your team's points ticking up, a hole view showing your starters' birdies and
  eagles, a news ticker and crowd noise. **SPACE** fast-forwards and **ESC** skips to the end.
- **Leaderboard** and **hole-by-hole scorecards**, with each golfer's fantasy points broken down.
- **League standings** (season, each segment, this week), where you can look at any rival's team.
  Also **Schedule & Results**, **FedExCup standings**, **Golfer stats**, **Records & History** and
  **Scoring & Rules**.
- After the TOUR Championship the season ends. Golfers improve or decline with how they played,
  the world ranking is redone, and the next season starts in Hawaii.

The game autosaves after every round (`~/.fantasy_pga/savegame.json`, and online leagues in
`~/.fantasy_pga/online/`).

Controls: number keys, arrows + RETURN, or the mouse. Right-click or ESC goes back. **F11**
switches fullscreen on and off.

## Install

Download the installer for your computer from the
[latest release](https://github.com/mikehellyer/fantasy-pga/releases/latest):

- **Mac** (Apple Silicon): `Fantasy-PGA-x.y.z-macOS.dmg`. Open it and drag *Fantasy PGA* to
  Applications. The app isn't signed with an Apple developer certificate, so macOS blocks it the
  first time. Go to *System Settings → Privacy & Security* and click **Open Anyway**.
- **Windows**: `Fantasy-PGA-x.y.z-Windows-Setup.exe`. It adds a Start Menu shortcut and, if you
  want one, a desktop icon.
- **Linux** (Pop!_OS / Ubuntu / Debian): `fantasy-pga_x.y.z_amd64.deb`. Install it with
  `sudo apt install ./fantasy-pga_x.y.z_amd64.deb`.

When a new version comes out, the title screen and main menu show **Update available**. Choosing
it downloads the installer for your computer. The game never downloads anything by itself.

## Run from source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python main.py
```

## Project layout

```
src/fantasy_pga/core/   game logic (no pygame): golfers, courses, golf engine, fantasy scoring, season,
                        online leagues (online.py)
src/fantasy_pga/ui/     pygame front end: intro, menus, pick screen, live round, tables, sound
tests/                  pytest tests
tools/                  build.py (installers) and make_icon.py
supabase/schema.sql     the online league database (tables + functions)
```

## Building installers

`tools/build.py` builds the installer for the computer it runs on. Pushing a version tag makes
GitHub Actions build all three, self-test each packaged app and attach them to the release:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

## Tests

```bash
.venv/bin/python -m pytest
```

## Credits

- World rankings from the Official World Golf Ranking (as published on ESPN, 27 Sept 2026).
  The 2026 schedule and winners come from Wikipedia.
- Rules modelled on PGA TOUR Fantasy Golf.
- Inspired by Kevin Toms' *Football Manager* series, and by this game's sister project, SPFL Manager.

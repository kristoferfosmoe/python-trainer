# Mission Mode

Mission Mode is the third tab, **🏆 Missions**, next to **🗺️ Lessons** and
**🎮 Playground**. It turns the simulator into a small FLL-style robot game:
a table with mission models, attachments on the robot's arm motors, a 2:30
match, and a score. Students climb a ladder of challenges that starts with
"push one crate" and ends with a full match that has to work every time.

**Status:** built. The first game, **Harbor Rescue**, has 17 challenges in 7
tiers (§7).

**Lessons and the playground don't change.** Mission Mode is new content, new
code paths, and optional additions that only turn on for a mission. §10 says
how that's enforced and tested.

---

## 1. Goals

| Goal | What it means here |
|---|---|
| Feel like the robot game | Mission models that react (levers flip, loops get carried, gates open), attachments, Home, 2:30 matches, several runs, a score sheet, precision tokens. |
| Get harder step by step | Tiers: one mission, then arms, then carrying, then several missions, then wobble, then matches, then a tournament that must work every time. |
| Arms matter | An arm can hit things, stall, push, lift, hook and drop. `run_until_stalled` is useful, as on a real robot. |
| Keep the simulator's promises | Pure Python, the same result every run, virtual time, run first then replay, in Pyodide and in the CPython lesson checker. |
| Authors write YAML, not code | Mission models are picked from a small set of types and set up with numbers. |

**Not goals (for now):** real rigid-body physics, 3D, copies of real FLL
season missions (their names and artwork belong to FIRST and LEGO), coach
features for Mission Mode, and leaderboards.

## 2. Words

| Word | Meaning |
|---|---|
| **Game** | One robot game, like a season: a field, its mission models, the scoring rules, the attachments on offer and a ladder of challenges. |
| **Field** | A world (the same format as `content/worlds/`) plus mission models. It has a **Home** zone. |
| **Mission model** (or **model**) | A thing on the field that can move or change: a crate, a lever, a loop on a post, a gate. It has a **state**. |
| **Mission** | Something that scores points, like "Lighthouse lit: 20 points". Checked against model states. |
| **Attachment** | A shape on an arm motor (port E or F): a forklift, a sweeper, a pusher. |
| **Match** | Up to 150 seconds, with **one program**. The field isn't reset during a match. |
| **Run** | One trip out from Home and back. In a match with several runs, the program waits in Home for a button press before each one. |
| **Challenge** | One step on the ladder: which models are on the field, the runs and their attachments, the goals, and the stars. |

## 3. What the student sees

- **`#/missions`: the ladder.** Tiers down the page, a tile per challenge
  with its stars. **Challenges unlock one at a time:** a challenge opens
  once the one before it has at least one ★. Locked tiles show 🔒 and can't
  be opened. Only staff can open locked challenges (to test them).
- **`#/missions/<challenge>`: the workspace.** The playground's editor, mat,
  playback bar and console/variables/robot panels, plus:
  - the **stars** to aim for, and the **goals**;
  - the **attachment plan**: one row per run, showing the attachment on each
    port, with a drop-down where the challenge lets the student choose;
  - the **score panel**: the score as it changes during playback, the match
    clock, which run is going, the precision tokens, and after the match the
    score sheet and each try's score;
  - **Next challenge →** once the challenge has a star.
- **Run on your robot** works as for playground challenges (one program).

## 4. Attachments

### 4.1 2.5D

The mat stays a top-down 2D picture. Height is added only where arms need it:
every attachment and every model part has a **footprint** (a convex polygon)
and a **height range** in millimeters. Two things touch when their
footprints overlap **and** their height ranges overlap. So a raised forklift
passes over a crate, a lowered one hits it, and a hook can go into a ring.

### 4.2 Kinds

An attachment's angle **is** its motor's angle (divided by `gears`), so
encoders, `run_target`, `reset_angle` and stall detection work as usual.

| Kind | Turns around | Seen from above | In Harbor Rescue |
|---|---|---|---|
| `lift` | A sideways axle: up and down. 0° is level, positive is up. | A bar that gets shorter as it rises (`length × cos(angle)`), with its tip at `mount_z + length × sin(angle)`. Split into 4 segments, each with its own height. Can have a `hook`. | Forklift (E) |
| `sweep` | An upright axle: across the mat at a fixed height. Positive is clockwise. | A bar that swings around its mount. | Sweeper (F), on the left side |
| `slide` | Nothing: moves in and out by `travel` mm per degree. | A bar that gets longer. | Pusher (E) |

```yaml
# content/missions/harbor/attachments/forklift.yaml
id: forklift
name: Forklift
kind: lift
port: E
summary: Lifts, pushes and hooks. Level is 0°, up is positive (up to 80°), down to -15°.
mount: [110, 0]      # [forward, left] from the point between the wheels, mm
mount_z: 60          # height of the axle
length: 130
width: 40
rest_angle: 0        # the angle it's put on at
min_angle: -15       # mechanical stops
max_angle: 80
hook: {at: 130}      # a hook at the tip
```

**What the motor reads.** When a program starts, each motor reads its
attachment's `rest_angle` (SPIKE motors have absolute encoders), so the
sweeper, which is put on folded, reads 90. A challenge can put an
attachment on at another angle without the motor knowing (`rest: {E: 40}`),
which is what *Find Level* is about. Attachments swapped on **during** a
match go on at their resting angle, but the encoder keeps counting from
where it was, as on a real robot.

### 4.3 The robot

`content/robots/mission-bot.yaml` is the Trainer Bot (same wheels, sensors
and ports) with no stops on E and F (the attachments bring their own) and a
body height of 90 mm. `trainer-bot.yaml` is not changed.

### 4.4 A physics tick with a mission

`Simulation._tick` calls the mission only when `sim.mission` is set, which
only `run_mission` does:

```
1. drive bases, then motors             (as always)
2. move the robot                        (as always: walls and obstacles)
3. mission field step (missions/contacts.py):
   a. arms that turned, with the robot where it was: anything they push
      into either gives way (a block slides, a lever turns, a button
      presses in) or is solid: then that motor's step is undone and it
      stalls ("blocked" event). An arm that comes down onto something
      rests on it instead of shoving it sideways.
   b. if the robot moved: its body and attachments, where it is now.
      Same rules; if something won't give way, the move is undone and the
      wheels stall ("collision" event, so no_collisions still works).
   c. hooks: a hook that goes into a loop (or under a flag's handle) and
      then lifts carries the loop (or raises the flag). Carried loops
      follow their hook; lowering the hook drops them.
   d. models: levers spring back, buttons count presses, links run.
4. motors end their tick; record a frame; then the teammate (§6.3)
```

Contact checks are cheap: a quick distance check first, then bounding
boxes, then a separating-axis test. The worst case (a whole field crowded
around a busy robot for 150 s) simulates in about 2.5 s in CPython.

## 5. Mission models

Authors pick from **six types** and set them up with numbers. Each type is a
Python class in `trainer_sim/missions/models.py`.

| Type | States | What moves it |
|---|---|---|
| `block` | `on_field` | Pushed by the body or an attachment: slides away from the push; stops against walls, obstacles and other models (then the pusher stalls). Doesn't turn. Rectangle (`size`) or round (`r`). |
| `lever` | two names, like `[dark, lit]` | Its bar turns on a hinge (seen from above) when pushed toward `to`, and is solid the other way. A latching lever pushed past its **tipping point** (`tip`, 60% of the way) falls the rest of the way and stays. `spring: true` makes it swing back instead. |
| `button` | `not_pressed` / `pressed` | Pressing into its face (up to `depth` mm) presses it, then it's solid. Counts presses (`presses`). |
| `loop` | `on_post` / `carried` / `dropped` | A ring on a short post (30 mm, so a level arm passes over it). A hook that goes into the ring and lifts above `lift_z` carries it; lowering the hook below `drop_z` drops it there. |
| `flag` | `down` / `raised` | A hook that goes under the handle (`handle_z`) and lifts above `raise_z` raises it, for good. It can have a solid `pole`. |
| `gate` | `closed` / `open` | Solid while closed. Opens (or closes) when a link tells it to. |

Any model can start `hidden: true` and be shown by a link. Every model can
also be `removed` (taken off the field after an interruption).

**Links.** A model can change others when it reaches a state:

```yaml
- id: lighthouse
  type: lever
  hinge: [1100, 1125]
  length: 120
  angle: 90            # hanging down into the top lane
  to: 0
  states: [dark, lit]
  on:
    lit: {open: harbor-gate}      # also: close, show
```

Links to a model that a challenge leaves off its field do nothing; the
checker makes sure every link names a model in the game. (YAML reads a bare
`on:` key as `true`; the loader and the simulator handle that.)

**Why fixed types?** A general "when X touches Y at height Z" rule engine is
more flexible, but hard to check, hard to show in the admin, and easy to get
surprising behavior from. Fixed types keep models predictable and testable;
a new type can be added when a game needs one.

## 6. Scoring and matches

### 6.1 Missions and points

Scoring is checked at the end of the match, from the final field, like a
referee. Each mission's rules are checked top to bottom, and the first one
that matches counts:

```yaml
missions:
  - id: M03
    title: Bring Back the Sample
    score:
      - {when: {model: sample, in_zone: home}, points: 30}
      - {when: {model: sample, state: dropped, in_zone: lab}, points: 25}
      - {when: {model: sample, state: [carried, dropped]}, points: 10}
```

Conditions: `model` (or `models` with `each: true` to score each one),
`state`, `in_zone`, `not_in_zone`, `presses`. A challenge scores only the
missions whose models are on its field (or the ones it lists in `missions`).

**Precision tokens.** The team starts with some (6 in Harbor Rescue), loses
one per interruption, and the ones left are worth points
(`precision_tokens: {start: 6, points: [0, 10, 15, 25, 35, 50, 50]}`).

The score is also recorded as it changes (`score.timeline`), so the score
panel counts up during playback.

### 6.2 One program, several runs

A match is **one program**, the mission runner from lesson 11:

```python
hub.system.set_stop_button(Button.BLUETOOTH)   # so the center button can start runs

for run in [crate_and_bell, sample, buoy_and_flag]:
    while Button.CENTER not in hub.buttons.pressed():
        wait(10)                               # wait in Home for the teammate
    run()
```

Tiers 1–5 have one run, so the program just starts.

### 6.3 The teammate

The simulator plays the teammate at the table (`missions/match.py`), the
same way every time:

- **Run 1:** with several runs, it presses the start button (`CENTER`, or
  the challenge's `start_button`) at 0.5 s.
- **Back in Home:** when the robot has been out, comes back, and stands
  still (wheels and arms) in Home for 0.5 s, the run is over. The teammate
  takes off anything carried (in Home, so it counts there), puts the robot on
  the next run's start spot, swaps the attachments (`handling_time`, 5 s),
  and presses the button.
- **A run that does nothing:** a robot that never leaves Home and sits still
  for 3 s has finished its run too.
- **Stuck outside Home:** in a match with several runs, a robot standing
  still outside Home for 3 s is an **interruption**: a precision token is
  lost, anything it carries is `removed`, and the teammate carries on as
  above.
- **The end:** the match ends when the program ends (and the robot has
  settled) or at the time limit. A robot outside Home then is one more
  interruption.

The teammate only does what a real one can, so real mistakes happen here
too: the gyro and the encoders keep counting when the robot is picked up
and attachments are swapped (*Fresh Start* is about that), and without
`set_stop_button(...)` the first press of the center button stops the
program.

### 6.4 Works every time

A challenge can set `seeds: [1, 2, 3]` (with `realism: "on"`): the match is
played once per seed, and a star only counts if **every** try reaches it. The
trace shown is the first try's, plus each try's score. Stars:

- `stars: [140, 170, 200]`: one star per score reached by every try, as long
  as every goal passes on every try;
- no `stars`: three stars for passing every goal.

The first star is the pass, and it's what unlocks the next challenge.

### 6.5 Goals

Every goal type from lessons works (`end_in_zone`, `no_collisions`,
`must_use`, `max_calls`, `min_calls`...), plus:

| Goal | Example |
|---|---|
| `mission_done` | `{type: mission_done, mission: M02, points: 20}` (points is optional: any points) |
| `min_score` | `{type: min_score, points: 50}` (precision tokens count) |
| `model_state` | `{type: model_state, model: flag, state: raised}` |
| `model_in_zone` | `{type: model_in_zone, model: sample, zone: lab}` |

A challenge with `stars` also gets "Score at least N points", and one with
several seeds gets "Works every time: all N tries".

## 7. Harbor Rescue

The table is laid out in lanes that start in Home (x 0–420, y 0–760):

| Lane | What's there |
|---|---|
| 1 (y 150) | the bell at the far end |
| 2 (y 330) | the crate, and the yellow dock beyond it |
| 3 (y 520) | the sample on its post, and the green lab beyond it |
| middle (y 700) | a black line, the buoy hanging down on the left, the flag at the far end |
| top (y 1000) | the lighthouse lever hanging into the lane, the harbor gate, the barrel, the orange warehouse |

Seven missions, 155 points plus 50 for precision tokens (205 at most).

| Tier | Challenges | New skill |
|---|---|---|
| 1 🟢 First Missions | Crate to the Dock · Ring the Bell (twice) · There and Back | Distances, backing up, coming home |
| 2 🦾 Arms | Raise the Flag (forklift) · Flip the Buoy (sweeper) · Find Level (homing with `run_until_stalled`) | Arm motors, `run_target`, stalls, `reset_angle` |
| 3 🪝 Carry and Deliver | Bring Back the Sample · Sample to the Lab | Hooks, lifting, dropping in the right place |
| 4 🔗 Combos | Open the Gate (the lighthouse opens it, then the barrel) · Buoy and Flag (two attachments, a function per mission) | Linked missions, functions |
| 5 🧭 Navigation (wobble on, 3 tries) | Straight to the Flag (gyro) · Steady Hands (gyro, small ring) · Follow the Line (no gyro allowed) | `use_gyro`, proportional line following |
| 6 🏁 Matches | Press to Go (two runs) · Fresh Start (reset between runs) · Pick Your Attachments (three runs, choose, 100/125/145 points) | Mission runner, resetting, strategy |
| 7 🏆 Tournament | Tournament: every mission, four runs, 2:30, wobble, 3 tries (140/170/200 points) | Everything, reliably |

Every challenge's solution is checked to earn three stars on every try, and
every starter to run without errors and earn none.

## 8. The trace

Lessons and the playground get exactly the trace they always did. A mission
run adds one key, `mission`:

```jsonc
"mission": {
  "initial": {"crate": {"state": "on_field", "hidden": false, "x": 750, "y": 330}, ...},
  "changes": [[frame, "crate", {"state": "on_field", "hidden": false, "x": 912.4, "y": 330}], ...],
  "arms":    {"E": [0, 0.5, 1.0, ...], "F": [null, ...]},        // attachment angles per frame
  "mounts":  [[0, "E", "forklift"], [1220, "E", null], [1221, "E", "pusher"]],
  "attachments": {"forklift": {...}, "pusher": {...}},             // for drawing
  "runs":    [{"run": 1, "start": 500, "end": 24340, "ended": "home", "attachments": {"E": "pusher"}}, ...],
  "home":    "home",
  "score":   {"total": 205, "missions": [{"id": "M01", "title": "...", "points": 20}, ...],
              "tokens": 6, "token_start": 6, "token_points": 50, "timeline": [[t, total], ...]},
  "stars": 3, "thresholds": [140, 170, 200],
  "seeds": [{"seed": 1, "score": 205, "passed": true}, ...]
}
```

Model changes are only recorded when something changes. New event types:
`blocked` (an arm hit something), `state` (a model changed state), `pressed`,
`interruption`, `run_end` and `teammate` (a button press or a pick-up). Field
events are stamped with physics time, and a mission's events are sorted.

## 9. Where things live

| Part | Where |
|---|---|
| Content | `content/missions/harbor/`: `game.yaml` (tiers, field, models, missions, tokens), `attachments/*.yaml`, `challenges/*.yaml` (ladder order is file-name order); `content/robots/mission-bot.yaml` |
| Simulator | `sim/src/trainer_sim/missions/`: `geometry.py`, `attachments.py`, `models.py`, `contacts.py` (the field and the contact step), `scoring.py` (missions, tokens, goals), `match.py` (the teammate, seeds, stars, `run_mission`). Hooks: `Simulation.mission` and `runner.run_simulation`. |
| Checker | `sim/src/trainer_content/missions.py` loads and checks games; `trainer_content.check` also takes `mission_game` / `mission_challenge` requests, so admin saves run in the sandboxed checker, like lessons. |
| Backend | `backend/missions/`: `MissionGame`, `MissionChallenge`, `MissionProgress` (best stars and score; only goes up), the API, and admin YAML editors. `import_content` loads and checks the games too. |
| Frontend | `pages/MissionsPage.tsx` (the ladder), `pages/MissionPage.tsx` (the workspace and score panel), `missions.ts` (locks, attachment picks, reading a trace at a moment), `render/drawMissions.ts` (models and attachments), `runner.runMission` in the worker. |

API:

```
GET /api/missions                              games, tiers, challenges; your stars; unlocked (null for guests)
GET /api/missions/challenges/{slug}            a challenge and its game (403 while locked)
PUT /api/missions/challenges/{slug}/progress   {stars, score}: kept only if better (403 while locked)
PUT /api/drafts, POST /api/attempts            key mission/<challenge>
GET /api/me/state                              now also {missions: {slug: {stars, best_score}}}
POST /api/me/import                            now also takes a guest's mission stars (in ladder order)
```

Locks are worked out on the server for signed-in students. Guests' stars
live in their browser, so their locks are worked out there (and the server
sends any challenge to a guest). Pass/fail is decided in the browser, so a
determined student could fake a star; that's fine for a learning tool.
Solutions are only sent to coaches, mentors and staff, as for lessons.

## 10. Keeping lessons and the playground unchanged

| Risk | How it's handled |
|---|---|
| Shared simulator code changes behavior | The mission steps only run when `Simulation.mission` is set, which only `run_mission` does. `sim/tests/test_unchanged.py` runs all 131 programs in the lessons and playground and compares their traces with fingerprints saved **before** Mission Mode was written. |
| The trace changes | Only mission runs get the `mission` key. |
| Content | No existing file in `content/` was edited. |
| The web app | Shared pieces (`MatView`, `drawMat`, the worker) got optional additions that are off unless a mission passes them. The browser tests still run every lesson and playground solution. |
| Progress data | Missions have their own table and the `mission/` key prefix. |

## 11. Tests

- `sim/tests/test_missions.py`: attachments, stalls, pushing, levers,
  buttons, hooks, scoring, the teammate, interruptions, seeds, mistakes in
  game files, speed.
- `sim/tests/test_mission_content.py`: every challenge in `content/missions/`.
- `sim/tests/test_unchanged.py`: lessons and the playground run exactly as
  before.
- `backend/tests/test_missions.py`: import, the API, locks, stars, guests,
  drafts and attempts, the admin.
- `frontend/src/missions.test.ts`: locks, attachment picks, reading a trace.
- `frontend/tests/e2e/missions.spec.ts`: the ladder and its locks, and all
  17 challenges played in order in the browser's Python.

## 12. Decisions

| Question | Decision |
|---|---|
| Runs as separate programs, or one program? | **One program**, with a button press in Home before each run; the simulator plays the teammate. |
| Locked or open ladder? | **Locked:** each challenge unlocks when the one before it has a star. Staff can open everything. |
| Coach input? | **Not in v1.** Staff write games in the admin or in `content/missions/`. |
| Leaderboards? | **No.** |
| General rule engine or fixed model types? | **Fixed types** (§5). |
| What the motor reads at the start | The attachment's resting angle (absolute encoders). Swaps during a match don't reset it. |

## 13. Later

- Load on the arm: a heavy piece slowing or stalling a lift arm.
- The distance sensor seeing mission models (today it sees walls and field
  obstacles).
- More games, and a visual field editor.

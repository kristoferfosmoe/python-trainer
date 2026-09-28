# Mission Mode: Design (draft)

Mission Mode is a third tab next to **🗺️ Lessons** and **🎮 Playground**. It
turns the simulator into a small FLL-style robot game: a table with mission
models, attachments on the robot's arm motors, a 2:30 match, and a score.
Students climb a ladder of challenges that start with "push one block" and
end with a full match of several runs.

This is a design, not a finished feature. Nothing described here exists yet.
§12 lists the decisions still open.

**Hard rule: lessons and the playground don't change.** Everything below is
new content, new code paths, or optional additions that only turn on when a
world or robot asks for them. §10 explains how that's enforced and tested.

---

## 1. Goals

| Goal | What it means here |
|---|---|
| Feel like the robot game | Mission models that react (levers flip, loops get carried, gates open), attachments, home area, 2:30 matches, several runs, a score sheet. |
| Get harder step by step | A ladder of tiers: one mission, then arms, then carrying, then several missions, then full matches that must work every time. |
| Arms matter | An arm can hit things, stall, push, lift, hook and drop. `run_until_stalled` becomes useful, as on a real robot. |
| Keep the simulator's promises | Pure Python, same result every run, virtual time, run first then replay, works in Pyodide and in the CPython lesson checker. |
| Authors write YAML, not code | Mission models are picked from a small set of types and set up with numbers. |

**Not goals (for now):** real rigid-body physics, 3D rendering, copies of real
FLL season missions (their names and artwork belong to FIRST and LEGO, see
§4.4 of the architecture doc), head-to-head play between teams.

## 2. Words

| Word | Meaning |
|---|---|
| **Game** | One robot game, like a season: a field, its mission models, the scoring rules and the attachments on offer. |
| **Field** | A world (the same format as `content/worlds/`) plus mission models. |
| **Mission model** (or **model**) | A thing on the field that can be moved or changed: a lever, a block, a loop on a post, a gate. It has a **state**. |
| **Mission** | Something that scores points, like "Lever flipped: 20 points". Checked against model states. |
| **Attachment** | A shape bolted onto an arm motor (port E or F): a lift arm, a sweeper, a hook, a pusher. |
| **Run** | One program, started with the robot in Home. |
| **Match** | 150 seconds of runs. The field isn't reset between runs. |
| **Challenge** | One step on the ladder: which models are on the field, how many runs, what counts as passing, and the stars. |

## 3. What the student sees

```
🗺️ Lessons   🎮 Playground   🏆 Missions        (new tab)
```

- **`#/missions`: the ladder.** Tiers down the page, challenges left to right,
  1–3 ⭐ on each. A tier unlocks when the student has at least one star on
  every challenge of the tier before it. (Coaches and staff see everything
  unlocked.)
- **`#/missions/<challenge>`: the workspace.** It reuses the playground's
  pieces (editor, mat, playback bar, console and variables panels) and adds:
  - **Run tabs** (`Run 1`, `Run 2`, …) when the challenge has more than one
    run. Each run is its own program.
  - **An attachment picker** per run: a small card for each attachment the
    challenge allows, with a picture and the port it goes on.
  - **A score panel**: every mission with its points, ticked off as it scores
    during playback; the running total; precision tokens; the match clock.
  - **Stars** after the run: bronze, silver and gold score targets.
- **Run on your robot** still works for each run's program. Attachments are
  up to the team to build.

## 4. Simulating attachments

### 4.1 The approach: 2.5D

The mat is top-down 2D today, and it stays that way. We add **height** only
where arms need it:

- Every attachment and every model part has a **footprint** on the mat (a
  polygon or circle) and a **height range** `[z_low, z_high]` in millimeters
  above the mat.
- Two things touch when their footprints overlap **and** their height ranges
  overlap.

That's enough for "the lift arm passes over the block when it's up and hits
it when it's down", "the hook goes under the loop and lifts it", and "the
sweeper knocks the lever", without a 3D engine.

### 4.2 Attachment kinds

An attachment is fixed to a motor's output. Its angle **is** the motor's
angle (times a gear ratio, if it has one), so encoders, `run_target`,
`reset_angle` and stall detection all work as they do today.

| Kind | Turns around | Looks like (top-down) | Real example |
|---|---|---|---|
| `lift` | A sideways axle (arm goes up and down) | A bar whose length on the mat is `length × cos(angle)` and whose tip height is `mount_z + length × sin(angle)` | Forklift, lift arm, hook arm |
| `sweep` | An upright axle (arm swings across the mat) | A bar that swings around the mount point, at a fixed height | Side sweeper, flipper |
| `slide` | Nothing: moves in and out (rack and pinion) | A bar that sticks out further as the motor turns | Pusher, poker |

Every attachment can also have:

- **`hook`**: a point on the bar that can catch a loop (see `loop` models).
- **`tray`**: an area on the robot that carries pieces while they're in it
  (a passive basket; no motor needed, so it can also be on the robot itself).
- **`gears`**: the gear ratio between motor and attachment, as in
  `Motor(..., gears=[12, 36])`. The simulator uses the robot file's ratio;
  the student's `gears=` only changes what `angle()` reports, as today.
- **`min_angle` / `max_angle`**: mechanical stops. These already exist on the
  arm ports; an attachment can set its own.

Example attachment file:

```yaml
# content/missions/harbor/attachments/forklift.yaml
id: forklift
name: Forklift
kind: lift
port: E                  # the motor it goes on
mount: [120, 0]          # [forward, left] from the point between the wheels, in mm
mount_z: 60              # height of the axle
length: 110
width: 40                # the bar's width on the mat
angle_zero: 0            # 0° = pointing straight ahead, level
min_angle: -20           # can dip a little below level (the tines touch the mat)
max_angle: 80
hook: {at: 100, z_size: 15}    # a hook near the tip
```

### 4.3 Robots with attachments

A new robot file, `content/robots/mission-bot.yaml`. It's the Trainer Bot
(same wheels, sensors and ports, so everything students learned carries
over) with no attachments bolted on. The challenge, or the student's pick in
the attachment picker, adds them for each run.

`trainer-bot.yaml` is not changed.

### 4.4 What happens in a physics tick

Today a tick is: drive bases, then motors, then move the robot (undo the
move if it hits something). Mission Mode adds two steps, and **only runs them
when the field has models or the robot has attachments**:

```
1. drive bases update
2. motors step                         (proposed new arm angles)
3. move the robot                      (proposed new pose)
4. NEW  solve contacts:
        for each attachment and the robot body, against each model part:
          - fixed part   → block: undo that motor's step (or the robot's move),
                           mark it stalled, record a "blocked" event once
          - moving part  → the model reacts (§5); if it can't move any
                           further, block as above
5. NEW  carried pieces follow the hook or tray they're attached to
6. motors end their tick (stall timers, then/Stop handling)
7. record a frame; record model changes (§8)
```

Blocking an arm uses the same `SimMotor.block()` the wheels already use, so
a blocked arm reports `stalled()`, `run_until_stalled` finishes, and a
`run_angle` gives up after half a second of stalling, the same as it does
today at the mechanical stops.

**Contact checks are cheap.** Every part is a rectangle or circle (the
existing `shapes.py` already has overlap tests for both). A field has at
most about 20 models; a tick checks at most 3 moving shapes (body, 2
attachments) against those, and only models within reach of the robot
(a bounding-circle check first).

### 4.5 Load on the arm (later)

A lift arm carrying a piece could turn slower, and a heavy piece could stall
a weak motor. This is a good "why did my arm stop?" lesson, but it's not
needed for the first tiers. Planned as an optional `mass` on pieces and a
`torque` on the attachment: when `mass × arm length` goes over it, the arm's
top speed drops, then it stalls.

## 5. Mission models

Authors pick from a **small fixed set of model types** and set them up with
numbers. Each type is a Python class with a known state, a shape for each
state, and a rule for what contact does to it. This is easier to write,
check and explain to kids than a general-purpose state machine, and new
types can be added as games need them.

### 5.1 Types

| Type | States | What moves it | Example mission |
|---|---|---|---|
| `block` | where it is | Pushed by the body or an attachment. Slides in the direction it's pushed; stops against walls and fixed parts (then the pusher is blocked too). Doesn't turn. | Push the crate into the dock |
| `lever` | angle, and `up`/`down` (or any two names) | Pushed from one side by something at the right height. Turns on its hinge until it reaches its end. Can **latch** (stays down, like a ratchet) or spring back. | Flip the lever to raise the bridge |
| `button` | `pressed` count | Pressed when something presses its face at the right height for long enough. | Press the button twice |
| `loop` | `on_post` / `carried` / `dropped` (+ where) | Caught by a `hook` that goes under it and then lifts above `lift_z`. Follows the hook. Dropped when the hook goes below `drop_z`, at the hook's spot. | Take the sample loop home |
| `piece` | where it is, `carried` | Picked up by a `tray` when it's inside the tray's area (a basket); falls out when the robot drives off without it inside. | Collect the three cargo pieces |
| `gate` | `closed` / `open` | Doesn't react to contact. Opens when another model changes (a `link`). Blocks like a wall while closed. | The gate opens when the lever is down |
| `dispenser` | count left | Pushing its lever `release`s a `piece` or `block` at a spot. | Push the chute to release a ball |
| `flag` | `down` / `up` | A `lever` that only lifts: raised by a lift attachment from below. | Raise the flag |

Walls and plain `obstacles` from the world still work as today.

### 5.2 Links: one model changing another

Any model can say what happens when it changes state:

```yaml
- id: bridge-lever
  type: lever
  ...
  on:
    down: {open: bridge-gate}
```

Actions in v1: `open`, `close`, `release` (a dispenser) and `score_event`
(just for the log). Links are checked once per tick, in file order, and a
model can change at most once per tick, so chains can't loop forever.

### 5.3 A model in YAML

```yaml
# In a game's field file
models:
  - id: bridge-lever
    type: lever
    label: Bridge lever
    hinge: [1180, 640]            # mat position of the hinge
    length: 90                    # from hinge to tip
    width: 20
    z: [30, 70]                   # height range of the handle
    angle: 0                      # start angle, degrees (0 = pointing right)
    turn: [0, 80]                 # it can turn from 0 to 80 degrees
    push_from: west               # which side it can be pushed from
    latch: true                   # once at 80°, it stays
    states: {up: [0, 10], down: [70, 80]}
    on:
      down: {open: bridge-gate}

  - id: sample
    type: loop
    label: Sample
    at: [1600, 900]
    r: 25
    post_z: [0, 80]               # the post it sits on (fixed)
    loop_z: [60, 80]              # the loop's height range
    lift_z: 90                    # a hook must lift it above this to catch it
    drop_z: 20

  - id: cargo
    type: block
    label: Cargo crate
    at: [900, 500]
    size: [80, 80]
    z: [0, 60]
```

### 5.4 Why not a general rule engine?

We considered letting authors write "when X touches Y at height Z, set state
S". It's more flexible, but hard to check for mistakes, hard to show in the
admin, and easy to make models that do surprising things. Fixed types keep
each model's behavior predictable and testable. If authors keep asking for
something the types can't do, we add a type.

## 6. Scoring and matches

### 6.1 Missions and points

Scoring is checked **at the end of the match**, from the final state of the
models, like a referee reading the field. A game's score sheet:

```yaml
missions:
  - id: M01
    title: Raise the bridge
    score:
      - {when: {model: bridge-lever, state: down}, points: 20}
  - id: M02
    title: Bring back the sample
    score:
      - {when: {model: sample, in_zone: home}, points: 30}
      - {when: {model: sample, state: dropped, not_in_zone: home}, points: 10}   # partly done
  - id: M03
    title: Deliver cargo
    score:
      - {when: {model: cargo, in_zone: dock}, points: 15}
      - {when: {model: cargo, touching_zone: dock}, points: 5}
      # Several models can share a rule and score each: {models: [c1, c2, c3], in_zone: dock, points: 10, each: true}
```

A mission's `score` list is checked top to bottom, and the first rule that
matches counts (so "fully in" beats "partly in").

**Live score during playback.** The simulator also writes a `score` event
every time the total changes during the run, so the score panel can tick
missions off as the replay reaches them. The final score is the one that
counts.

### 6.2 Home, runs and interruptions

Real FLL rules, simplified:

- **Home** is a zone in the field file. Every run starts with the whole robot
  inside it, at a start pose the run chooses (from a small list of marked
  spots, or anywhere in Home in later tiers).
- A **run ends** when its program finishes (or errors) **and** the robot has
  stopped moving.
- If the robot ends a run **inside Home**, the next run starts right away (after a
  short handling time for swapping attachments, default 5 s of match time).
- If it ends **outside Home**, that's an **interruption**: the robot is
  picked up and put back in Home, the team loses a **precision token**
  (6 to start, each worth points at the end, per the game's rules), and
  anything it was carrying is removed from the field.
- The match ends at 150 s. A run still going then is stopped (like the time
  limit today).

### 6.3 How a match runs in the simulator

One `Simulation` for the whole match, so the field keeps its state between
runs. For each run:

1. Put the robot at the run's start pose; reset motor angles, gyro and
   drive bases (as a fresh program on a real hub would).
2. Swap in the run's attachments.
3. Run the run's program with fresh Python globals, through the same
   `runner` (tracing, line cost, limits, kid-friendly errors).
4. Let the robot settle (as `finish()` does today), then apply the Home /
   interruption rules.

The trace is one recording for the whole match, with a `runs` list saying
where each run starts and ends (§8), so playback, the scrubber and the score
panel work across runs. A program error in Run 2 stops Run 2 only; later runs
still happen, the way a real team would press on.

**Alternative (see §12):** one program with a hub menu choosing the run, and
scripted button presses in between, like lesson 11's mission runner. This is
closer to how many teams really do it, but it's harder for younger students.
We start with one program per run and can add the menu style as a later
tier.

## 7. The ladder

Each challenge sets which models are on the field (the rest are hidden),
where the robot starts, the runs, the allowed attachments, and what passing
and the stars mean. Challenges within a tier can be done in any order.

| Tier | Theme | Example challenges | New skill |
|---|---|---|---|
| 1. 🟢 First Missions | One model, no arm. Robot starts aimed at it. | Push the crate into the dock · Push the button · Knock over the fence | Driving to a spot, `straight`/`turn` with care |
| 2. 🦾 Arms | One model that needs the arm. | Flip the lever with the sweeper · Raise the flag with the lift arm · Arm homing with `run_until_stalled` | Arm motors, `run_angle`/`run_target`, stalls |
| 3. 🪝 Carry and Deliver | Pick up and bring back. | Take the sample home · Collect cargo in the tray · Drop the loop on the target | Hook heights, order of moves, returning Home |
| 4. 🔗 Combos | Two or three missions in one run; linked models. | Lever opens gate, then drive through · Two deliveries in one trip | Planning a route, functions for each mission |
| 5. 🧭 Navigation | Missions far from Home; realism on. | Follow the line to the crane · Square up on the wall, then turn · Gyro-straight across the field | Line following, wall alignment, gyro; mistakes pile up over distance |
| 6. 🏁 Matches | Several runs, attachment swaps, precision tokens, 150 s. | Two-run match · Pick your attachments · Beat 120 points | Run strategy, time, choosing attachments |
| 7. 🏆 Tournament | Full field, all missions, **must work every time**. | Score 200 on 3 different seeds · Gold: 250 on all 5 | Reliability: code that copes with small errors |

**Stars.** Each challenge has a pass rule and three score targets:

```yaml
stars: [60, 90, 120]        # bronze, silver, gold
```

The first star is the pass. Tier 1–4 challenges can use goals instead of
scores (see below).

**"Works every time" (tier 7).** A challenge can set `seeds: [1, 2, 3]`: the
same code runs once per seed with realism on (so slip and wheel mismatch
differ), and the star is only given if **every** seed reaches it. This is
the real lesson of the robot game: a run that works once isn't a strategy.
Three runs of a 150 s match take about 3–6 s to simulate in Chromium, which
is fine behind a "Running 3 matches…" message.

**Goals still work.** Every existing goal type (`end_in_zone`,
`no_collisions`, `must_use`, `max_calls`…) can be used in mission
challenges. Three new ones:

| Goal type | Example |
|---|---|
| `mission_done` | `{type: mission_done, mission: M01}` (scored any points) |
| `min_score` | `{type: min_score, points: 50}` |
| `model_state` | `{type: model_state, model: bridge-lever, state: down}` |

These live in a new `trainer_sim/missions/` module, not in `goals.py`, so the
goal code lessons use stays as it is (§10).

## 8. Trace additions

Only present when a run has models or attachments; lessons and the
playground get exactly the trace they get today.

```jsonc
{
  // ... everything that's there today ...
  "attachments": {"E": {"id": "forklift", "kind": "lift", ...}},   // geometry, for drawing
  // "motors" (arm angles per frame) is already recorded and drives the attachment drawing.
  "models": {
    "initial": {"bridge-lever": {"angle": 0, "state": "up"}, "cargo": {"x": 900, "y": 500}, ...},
    "changes": [[frame, "cargo", {"x": 912.4, "y": 500}], ...]    // only when something changes
  },
  "runs":  [{"run": 1, "start": 0, "end": 41200, "ended": "home"},
            {"run": 2, "start": 46200, "end": 98800, "ended": "interrupted"}],
  "score": {"total": 85, "missions": [{"id": "M01", "points": 20}, ...],
            "tokens": 5, "timeline": [[t, total], ...]},
  // new event types: "blocked" (an arm hit something), "caught", "dropped",
  // "state" (a model changed state), "interruption", "run_start", "run_end"
}
```

Model changes are stored as a sparse list because most models don't move
most of the time. A block being pushed changes every frame while it's
pushed, which is at most about 50 entries per second of pushing.

## 9. Where things live

### 9.1 Content

```
content/missions/
  harbor/                       # one game (an invented theme; not a real season)
    game.yaml                   # title, summary, field (a world + models), missions, rules
    attachments/
      forklift.yaml
      sweeper.yaml
      hook.yaml
      tray.yaml
    challenges/
      1-01-crate-to-dock.yaml   # tier-index-slug, ordered by file name
      1-02-press-the-button.yaml
      2-01-flip-the-lever.yaml
      ...
content/robots/mission-bot.yaml
```

A challenge file looks like a playground challenge with a few extra keys:

```yaml
id: flip-the-lever
title: Flip the Lever
tier: 2
game: harbor
models: [bridge-lever, bridge-gate]    # the rest of the field's models are hidden
time_limit: 30
runs:
  - start: {x: 200, y: 200, heading: 0}
    attachments: [sweeper]              # fixed for this challenge; or `choose: [sweeper, forklift]`
    starter: |
      ...
    solution: |
      ...
goals:
  - {type: model_state, model: bridge-lever, state: down}
  - {type: no_collisions}
# no `stars`: passing the goals gives all three stars
hints: [...]
```

### 9.2 Simulator

New code goes in `sim/src/trainer_sim/missions/`:

| File | What it does |
|---|---|
| `attachments.py` | Attachment specs, their shape and height for an angle |
| `models.py` | The model types (§5.1) and links |
| `contacts.py` | The contact step (§4.4) |
| `scoring.py` | Missions, precision tokens, stars, the new goals |
| `match.py` | Runs a match: several programs in one `Simulation` (§6.3) |

Changes to existing files are small hooks:

- `sim.py`: `_tick()` calls `self.contacts.step()` if `self.contacts` is set
  (it's `None` for lessons and the playground). The recorder adds the new
  trace keys only when there's something to put in them.
- `runner.py`: a `run_match(...)` next to `run_program(...)`. `run_program`
  itself doesn't change.
- `robot.py`: reads an optional `attachments` list. Robots without it are
  built exactly as today.

### 9.3 Checker

`trainer_content` gets a `check_game()` and `check_mission_challenge()`,
run by pytest, `import_content`, the admin and the checker container, the
same as lessons:

- Every model, zone and attachment a challenge or mission names exists.
- No model overlaps another, a wall, or Home at the start.
- Links only point at models that can take that action.
- Each challenge's solution reaches the gold star on every seed; each
  starter runs without errors and doesn't already pass.

### 9.4 Backend

A new Django app, `missions`, so the curriculum and progress apps keep their
current models:

| Model | Fields |
|---|---|
| `MissionGame` | slug, title, summary, order, published, spec (JSON: field, missions, rules, attachments) |
| `MissionChallenge` | game, slug, tier, order, published, spec (JSON, as in the YAML) |
| `MissionProgress` | user, challenge, best_score, stars, updated_at (only moves up, like lesson progress) |

Saved code and runs reuse the existing `CodeDraft` and `Attempt` tables
with a new key prefix, `mission/<challenge>/<run>`. That needs one change
outside the new app: allowing the `mission/` prefix in
`progress/api.py`'s key check (a one-line change that lessons and the
playground don't see).

API:

```
GET  /api/missions                       games, tiers and challenges; your stars
GET  /api/missions/{slug}                one challenge, with its game's field and attachments
PUT  /api/missions/{slug}/progress       {score, stars}   (kept only if higher)
PUT  /api/drafts                         key mission/<challenge>/<run>   (existing endpoint)
POST /api/attempts                       key mission/<challenge>         (existing endpoint)
```

Solutions are only sent to coaches, mentors and staff, as today. `import_content`
also loads `content/missions/`. The admin gets YAML editors for games and
challenges, with the full check on save.

The coach's student page gets a **Missions** section (stars per challenge,
best score, the code of each run) after the lesson list. The team progress
grid is not changed in v1.

### 9.5 Frontend

- `router.ts`: new routes `#/missions` and `#/missions/<challenge>`.
- `App.tsx`: a **🏆 Missions** link in the main nav. The Lessons and
  Playground links and pages stay as they are.
- New: `pages/MissionsPage.tsx` (the ladder), `components/MissionWorkspace.tsx`
  (run tabs, attachment picker, score panel; built from the same editor,
  mat and playback pieces as `ChallengeWorkspace`), `components/ScorePanel.tsx`.
- `render/drawMat.ts`: new optional drawing for models and attachments,
  used only when the trace has them. Lift arms are drawn shorter as they
  rise (their length on the mat) and lighter the higher they are, so height
  is visible from above. Carried pieces are drawn on the hook or tray.
- The worker gets a `runMatch` message next to `run`.
- Guests keep mission stars in `localStorage`, like playground challenges,
  and they're merged into the account on sign-in.

## 10. Keeping lessons and the playground unchanged

| Risk | How it's avoided |
|---|---|
| Shared simulator code changes behavior | The new tick steps only run when `self.contacts` is set, which only `run_match` does. Every existing test must pass unchanged. |
| Trace changes break playback | New trace keys are only added by `run_match`. A new test runs every existing lesson and playground solution and compares the trace with one saved before Mission Mode (only `sim_version` may differ). |
| Content changes | No existing file in `content/` is edited. New files only. |
| Frontend regressions | Shared components (`MatView`, `drawMat`, panels) get optional props that default to today's behavior. The existing Playwright tests (every lesson and playground solution) must pass unchanged. |
| Progress data | Lessons keep `LessonProgress`; the playground keeps its `playground/` attempts. Mission data uses its own table and prefix. |

## 11. Build order

Each step is a separate PR that ships something testable.

1. **Arms that touch things (simulator only).** Attachment specs, the
   contact step, `block` and `lever` models, the `blocked` event, pytest
   tests for contacts and stalls. No UI.
2. **Drawing.** Models and attachments in `drawMat.ts`; a dev-only page to
   view a field.
3. **Tier 1–2 end to end.** The `missions` app, import, API, the ladder
   page, the workspace for single-run challenges, stars, the score panel,
   and 5–6 challenges.
4. **Carrying.** `loop`, `piece`, hooks and trays; tier 3 challenges.
5. **Links and the full field.** `gate`, `dispenser`, `button`, `flag`,
   links; tiers 4–5.
6. **Matches.** Several runs, Home and interruptions, precision tokens,
   attachment picker; tier 6.
7. **Tournament.** Seeds, "works every time" stars; tier 7. Coach page
   Missions section.
8. **Later:** arm load, hub-menu runs, a visual field editor.

## 12. Open questions

1. **Runs as separate programs or one program with a menu?** This design
   starts with separate programs per run (simpler, one clear file per run)
   and leaves a hub-menu version for later. Real teams do both.
2. **One game or several?** One invented game ("Harbor") is enough to fill
   seven tiers. The format allows more games, such as a coach-made one for
   their team (like team-owned courses).
3. **Should tiers be locked?** This design locks a tier until the one before
   it has a star on every challenge. It could also be "suggested order,
   nothing locked".
4. **Team scores?** A team leaderboard per challenge would be motivating,
   but pass/fail and scores are computed in the browser and can be faked
   (see §8 of the architecture doc). Fine for fun, not for anything that
   matters.
5. **How close to real FLL rules?** Precision tokens, handling time and
   interruptions are simplified here. We could follow a real season's rules
   more closely, but not copy its missions or artwork.

# Python Trainer

A web app that teaches FIRST LEGO League Challenge students to program their
robot in Python using the [Pybricks](https://pybricks.com) API. Students write
real Pybricks code and watch a simulated robot run it on a virtual FLL table.
Code that works here can be pasted into Pybricks for the real robot.

**Status:** Milestones 1 and 2 are done: the simulator, the playground, and
the lesson system with the first four units (12 lessons). Accounts and the
server come next. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the
design and roadmap.

## What's here

| Folder | What it is |
|---|---|
| `sim/` | The robot simulator in Python: a Pybricks-compatible API (`pybricks.*`) plus the physics, sensors and kid-friendly error messages. It runs in the browser through Pyodide. `trainer_content` loads and checks lessons. |
| `frontend/` | The web app: React + TypeScript + Vite. It has the course map, the lesson player, the step-by-step visualizer, quizzes, the CodeMirror editor, the mat renderer and playback. |
| `content/` | The course (`courses/`), the playground challenges, the practice mats (worlds) and the robot, all as YAML files. |
| `docs/` | Architecture and decisions. |

## Run it locally

You need Node 22+ and [uv](https://docs.astral.sh/uv/) (for the Python tests).

```bash
cd frontend
npm install
npm run dev          # open http://localhost:5173
```

The first load takes a few seconds while Python (Pyodide) starts in the browser.

## Tests

```bash
# Simulator: physics, sensors, errors, and every challenge's solution
cd sim && uv run pytest

# Web app: typecheck, unit tests, production build
cd frontend && npm run typecheck && npm test && npm run build

# Browser tests: real Python in Chromium, runs every challenge's solution
cd frontend && npx playwright install chromium && npm run test:e2e
```

If Chromium is already installed somewhere else, set `CHROMIUM_PATH` to its
executable instead of running `playwright install`.

## Writing lessons

Lessons live in `content/courses/fll-python/<unit>/<lesson>.yaml`. Units and
lessons are ordered by file name. A lesson is a list of blocks:

| Block | What it is |
|---|---|
| `text` | Markdown. Python code fences are syntax-highlighted. |
| `example` | Code students can run, change and step through. Add `expect_error: true` to show off a bug. |
| `visualize` | Code that opens in step-by-step mode, showing line counts, loop rounds, True/False notes and variables. |
| `quiz` | Multiple choice. With `check: output`, the tests make sure the right answer really is what the code prints. |
| `challenge` | Editor + robot + goals, like a playground challenge. Leave out `world` for a console-only challenge, or use `ref: <playground-id>` to reuse one. |

The existing lessons are the best templates. The lesson player starts a new
page after each block that isn't text, so write text right before the thing
it introduces.

`cd sim && uv run pytest` checks every lesson:
- Examples run.
- Quiz answers match the real output.
- Goal zones exist.
- Every challenge's solution passes while its starter doesn't.

## Adding a playground challenge

Add a YAML file to `content/challenges/`. The existing ones are good
templates. A challenge names a world from `content/worlds/`, and has
instructions (Markdown), goals, hints, starter code and a solution:

```yaml
id: my-challenge
title: My Challenge
world: practice-field
start: {x: 200, y: 200, heading: 0}   # optional; heading 0 faces right, 90 faces down
time_limit: 30                        # seconds of robot time
realism: off                          # "on" adds wheel slip, uneven wheels and gyro drift
summary: One sentence shown under the title.
instructions: |
  What to do, in **Markdown**.
goals:
  - {type: end_in_zone, zone: garage}
  - {type: must_use, construct: for}
hints:
  - A first nudge.
starter: |
  # code the student starts with
solution: |
  # code that passes every goal
```

`cd sim && uv run pytest` checks every challenge. The solution must pass all of
its goals, and the starter code must run without errors but not already pass.
Goal types and world shapes are documented in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#47-challenge-goals).

# Python Trainer

A web app that teaches FIRST LEGO League Challenge students to program their
robot in Python using the [Pybricks](https://pybricks.com) API. Students write
real Pybricks code and watch a simulated robot run it on a virtual FLL table.
When it works, **🤖 Run on your robot** gets the code ready for
[Pybricks](https://code.pybricks.com), changed to fit the team's real robot.

**Status:** all planned milestones are done:
- the simulator and playground,
- the lesson system with all 12 units (28 lessons, from `print()` to line
  following, proportional control and a mission runner),
- student accounts (username + PIN), teams and saved progress,
- coach tools: team progress, coach-made accounts with printable sign-in
  cards, PIN resets, mentors, and each student's code,
- running lesson code on a real robot through Pybricks,
- lesson editing in the admin,
- deployment to AWS: every merge to `main` is tested, built and deployed
  by itself, with automatic rollback.

Next up: an AI tutor and a friendlier lesson editor. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and
[docs/DEPLOY.md](docs/DEPLOY.md) to put it online.

## What's here

| Folder | What it is |
|---|---|
| `sim/` | The robot simulator in Python: a Pybricks-compatible API (`pybricks.*`) plus the physics, sensors and kid-friendly error messages. It runs in the browser through Pyodide. `trainer_content` loads and checks lessons. |
| `backend/` | Django + Django Ninja: sign-up and sign-in, teams and join codes, lessons served from the database, progress and saved code, and the admin where teachers edit lessons. |
| `frontend/` | The web app: React + TypeScript + Vite. It has the course map, the lesson player, the step-by-step visualizer, quizzes, the CodeMirror editor, the mat renderer and playback. |
| `content/` | The course (`courses/`), the playground challenges, the practice mats (worlds) and the robot, all as YAML files. They're imported into the database. |
| `deploy/` | Docker images, Docker Compose (Caddy + Django + the lesson checker + PostgreSQL), the deploy and backup scripts, and `aws/`: the CloudFormation stack for AWS. |
| `docs/` | Architecture, decisions and the deployment guide. |

## Run it locally

You need Node 22+ and [uv](https://docs.astral.sh/uv/). Run the backend and
the web app in two terminals:

```bash
# Terminal 1: the backend on http://127.0.0.1:8000
cd backend
uv run python manage.py migrate
uv run python manage.py import_content        # load the lessons (checks them first)
uv run python manage.py createsuperuser       # for /admin (optional)
uv run python manage.py create_coach coach_kim --team "Brick Builders"   # a coach (optional)
uv run python manage.py runserver

# Terminal 2: the web app on http://localhost:5173 (it forwards /api and /admin to Django)
cd frontend
npm install
npm run dev
```

The first load takes a few seconds while Python (Pyodide) starts in the
browser. Locally the backend uses SQLite. In production it uses PostgreSQL.

## Tests

```bash
# Simulator: physics, sensors, errors, and every lesson and challenge
cd sim && uv run pytest

# Backend: accounts, PIN protection, teams and coach tools, lessons, progress, admin checks
cd backend && uv run pytest

# Web app: typecheck, unit tests (including the Pybricks export), production build
cd frontend && npm run typecheck && npm test && npm run build

# Browser tests: starts Django and Vite, runs real Python in Chromium,
# runs every lesson and playground solution, and walks through the coach tools
cd frontend && npx playwright install chromium && npm run test:e2e
```

If Chromium is already installed somewhere else, set `CHROMIUM_PATH` to its
executable instead of running `playwright install`.

## For coaches

Sign in with your coach account and open **👥 Teams**:

- **Make a team.** Its join code is on the team page. Students type it when
  they sign up (or on their account page). A team can have up to 100
  members (students, mentors and coaches).
- **Or make the accounts yourself**: type one nickname per line (first names
  or initials, no last names) and print the sign-in cards. PINs are shown
  only once, but you can make a new PIN for anyone at any time (you'll type
  your password first).
- **Shared computers**: coaches are signed out after 2 hours without use.
  Anyone who opens the app still signed in from an earlier visit is asked
  "Not you?".
- **See progress**: a row per student and a column per unit. Click a student
  to see their lessons and the code for every challenge they've tried.
- **Mentors**: make an older student a mentor. Mentors can see everyone's
  work and the answers, but can't change accounts.
- **Our robot**: describe your team's real robot (which port each motor and
  sensor uses, and the wheel sizes). When students press **🤖 Run on your
  robot**, their code is changed to fit it and they get the steps to run it in
  Pybricks.

## Writing lessons

There are two ways:

- **In the admin** (`/admin/` → Lessons), no git needed. Saving checks the
  lesson first. On the server, lesson code runs in its own walled-off
  `checker` container, never next to the database.
- **As files** in `content/courses/fll-python/<unit>/<lesson>.yaml`. They're
  loaded with `import_content`, which runs on every deploy. Units and lessons
  are ordered by file name.

A lesson is a list of blocks:

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

`cd sim && uv run pytest` (and the admin, on save) checks every lesson:
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

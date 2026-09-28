"""Running a match: one program, one or more runs, and the teammate.

A match is one program, started with the robot in Home. In a challenge with
several runs, the program waits in Home for a button press before each run
(lesson 11's mission runner), and the simulator plays the teammate:

- Before run 1 it presses the start button at 0.5 s.
- When the robot has come back and stopped in Home for 0.5 s, the run is
  over: it takes off anything the robot carried, puts the robot on the next
  run's start spot, swaps the attachments (the handling time passes), and
  presses the button.
- If the robot stops outside Home for 3 s, that's an interruption: the team
  loses a precision token, and whatever the robot carried is taken off the
  field. Then the teammate carries on as above.
- A robot outside Home when the program ends counts as an interruption too.

The teammate never resets anything on the hub: the gyro and the motor
encoders keep counting, as on a real robot.
"""

import json
import time

from ..robot import RobotSpec
from ..runner import run_simulation
from ..shapes import ShapeError
from ..sim import Simulation
from .attachments import AttachmentSpec
from .contacts import MissionField
from .scoring import Scorer

FIRST_PRESS_MS = 500
PRESS_MS = 200
HOME_STILL_MS = 500
STUCK_MS = 3000
DEFAULT_HANDLING_S = 5
START_BUTTONS = ("CENTER", "LEFT", "RIGHT")


class Teammate:
    def __init__(self, sim, field, scorer, runs, home, button, handling_ms):
        self.sim = sim
        self.field = field
        self.scorer = scorer
        self.runs = runs  # [(start pose, {port: AttachmentSpec})]
        self.home = home
        self.button = button
        self.handling_ms = handling_ms
        self.interrupts_while_running = len(runs) > 1
        self.index = 0
        self.active = True
        self.done = False
        self.waiting_until = 0.0
        self.left_home = False
        self.still_since = None
        self.log = []

    def begin(self):
        self._mount(0)
        start = 0.0
        if len(self.runs) > 1:
            start = FIRST_PRESS_MS
            self._press(start)
            self.waiting_until = start
        self._log_start(start)

    def _mount(self, index):
        for port in list(self.field.mounts):
            self.field.unmount(port)
        for spec in self.runs[index][1].values():
            self.field.mount(spec)

    def _press(self, at):
        self.sim.button_presses.append({"at": at, "button": self.button, "duration": PRESS_MS})
        self.field.event("teammate", action="press", button=self.button, run=self.index + 1, at=at)

    def _log_start(self, t):
        self.log.append({
            "run": self.index + 1, "start": round(t, 1), "end": None, "ended": None,
            "attachments": {port: spec.id for port, spec in self.runs[self.index][1].items()},
        })

    def _robot_moving(self):
        sim = self.sim
        return sim.speed != 0 or sim.turn_rate != 0 or any(m.moving for m in sim.motors.values())

    def in_home(self):
        return self.home.contains(self.sim.x, self.sim.y)

    def after_tick(self):
        if self.done or not self.active:
            return
        t = self.sim.phys_t
        if t < self.waiting_until:
            return
        in_home = self.in_home()
        if not in_home:
            self.left_home = True
        if self._robot_moving():
            self.still_since = None
            return
        if self.still_since is None:
            self.still_since = t
        still = t - self.still_since
        if in_home and self.left_home and still >= HOME_STILL_MS:
            self._end_run("home")
        elif not in_home and self.interrupts_while_running and still >= STUCK_MS:
            self._end_run("interrupted")

    def _interrupt(self):
        self.field.remove_carried()
        self.scorer.lose_token()
        self.field.event("interruption", run=self.index + 1, tokens=self.scorer.tokens)

    def _end_run(self, how):
        t = self.sim.phys_t
        self.log[-1].update(end=round(t, 1), ended=how)
        self.field.event("run_end", run=self.index + 1, how=how)
        if how == "interrupted":
            self._interrupt()
        if self.index + 1 >= len(self.runs):
            self.done = True
            if how == "interrupted":
                self._place(self.runs[self.index][0])
            return
        self.index += 1
        for port in list(self.field.mounts):
            self.field.unmount(port)  # anything still carried is taken off, in Home
        self._place(self.runs[self.index][0])
        self._mount(self.index)
        press = t + self.handling_ms
        self._press(press)
        self.waiting_until = press
        self.left_home = False
        self.still_since = None
        self._log_start(press)

    def _place(self, pose):
        sim = self.sim
        sim.x, sim.y, sim.heading = pose
        sim.speed = sim.turn_rate = 0.0
        self.field.event("teammate", action="place", run=self.index + 1)

    def end_match(self):
        """After the program ends and the robot has settled."""
        run = self.log[-1]
        if run["end"] is None:
            home = self.in_home()
            run.update(end=round(self.sim.now, 1), ended="home" if home else "interrupted")
            if not home:
                self._interrupt()


class Mission:
    """What Simulation._tick calls when there's a mission (sim.mission)."""

    def __init__(self, field, teammate, scorer):
        self.field = field
        self.teammate = teammate
        self.scorer = scorer

    def step(self, old_pose, dt):
        self.field.step(old_pose, dt)

    def after_tick(self):
        self.teammate.after_tick()
        if self.field.record():
            self.scorer.update()


# --- Putting a game and a challenge together -------------------------------------------

def _pose(spec, fallback):
    spec = spec or {}
    return (
        float(spec.get("x", fallback[0])),
        float(spec.get("y", fallback[1])),
        float(spec.get("heading", fallback[2])),
    )


def resolve(game, challenge, choices=None):
    """Everything one match needs, from a game, one of its challenges, and the student's attachment picks."""
    if not isinstance(game, dict) or not isinstance(challenge, dict):
        raise ShapeError("a mission run needs a game and a challenge")
    field = game.get("field")
    if not isinstance(field, dict):
        raise ShapeError(f"game {game.get('id', '?')} needs a 'field' (a world)")
    home = game.get("home", "home")
    zone_ids = {z.get("id") for z in field.get("zones", [])}
    if home not in zone_ids:
        raise ShapeError(f"game {game.get('id', '?')}: the field has no Home zone called '{home}'")
    attachments = {}
    for spec in game.get("attachments", []):
        parsed = AttachmentSpec(spec)
        attachments[parsed.id] = parsed

    wanted = challenge.get("models")
    all_models = game.get("models", [])
    known = {m.get("id") for m in all_models if isinstance(m, dict)}
    for model in all_models:
        on = model.get("on") if isinstance(model, dict) else None
        for actions in (on.values() if isinstance(on, dict) else []):
            for action in actions if isinstance(actions, list) else [actions]:
                for target in (action.values() if isinstance(action, dict) else []):
                    if target not in known:
                        raise ShapeError(f"model {model.get('id')}: a link names a model that isn't in the game: '{target}'")
    if wanted is not None:
        for name in wanted:
            if name not in known:
                raise ShapeError(f"challenge {challenge.get('id', '?')}: the game has no model '{name}'")
        models = [m for m in all_models if m.get("id") in wanted]
    else:
        models = list(all_models)

    world_start = field.get("start", {})
    default_start = (float(world_start.get("x", 200)), float(world_start.get("y", 200)),
                     float(world_start.get("heading", 0)))
    run_specs = challenge.get("runs") or [{}]
    choices = choices or []
    runs = []
    for index, run in enumerate(run_specs):
        start = _pose(run.get("start"), default_start)
        picked = {}
        fixed = run.get("attachments") or {}
        choose = run.get("choose") or {}
        chosen = choices[index] if index < len(choices) and isinstance(choices[index], dict) else {}
        for port, name in fixed.items():
            picked[port] = name
        for port, options in choose.items():
            options = options if isinstance(options, list) else [options]
            if not options:
                raise ShapeError(f"challenge {challenge.get('id', '?')}: run {index + 1} has nothing to choose on port {port}")
            pick = chosen.get(port, options[0])
            picked[port] = pick if pick in options else options[0]
        specs = {}
        for port, name in picked.items():
            if name not in attachments:
                raise ShapeError(f"challenge {challenge.get('id', '?')}: no attachment called '{name}'")
            spec = attachments[name]
            if spec.port != port:
                raise ShapeError(f"attachment {name} goes on port {spec.port}, not {port}")
            specs[port] = spec
        runs.append((start, specs))

    button = challenge.get("start_button", "CENTER")
    if button not in START_BUTTONS:
        raise ShapeError(f"start_button must be one of {', '.join(START_BUTTONS)}")
    seeds = challenge.get("seeds") or [1]
    return {
        "field": field,
        "home": home,
        "models": models,
        "robot": game.get("robot"),
        "runs": runs,
        "missions": game.get("missions", []),
        "only_missions": challenge.get("missions"),
        "tokens": game.get("precision_tokens"),
        "button": button,
        "handling_ms": float(challenge.get("handling_time", DEFAULT_HANDLING_S)) * 1000,
        "options": {
            "time_limit": challenge.get("time_limit", 150),
            "realism": challenge.get("realism", "off"),
        },
        "seeds": [int(s) for s in seeds],
        "goals": challenge.get("goals") or [],
        "stars": challenge.get("stars"),
    }


def _one_match(code, setup, seed):
    started = time.perf_counter()
    options = dict(setup["options"], seed=seed, start=dict(zip(("x", "y", "heading"), setup["runs"][0][0])))
    robot = RobotSpec(setup["robot"])
    sim = Simulation(setup["field"], robot, options)
    body_height = (setup["robot"].get("body") or {}).get("height", 90)
    field = MissionField(sim, setup["models"], body_height)
    scorer = Scorer(setup["missions"], setup["tokens"], field, sim.world, setup["only_missions"])
    teammate = Teammate(sim, field, scorer, setup["runs"], sim.world.zone_at(setup["home"]),
                        setup["button"], setup["handling_ms"])
    field.listeners.append(scorer.update)
    sim.mission = Mission(field, teammate, scorer)
    teammate.begin()
    scorer.update()
    field.record()

    def program_ended():
        teammate.active = False

    def check(recording, end):
        # The robot has settled; now the referee looks at the field.
        teammate.end_match()
        field.record()
        scorer.update()
        return scorer.check_goals(setup["goals"], recording, end, code, sim)

    result = run_simulation(sim, code, options, check, started, program_ended)
    # Field events are stamped with physics time, which can run ahead of the program's clock.
    result["events"].sort(key=lambda e: e["t"])
    result["mission"] = {
        **field.to_dict(),
        "attachments": {spec.id: spec.to_dict() for _, specs in setup["runs"] for spec in specs.values()},
        "runs": teammate.log,
        "score": scorer.to_dict(),
        "home": setup["home"],
    }
    return result


def stars_for(thresholds, results):
    """Stars (0-3) for a set of seed results: every seed must pass its goals and reach the score."""
    all_pass = all(all(g["passed"] for g in r["goals"]) for r in results)
    if not all_pass:
        return 0
    if not thresholds:
        return 3
    worst = min(r["mission"]["score"]["total"] for r in results)
    return sum(1 for t in thresholds if worst >= t)


def run_mission(code, game, challenge, choices=None):
    """Run a match (once per seed) and return the first seed's trace, with the stars."""
    setup = resolve(game, challenge, choices)
    results = [_one_match(code, setup, seed) for seed in setup["seeds"]]
    thresholds = setup["stars"]
    if thresholds is not None:
        if not isinstance(thresholds, list) or len(thresholds) != 3 or thresholds != sorted(thresholds):
            raise ShapeError("stars must be three scores, lowest first, like [60, 90, 120]")
    trace = results[0]
    goals = trace["goals"]
    if thresholds:
        worst = min(r["mission"]["score"]["total"] for r in results)
        goals.append({
            "id": "first-star", "type": "min_score", "label": f"Score at least {thresholds[0]} points",
            "passed": worst >= thresholds[0], "detail": "" if worst >= thresholds[0] else f"You scored {worst}.",
        })
    if len(results) > 1:
        passing = sum(1 for r in results if all(g["passed"] for g in r["goals"]) and (
            not thresholds or r["mission"]["score"]["total"] >= thresholds[0]))
        goals.append({
            "id": "every-time", "type": "every_time",
            "label": f"Works every time: all {len(results)} tries",
            "passed": passing == len(results),
            "detail": "" if passing == len(results) else f"It worked {passing} of {len(results)} times.",
        })
    stars = stars_for(thresholds, results)
    trace["mission"]["stars"] = stars
    trace["mission"]["thresholds"] = thresholds
    trace["mission"]["seeds"] = [
        {"seed": seed, "score": r["mission"]["score"]["total"], "passed": all(g["passed"] for g in r["goals"])}
        for seed, r in zip(setup["seeds"], results)
    ]
    return trace


def run_mission_json(payload):
    """JSON in, JSON out: the entry point the browser's Web Worker calls."""
    request = json.loads(payload)
    result = run_mission(request["code"], request["game"], request["challenge"], request.get("choices"))
    return json.dumps(result, separators=(",", ":"))

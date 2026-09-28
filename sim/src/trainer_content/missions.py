"""Load and check Mission Mode games: content/missions/<game>/.

    content/missions/harbor/
      game.yaml            title, tiers, field (a world), home, models, missions, precision tokens
      attachments/*.yaml   the attachments on offer
      challenges/*.yaml    the ladder, in file-name order (each names its tier)

The checker runs every challenge: its solution must earn all three stars
(on every seed), and its starter must run without errors and earn none.
"""

import pathlib

import yaml

from trainer_sim.missions import run_mission
from trainer_sim.missions.match import resolve
from trainer_sim.missions.scoring import MISSION_GOALS
from trainer_sim.robot import RobotSpec
from trainer_sim.shapes import ShapeError
from trainer_sim.world import World

from . import GOAL_TYPES, ContentError

CHALLENGE_KEYS = ("id", "title", "tier", "summary", "instructions", "starter")
ALL_GOALS = GOAL_TYPES + MISSION_GOALS


def _load(path):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ContentError(f"{path}: expected a YAML dictionary")
    return data


def load_game(game_dir, robots_dir):
    """A game with its attachments, challenges and robot filled in."""
    game_dir = pathlib.Path(game_dir)
    game = _load(game_dir / "game.yaml")
    for model in game.get("models", []):
        if isinstance(model, dict) and True in model:
            model["on"] = model.pop(True)  # YAML reads a bare `on:` key as True
    robot_id = game.get("robot", "mission-bot")
    robot_path = pathlib.Path(robots_dir) / f"{robot_id}.yaml"
    if not robot_path.exists():
        raise ContentError(f"{game_dir.name}: no robot file {robot_path.name}")
    game["robot"] = _load(robot_path)
    game["attachments"] = [_load(p) for p in sorted((game_dir / "attachments").glob("*.yaml"))]
    game["source"] = str(game_dir)
    game["challenges"] = []
    for path in sorted((game_dir / "challenges").glob("*.yaml")):
        challenge = _load(path)
        challenge["source"] = str(path)
        game["challenges"].append(challenge)
    return game


def load_games(root):
    """Every game under content/missions/, in folder-name order."""
    root = pathlib.Path(root)
    missions = root / "missions"
    if not missions.exists():
        return []
    return [load_game(d, root / "robots") for d in sorted(missions.iterdir()) if (d / "game.yaml").exists()]


def game_spec(game):
    """The game as the simulator and the browser need it (without its challenges)."""
    return {key: value for key, value in game.items() if key not in ("challenges", "source")}


class MissionChecker:
    """Finds problems in a game and its challenges. `run=False` skips running code."""

    def __init__(self, run=True):
        self.run_code = run

    def check_game(self, game):
        name = game.get("id", "?")
        problems = []
        for key in ("id", "title", "field", "tiers"):
            if not game.get(key):
                problems.append(f"game {name}: missing '{key}'")
        if problems:
            return problems
        try:
            World(game["field"])
            RobotSpec(game["robot"])
        except (ShapeError, KeyError, TypeError, ValueError) as error:
            return [f"game {name}: {error}"]
        tiers = [t.get("id") for t in game["tiers"] if isinstance(t, dict)]
        if len(tiers) != len(game["tiers"]) or len(set(tiers)) != len(tiers):
            problems.append(f"game {name}: every tier needs its own 'id'")
        # Every model and mission together: load them on a challenge with the whole field.
        try:
            resolve(game_spec(game), {"id": "whole-field"})
            self._run_whole_field(game)
        except (ShapeError, KeyError, TypeError, ValueError) as error:
            problems.append(f"game {name}: {error}")
        ids = set()
        for challenge in game.get("challenges", []):
            cid = challenge.get("id")
            if cid in ids:
                problems.append(f"game {name}: two challenges are called '{cid}'")
            ids.add(cid)
            problems += self.check_challenge(game, challenge)
        return problems

    @staticmethod
    def _run_whole_field(game):
        run_mission("pass\n", game_spec(game), {"id": "whole-field", "time_limit": 1})

    def check_challenge(self, game, challenge):
        where = f"{game.get('id')}/{challenge.get('id', challenge.get('source', '?'))}"
        problems = []
        for key in CHALLENGE_KEYS:
            if challenge.get(key) in (None, ""):
                problems.append(f"{where}: missing '{key}'")
        if challenge.get("tier") not in [t.get("id") for t in game.get("tiers", [])]:
            problems.append(f"{where}: tier {challenge.get('tier')!r} isn't one of the game's tiers")
        goals = challenge.get("goals") or []
        for goal in goals:
            if goal.get("type") not in ALL_GOALS:
                problems.append(f"{where}: unknown goal type '{goal.get('type')}'")
        stars = challenge.get("stars")
        if stars is not None and (not isinstance(stars, list) or len(stars) != 3 or stars != sorted(stars)):
            problems.append(f"{where}: stars must be three scores, lowest first")
        if not goals and stars is None:
            problems.append(f"{where}: a challenge needs goals, stars, or both")
        if not challenge.get("solution"):
            problems.append(f"{where}: needs a 'solution'")
        if problems:
            return problems

        spec = game_spec(game)
        try:
            setup = resolve(spec, challenge)
        except (ShapeError, KeyError, TypeError, ValueError) as error:
            return [f"{where}: {error}"]
        problems += self._check_starts(where, spec, setup)
        if problems or not self.run_code:
            return problems
        try:
            solved = run_mission(challenge["solution"], spec, challenge, self._best_choices(challenge))
            starter = run_mission(challenge["starter"], spec, challenge)
        except (ShapeError, KeyError, TypeError, ValueError) as error:
            return [f"{where}: {error}"]
        if solved["mission"]["stars"] != 3:
            failed = [g["label"] for g in solved["goals"] if not g["passed"]]
            seeds = ", ".join(f"seed {s['seed']}: {s['score']}" for s in solved["mission"]["seeds"])
            problems.append(f"{where}: the solution gets {solved['mission']['stars']} stars "
                            f"(failed: {', '.join(failed) or 'none'}; scores {seeds})")
        if starter["end"]["reason"] == "error":
            problems.append(f"{where}: starter code has an error: {starter['end']['error']['python_message']}")
        elif starter["mission"]["stars"] > 0:
            problems.append(f"{where}: the starter code already earns a star")
        return problems

    @staticmethod
    def _best_choices(challenge):
        """The attachments the solution was written for (`solution_attachments`), if the challenge lets you choose."""
        return challenge.get("solution_attachments")

    @staticmethod
    def _check_starts(where, spec, setup):
        problems = []
        world = World(spec["field"])
        home = world.zone_at(setup["home"])
        robot = RobotSpec(spec["robot"])
        from trainer_sim.missions.geometry import overlap
        from trainer_sim.missions.models import make_model

        parts = [part for m in setup["models"] for part in make_model(m).parts()]
        for index, (start, _) in enumerate(setup["runs"]):
            outline = robot.outline(*start)
            if not home.contains(start[0], start[1]):
                problems.append(f"{where}: run {index + 1} starts outside Home")
            if world.collision(outline):
                problems.append(f"{where}: run {index + 1} starts touching {world.collision(outline)}")
            for part in parts:
                if part.z[0] < 90 and overlap(outline, part.poly):
                    problems.append(f"{where}: run {index + 1} starts touching {part.model.label}")
        return problems

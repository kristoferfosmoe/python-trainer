"""Every world, robot and challenge in content/ must load and work.

Each challenge's solution must pass all of its goals, and its starter code
must run without errors. This keeps teachers' lessons honest.
"""

import pytest

from conftest import CONTENT, load
from trainer_sim.goals import check_goals
from trainer_sim.robot import RobotSpec
from trainer_sim.runner import run_program
from trainer_sim.world import World

WORLDS = sorted(p.stem for p in (CONTENT / "worlds").glob("*.yaml"))
CHALLENGES = sorted(p.stem for p in (CONTENT / "challenges").glob("*.yaml"))


@pytest.mark.parametrize("name", WORLDS)
def test_world_loads_and_start_is_clear(name, robot):
    world = World(load("worlds", name))
    spec = RobotSpec(robot)
    x, y, h = world.start
    assert world.collision(spec.outline(x, y, h)) is None


def _options(challenge):
    options = {"time_limit": challenge.get("time_limit", 150), "realism": challenge.get("realism", "off")}
    if "start" in challenge:
        options["start"] = challenge["start"]
    return options


@pytest.mark.parametrize("name", CHALLENGES)
def test_challenge(name, robot):
    challenge = load("challenges", name)
    for key in ("id", "title", "world", "summary", "instructions", "starter"):
        assert challenge.get(key), f"{name} is missing '{key}'"
    world_spec = load("worlds", challenge["world"])
    world = World(world_spec)
    if "start" in challenge:
        s = challenge["start"]
        assert world.collision(RobotSpec(robot).outline(s["x"], s["y"], s.get("heading", 0))) is None

    starter = run_program(challenge["starter"], world_spec, robot, _options(challenge), challenge.get("goals"))
    assert starter["end"]["reason"] in ("finished", "time_limit"), starter["end"]

    goals = challenge.get("goals")
    if not goals:
        return
    assert challenge.get("solution"), f"{name} has goals but no solution"
    solved = run_program(challenge["solution"], world_spec, robot, _options(challenge), goals)
    failed = [g for g in solved["goals"] if not g["passed"]]
    assert not failed, failed
    assert not all(g["passed"] for g in starter["goals"]), "the starter code already passes every goal"


def test_goal_zones_exist():
    for name in CHALLENGES:
        challenge = load("challenges", name)
        world = World(load("worlds", challenge["world"]))
        for goal in challenge.get("goals", []):
            for zone in goal.get("zones", []) + ([goal["zone"]] if "zone" in goal else []):
                world.zone_at(zone)


def test_unknown_goal_type_is_rejected(robot):
    with pytest.raises(ValueError):
        check_goals([{"type": "fly"}], World({}), {"frames": {"x": [], "y": []}}, {"reason": "finished"}, "", None)

import pathlib
import textwrap

import pytest
import yaml

from trainer_sim.runner import run_program

CONTENT = pathlib.Path(__file__).resolve().parents[2] / "content"

SETUP = """\
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor, ColorSensor, UltrasonicSensor
from pybricks.parameters import Port, Direction, Stop, Color
from pybricks.robotics import DriveBase
from pybricks.tools import wait, StopWatch

hub = PrimeHub()
left_motor = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right_motor = Motor(Port.B)
drive_base = DriveBase(left_motor, right_motor, wheel_diameter=56, axle_track=112)
"""
SETUP_LINES = SETUP.count("\n")


def load(kind, name):
    return yaml.safe_load((CONTENT / kind / f"{name}.yaml").read_text())


@pytest.fixture(scope="session")
def robot():
    return load("robots", "trainer-bot")


@pytest.fixture(scope="session")
def open_world():
    """An empty mat with the robot in the middle, far from walls."""
    return {"id": "open", "size": [3000, 3000], "start": {"x": 1500, "y": 1500, "heading": 0}}


@pytest.fixture
def run(robot, open_world):
    def _run(code, world=None, setup=True, goals=None, **options):
        source = (SETUP if setup else "") + textwrap.dedent(code).lstrip("\n")
        return run_program(source, world or open_world, robot, options, goals)
    return _run


def final_pose(result):
    f = result["frames"]
    return f["x"][-1], f["y"][-1], f["heading"][-1]


def printed(result):
    return [p["text"] for p in result["prints"]]

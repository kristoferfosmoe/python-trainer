"""Mission Mode: attachments that touch things, mission models, scoring and matches."""

import copy
import textwrap

import pytest

from conftest import load
from trainer_sim.missions import run_mission
from trainer_sim.runner import run_program
from trainer_sim.shapes import ShapeError

SETUP = """\
from pybricks.hubs import PrimeHub
from pybricks.pupdevices import Motor
from pybricks.parameters import Port, Direction, Button, Stop
from pybricks.robotics import DriveBase
from pybricks.tools import wait

hub = PrimeHub()
drive_base = DriveBase(Motor(Port.A, Direction.COUNTERCLOCKWISE), Motor(Port.B), wheel_diameter=56, axle_track=112)
arm = Motor(Port.E)
"""

# The robot starts at (200, 250) facing right (+x). Its front is 110 mm ahead
# of its center. A level forklift reaches 110 + 130 = 240 mm ahead.
GAME = {
    "id": "test-game",
    "home": "home",
    "field": {
        "id": "test-field",
        "size": [2362, 1143],
        "start": {"x": 200, "y": 250, "heading": 0},
        "zones": [
            {"id": "home", "label": "Home", "type": "rect", "x": 0, "y": 0, "w": 420, "h": 500},
            {"id": "dock", "label": "Dock", "type": "rect", "x": 900, "y": 150, "w": 250, "h": 200},
        ],
        "obstacles": [{"label": "pillar", "type": "rect", "x": 1400, "y": 900, "w": 100, "h": 100}],
    },
    "attachments": [
        {"id": "forklift", "kind": "lift", "port": "E", "mount": [110, 0], "mount_z": 60, "length": 130,
         "width": 40, "min_angle": -15, "max_angle": 80, "hook": True},
        {"id": "sweeper", "kind": "sweep", "port": "E", "mount": [80, -70], "direction": 90, "length": 150,
         "width": 20, "z": [20, 60], "min_angle": -90, "max_angle": 90},
        {"id": "pusher", "kind": "slide", "port": "F", "mount": [110, 40], "length": 20, "width": 30,
         "travel": 1, "min_angle": 0, "max_angle": 100},
    ],
    "models": [
        {"id": "crate", "type": "block", "label": "Crate", "at": [700, 250], "size": [80, 80], "z": [0, 60]},
        {"id": "lever", "type": "lever", "label": "Lever", "hinge": [600, 700], "length": 120, "angle": 180,
         "to": 270, "z": [20, 70], "states": ["up", "down"], "on": {"down": [{"open": "gate"}, {"show": "prize"}]}},
        {"id": "gate", "type": "gate", "label": "Gate", "at": [1000, 700], "size": [20, 300]},
        {"id": "prize", "type": "block", "label": "Prize", "at": [1200, 1000], "size": [60, 60], "hidden": True},
        {"id": "bell", "type": "button", "label": "Bell", "at": [800, 250], "size": [40, 60], "z": [0, 80]},
        {"id": "sample", "type": "loop", "label": "Sample", "at": [700, 250]},
        {"id": "flag", "type": "flag", "label": "Flag", "at": [700, 250], "size": [60, 60], "handle_z": 70,
         "raise_z": 120},
    ],
    "missions": [
        {"id": "M01", "title": "Crate to the Dock", "score": [{"when": {"model": "crate", "in_zone": "dock"}, "points": 20}]},
        {"id": "M02", "title": "Open the Gate", "score": [{"when": {"model": "lever", "state": "down"}, "points": 15}]},
        {"id": "M03", "title": "Sample Home", "score": [
            {"when": {"model": "sample", "in_zone": "home"}, "points": 30},
            {"when": {"model": "sample", "state": ["carried", "dropped"]}, "points": 10},
        ]},
        {"id": "M04", "title": "Ring the Bell", "score": [{"when": {"model": "bell", "presses": 2}, "points": 10}]},
        {"id": "M05", "title": "Flag", "score": [{"when": {"model": "flag", "state": "raised"}, "points": 10}]},
    ],
    "precision_tokens": {"start": 3, "points": [0, 5, 10, 20]},
}


@pytest.fixture(scope="module")
def game():
    spec = copy.deepcopy(GAME)
    spec["robot"] = load("robots", "mission-bot")
    return spec


def play(game, code, models, runs=None, setup=True, **challenge):
    challenge = {"id": "test", "models": models, "runs": runs or [{"attachments": {"E": "forklift"}}], **challenge}
    source = (SETUP if setup else "") + textwrap.dedent(code).lstrip("\n")
    return run_mission(source, game, challenge, challenge.pop("choices", None))


def final(result, model_id):
    """The model's last recorded state."""
    state = dict(result["mission"]["initial"][model_id])
    for _, mid, snap in result["mission"]["changes"]:
        if mid == model_id:
            state = snap
    return state


def events(result, kind):
    return [e for e in result["events"] if e["type"] == kind]


def no_error(result):
    assert result["end"]["reason"] == "finished", result["end"]


# --- Lessons and the playground are untouched ----------------------------------------------

def test_lesson_runs_have_no_mission_section(run):
    result = run("drive_base.straight(100)")
    assert "mission" not in result


# --- Attachments -------------------------------------------------------------------------------

def test_level_forklift_pushes_a_crate_into_the_dock(game):
    result = play(game, "drive_base.straight(650)\ndrive_base.straight(-650)\n", ["crate"],
                  goals=[{"type": "mission_done", "mission": "M01"}])
    no_error(result)
    crate = final(result, "crate")
    # The fork reaches 240 mm ahead of the robot's center: 200 + 650 + 240 + 40.
    assert crate["x"] == pytest.approx(1130, abs=3)
    assert crate["y"] == pytest.approx(250, abs=1)
    assert all(g["passed"] for g in result["goals"])
    assert result["mission"]["score"]["missions"][0]["points"] == 20
    assert events(result, "collision") == []


def test_raised_forklift_passes_over_the_crate(game):
    result = play(game, """
        arm.run_target(300, 70)
        drive_base.straight(230)   # the fork's tip is past the crate's front, the body isn't
        """, ["crate"])
    no_error(result)
    assert final(result, "crate")["x"] == 700


def test_lowering_the_arm_onto_a_crate_stalls_it(game):
    result = play(game, """
        arm.run_target(300, 70)
        drive_base.straight(250)
        angle = arm.run_until_stalled(-200)
        print(angle)
        """, ["crate"])
    no_error(result)
    stopped_at = int(result["prints"][0]["text"])
    assert stopped_at > 0  # it came to rest on top of the crate, above level
    assert events(result, "blocked")[0]["what"] == "Crate"
    assert final(result, "crate")["x"] == 700


def test_arm_mechanical_stops_follow_the_attachment(game):
    result = play(game, "print(arm.run_until_stalled(500))\nprint(arm.run_until_stalled(-500))\n", [])
    assert [p["text"] for p in result["prints"]] == ["80", "-15"]


def test_gears_scale_the_attachment_angle(game):
    geared = copy.deepcopy(game)
    geared["attachments"][0]["gears"] = 3
    result = play(geared, "arm.run_angle(500, 90)\nprint(arm.angle())\n", [])
    assert result["prints"][0]["text"] == "90"
    assert result["mission"]["arms"]["E"][-1] == pytest.approx(30, abs=0.5)


def test_crate_stops_at_the_wall_and_so_does_the_robot(game):
    result = play(game, "drive_base.straight(1900)\n", ["crate"], time_limit=20)
    crate = final(result, "crate")
    assert 2362 - 40 - 1 <= crate["x"] <= 2362 - 40
    hits = events(result, "collision")
    assert hits and hits[0]["what"] == "Crate"


def test_attachment_hits_a_field_obstacle(game):
    result = play(game, """
        drive_base.turn(-90)
        arm.run_target(200, 0)
        drive_base.straight(200)
        """, [], runs=[{"start": {"x": 1450, "y": 600, "heading": 0}, "attachments": {"E": "forklift"}}])
    # The fork (reaching 240 mm) hits the pillar (y from 900) before the body would.
    assert final_pose_y(result) < 900 - 240 + 5
    assert events(result, "collision")[0]["what"] == "pillar"


def points(result, mission_id):
    return next(m["points"] for m in result["mission"]["score"]["missions"] if m["id"] == mission_id)


def final_pose_y(result):
    return result["frames"]["y"][-1]


def test_slide_attachment_pushes_out(game):
    result = play(game, """
        drive_base.straight(420)
        wait(200)
        arm2 = Motor(Port.F)
        arm2.run_angle(300, 100)
        """, ["crate"], runs=[{"attachments": {"F": "pusher"}}])
    no_error(result)
    # Mounted 40 mm to the left of center, 30 mm wide: it catches the crate's edge and pushes it.
    assert final(result, "crate")["x"] > 700 + 50


# --- Levers, gates, links -----------------------------------------------------------------------

# Facing up (+y), with the sweeper held out to the right: driving past, it
# catches the lever's bar (pointing left from its hinge) and pushes it up.
LEVER_CODE = "drive_base.straight(500)\n"
LEVER_RUN = [{"start": {"x": 330, "y": 250, "heading": -90}, "attachments": {"E": "sweeper"}}]


def test_sweeper_flips_the_lever_and_it_opens_the_gate(game):
    result = play(game, LEVER_CODE, ["lever", "gate", "prize"], runs=LEVER_RUN,
        goals=[{"type": "model_state", "model": "lever", "state": "down"}])
    no_error(result)
    assert final(result, "lever")["state"] == "down"
    assert final(result, "lever")["angle"] == 270  # pushed past its tipping point, it fell the rest of the way
    assert final(result, "gate")["state"] == "open"
    assert final(result, "prize")["hidden"] is False
    states = [(e["model"], e["state"]) for e in events(result, "state")]
    assert ("lever", "down") in states and ("gate", "open") in states
    assert all(g["passed"] for g in result["goals"])


def test_a_latched_lever_stays_down(game):
    result = play(game, LEVER_CODE + "drive_base.straight(-500)\n", ["lever", "gate"], runs=LEVER_RUN)
    assert final(result, "lever")["state"] == "down"


def test_a_spring_lever_goes_back(game):
    springy = copy.deepcopy(game)
    springy["models"][1].update(latch=False, spring=True)
    result = play(springy, LEVER_CODE + "wait(1500)\n", ["lever", "gate"], runs=LEVER_RUN)
    assert max(snap["angle"] for _, mid, snap in result["mission"]["changes"] if mid == "lever") > 230
    assert final(result, "lever")["angle"] == pytest.approx(180, abs=1)
    assert final(result, "lever")["state"] == "up"


def test_driving_into_a_closed_gate_is_a_collision(game):
    result = play(game, "drive_base.straight(800)\n", ["gate"], runs=[{
        "start": {"x": 400, "y": 700, "heading": 0}, "attachments": {}}],
        goals=[{"type": "no_collisions"}])
    assert events(result, "collision")[0]["what"] == "Gate"
    assert not result["goals"][1]["passed"]


# --- Buttons --------------------------------------------------------------------------------------

def test_button_counts_each_press(game):
    result = play(game, """
        for i in range(2):
            drive_base.straight(500)      # the bell's face is 470 mm ahead of the robot's front
            drive_base.straight(-100)
        """, ["bell"], runs=[{"attachments": {}}])
    no_error(result)
    bell = final(result, "bell")
    assert bell["presses"] == 2
    assert len(events(result, "pressed")) == 2
    assert points(result, "M04") == 10


def test_button_is_solid_after_its_travel(game):
    result = play(game, "drive_base.straight(600)\n", ["bell"], runs=[{"attachments": {}}])
    x = result["frames"]["x"][-1]
    # Bell face at x = 780; the robot's front (x + 110) can press in 15 mm at most.
    assert 780 - 110 <= x <= 780 + 15 - 110 + 2
    assert final(result, "bell")["presses"] == 1


# --- Hooks: loops and flags ------------------------------------------------------------------------

SAMPLE_CODE = textwrap.dedent("""
    arm.run_target(300, 0)
    drive_base.straight(260)      # hook (the fork's tip) goes into the loop
    arm.run_target(300, 45)       # lift: the loop comes off its post
    drive_base.straight(-260)
    """)


def test_hook_lifts_a_loop_and_brings_it_home(game):
    result = play(game, SAMPLE_CODE, ["sample"])
    no_error(result)
    sample = final(result, "sample")
    assert sample["state"] == "carried"
    assert sample["x"] < 420  # in Home, still on the hook
    assert points(result, "M03") == 30


def test_lowering_the_hook_drops_the_loop(game):
    result = play(game, SAMPLE_CODE + "drive_base.straight(600)\narm.run_target(300, -15)\n", ["sample"])
    sample = final(result, "sample")
    assert sample["state"] == "dropped"
    assert sample["x"] == pytest.approx(200 + 600 + 240 * 0.97, abs=15)
    assert points(result, "M03") == 10


def test_hook_that_starts_above_the_loop_doesnt_catch_it(game):
    result = play(game, "arm.run_target(300, 30)\ndrive_base.straight(260)\narm.run_target(300, 70)\n", ["sample"])
    assert final(result, "sample")["state"] == "on_post"


def test_hook_raises_a_flag(game):
    result = play(game, "drive_base.straight(260)\narm.run_target(300, 60)\n", ["flag"])
    assert final(result, "flag")["state"] == "raised"


# --- Scoring --------------------------------------------------------------------------------------

def test_score_has_missions_and_precision_tokens(game):
    result = play(game, "drive_base.straight(650)\ndrive_base.straight(-650)\n", ["crate"])
    score = result["mission"]["score"]
    assert [m["id"] for m in score["missions"]] == ["M01"]  # only missions whose models are on the field
    assert score["tokens"] == 3 and score["token_points"] == 20
    assert score["total"] == 40
    assert score["timeline"][0] == [0.0, 20]
    assert score["timeline"][-1][1] == 40


def test_min_score_and_stars(game):
    code = "drive_base.straight(650)\ndrive_base.straight(-650)\n"
    result = play(game, code, ["crate"], stars=[30, 40, 50])
    assert result["mission"]["stars"] == 2
    assert result["goals"][-1]["id"] == "first-star" and result["goals"][-1]["passed"]
    result = play(game, "pass\n", ["crate"], stars=[30, 40, 50])
    assert result["mission"]["stars"] == 0


def test_goals_only_challenge_gets_three_stars(game):
    code = "drive_base.straight(650)\ndrive_base.straight(-650)\n"
    result = play(game, code, ["crate"], goals=[{"type": "mission_done", "mission": "M01"}])
    assert result["mission"]["stars"] == 3
    result = play(game, "raise ValueError('oops')\n", ["crate"], goals=[{"type": "mission_done", "mission": "M01"}])
    assert result["mission"]["stars"] == 0


def test_each_model_scores(game):
    many = copy.deepcopy(game)
    many["models"] += [
        {"id": "box-1", "type": "block", "at": [1000, 200], "size": [40, 40]},
        {"id": "box-2", "type": "block", "at": [1000, 300], "size": [40, 40]},
        {"id": "box-3", "type": "block", "at": [100, 900], "size": [40, 40]},
    ]
    many["missions"].append({"id": "M06", "title": "Boxes", "score": [
        {"when": {"models": ["box-1", "box-2", "box-3"], "in_zone": "dock"}, "points": 5, "each": True}]})
    result = play(many, "pass\n", ["box-1", "box-2", "box-3"])
    assert result["mission"]["score"]["missions"][0]["points"] == 10


# --- Matches: the teammate -----------------------------------------------------------------------

RUNNER = """
    hub.system.set_stop_button(Button.BLUETOOTH)

    def run_1():
        drive_base.straight(650)
        drive_base.straight(-650)

    def run_2():
        print("run 2 arm at", arm.angle())
        drive_base.straight(100)
        drive_base.straight(-100)

    for run in [run_1, run_2]:
        while Button.CENTER not in hub.buttons.pressed():
            wait(10)
        run()
    """

TWO_RUNS = [
    {"start": {"x": 200, "y": 250, "heading": 0}, "attachments": {"E": "forklift"}},
    {"start": {"x": 200, "y": 150, "heading": 0}, "attachments": {"E": "sweeper"}},
]


def test_two_runs_with_a_button_press_and_an_attachment_swap(game):
    result = play(game, RUNNER, ["crate"], runs=TWO_RUNS, handling_time=4)
    no_error(result)
    runs = result["mission"]["runs"]
    assert [r["ended"] for r in runs] == ["home", "home"]
    assert runs[0]["start"] == 500
    assert runs[1]["attachments"] == {"E": "sweeper"}
    # The second run starts after the handling time.
    assert runs[1]["start"] == pytest.approx(runs[0]["end"] + 4000, abs=1)
    presses = [e for e in events(result, "teammate") if e["action"] == "press"]
    assert [p["run"] for p in presses] == [1, 2]
    mounts = result["mission"]["mounts"]
    assert [m[2] for m in mounts] == ["forklift", None, "sweeper"]
    assert result["mission"]["score"]["tokens"] == 3


def test_a_run_that_does_nothing_is_over_after_3_seconds(game):
    code = RUNNER.replace("""    def run_1():
        drive_base.straight(650)
        drive_base.straight(-650)""", """    def run_1():
        wait(300)""")
    result = play(game, code, ["crate"], runs=TWO_RUNS)
    no_error(result)
    runs = result["mission"]["runs"]
    assert runs[0]["end"] == pytest.approx(500 + 3000, abs=50)
    assert runs[1]["ended"] == "home"


def test_encoders_keep_counting_across_a_swap(game):
    code = RUNNER.replace("def run_1():\n", "def run_1():\n        arm.run_angle(300, 40)\n")
    result = play(game, code, ["crate"], runs=TWO_RUNS)
    # The sweeper went on at its resting angle, but the motor still says 40.
    assert result["prints"][0]["text"] == "run 2 arm at 40"
    arms = result["mission"]["arms"]["E"]
    assert arms[-1] == pytest.approx(0, abs=0.5)


def test_gyro_keeps_counting_when_the_robot_is_placed(game):
    runs = [dict(TWO_RUNS[0]), {"start": {"x": 200, "y": 150, "heading": 90}, "attachments": {}}]
    code = RUNNER.replace('print("run 2 arm at", arm.angle())', 'print(hub.imu.heading())')
    result = play(game, code, ["crate"], runs=runs)
    assert result["prints"][0]["text"] == "90.0"


def test_without_a_new_stop_button_the_first_press_stops_the_program(game):
    code = RUNNER.replace("hub.system.set_stop_button(Button.BLUETOOTH)", "")
    result = play(game, code, ["crate"], runs=TWO_RUNS)
    assert result["end"]["reason"] == "error"
    assert result["end"]["error"]["type"] == "SystemExit"


def test_stuck_outside_home_is_an_interruption(game):
    code = RUNNER.replace("drive_base.straight(-650)", "wait(4000)")
    result = play(game, code + "print('done')\n", ["crate"], runs=TWO_RUNS)
    runs = result["mission"]["runs"]
    assert runs[0]["ended"] == "interrupted"
    assert result["mission"]["score"]["tokens"] == 2
    assert len(events(result, "interruption")) == 1
    # The teammate put the robot on run 2's spot, and the match carried on.
    assert runs[1]["ended"] == "home"
    assert [p["text"] for p in result["prints"]][-1] == "done"


def test_interruption_takes_away_what_the_robot_carries(game):
    code = ("hub.system.set_stop_button(Button.BLUETOOTH)\n"
            "while Button.CENTER not in hub.buttons.pressed():\n    wait(10)\n"
            + SAMPLE_CODE.replace("drive_base.straight(-260)", "wait(4000)"))
    runs = [TWO_RUNS[0], {"start": {"x": 200, "y": 150, "heading": 0}, "attachments": {"E": "forklift"}}]
    result = play(game, code, ["sample"], runs=runs)
    assert final(result, "sample")["state"] == "removed"
    assert points(result, "M03") == 0


def test_ending_outside_home_costs_a_token(game):
    result = play(game, "drive_base.straight(650)\n", ["crate"])
    assert result["mission"]["runs"][0]["ended"] == "interrupted"
    assert result["mission"]["score"]["tokens"] == 2


def test_single_run_matches_have_no_button_presses(game):
    result = play(game, "wait(5000)\ndrive_base.straight(300)\nwait(4000)\ndrive_base.straight(-300)\n", ["crate"])
    no_error(result)
    assert events(result, "teammate") == []
    assert result["mission"]["runs"][0]["ended"] == "home"


def test_attachment_choice(game):
    runs = [{"choose": {"E": ["forklift", "sweeper"]}}]
    result = play(game, "pass\n", [], runs=runs, choices=[{"E": "sweeper"}])
    assert result["mission"]["runs"][0]["attachments"] == {"E": "sweeper"}
    result = play(game, "pass\n", [], runs=runs, choices=[{"E": "something-else"}])
    assert result["mission"]["runs"][0]["attachments"] == {"E": "forklift"}


# --- Works every time ----------------------------------------------------------------------------

def test_every_seed_must_pass(game):
    code = "drive_base.straight(650)\ndrive_base.straight(-650)\n"
    result = play(game, code, ["crate"], seeds=[1, 2, 3], realism="on", stars=[20, 30, 40])
    seeds = result["mission"]["seeds"]
    assert [s["seed"] for s in seeds] == [1, 2, 3]
    assert result["goals"][-1]["id"] == "every-time"
    assert result["mission"]["stars"] == (3 if all(s["score"] >= 40 for s in seeds) else result["mission"]["stars"])


def test_a_plan_that_only_works_sometimes_loses_the_star(game):
    # Wheel slip changes where the crate ends up a little on each try. Put the
    # dock's edge in the middle of those spots: some tries score, some don't.
    code = "drive_base.straight(420)\ndrive_base.straight(-420)\n"
    slippy = {"slip": 0.08, "wheel_mismatch": 0.05}
    spots = sorted(final(play(game, code, ["crate"], seeds=[s], realism=slippy), "crate")["x"] for s in range(1, 9))
    assert spots[-1] - spots[0] > 1
    close_call = copy.deepcopy(game)
    close_call["field"]["zones"][1].update(x=(spots[3] + spots[4]) / 2, w=300)
    results = [play(close_call, code, ["crate"], seeds=[s], realism=slippy) for s in range(1, 9)]
    assert {points(r, "M01") for r in results} == {0, 20}
    together = play(close_call, code, ["crate"], seeds=list(range(1, 9)), realism=slippy,
                    goals=[{"type": "mission_done", "mission": "M01"}])
    assert together["mission"]["stars"] == 0
    assert together["goals"][-1]["id"] == "every-time" and not together["goals"][-1]["passed"]
    assert "of 8 times" in together["goals"][-1]["detail"]


# --- Mistakes in game files ------------------------------------------------------------------------

@pytest.mark.parametrize("change, message", [
    (lambda g: g["models"].append({"id": "x", "type": "spaceship"}), "unknown type"),
    (lambda g: g["models"].append({"id": "crate", "type": "block", "at": [1, 1], "size": [1, 1]}), "two models"),
    (lambda g: g["models"][1]["on"].update(down={"open": "nowhere"}), "isn't in the game"),
    (lambda g: g["models"][1]["on"].update(down={"explode": "gate"}), "unknown action"),
    (lambda g: g["missions"][0]["score"][0]["when"].update(in_zone="moon"), "no zone"),
    (lambda g: g["missions"][1]["score"][0]["when"].update(state="sideways"), "has no state"),
    (lambda g: g["attachments"][0].update(kind="catapult"), "kind must be"),
    (lambda g: g.update(home="garage"), "Home zone"),
])
def test_game_mistakes_are_explained(game, change, message):
    broken = copy.deepcopy(game)
    change(broken)
    with pytest.raises(ShapeError, match=message):
        play(broken, "pass\n", sorted({m["id"] for m in broken["models"]}))


def test_a_full_match_simulates_quickly(game):
    # 150 s of a waiting loop with the whole field: the browser runs this in Pyodide.
    code = "while True:\n    arm.run_target(500, 60)\n    arm.run_target(500, 0)\n    drive_base.turn(30)\n"
    result = play(game, code, [m["id"] for m in game["models"]])
    assert result["end"]["reason"] == "time_limit"
    assert result["stats"]["wall_ms"] < 6000


def test_run_program_is_unchanged_by_a_mission_on_another_simulation(run, game):
    before = run("drive_base.straight(300)")
    play(game, "drive_base.straight(300)\n", ["crate"])
    after = run("drive_base.straight(300)")
    assert before["frames"] == after["frames"]


def test_trace_keeps_lesson_keys(game):
    result = play(game, "pass\n", ["crate"])
    lesson = run_program(SETUP, {"id": "w", "size": [1000, 1000]}, load("robots", "trainer-bot"))
    assert set(lesson) <= set(result)

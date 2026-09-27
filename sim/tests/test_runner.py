import json

import pytest

from conftest import SETUP_LINES, printed
from trainer_sim.runner import run_program_json


def test_prints_have_times_and_lines(run):
    result = run("""
        print("start")
        drive_base.straight(200)
        print("done", 1 + 1)
    """)
    first, second = result["prints"]
    assert (first["text"], first["line"]) == ("start", SETUP_LINES + 1)
    assert (second["text"], second["line"]) == ("done 2", SETUP_LINES + 3)
    assert second["t"] > first["t"] + 500


def test_print_with_end_joins_lines(run):
    result = run("""
        for i in range(3):
            print(i, end=" ")
        print()
    """)
    assert printed(result) == ["0 1 2 "]


def test_infinite_loop_hits_time_limit(run):
    result = run("""
        while True:
            pass
    """, time_limit=2)
    assert result["end"]["reason"] == "time_limit"
    assert result["end"]["t"] == pytest.approx(2000, abs=1)


def test_catching_exceptions_does_not_swallow_time_limit(run):
    result = run("""
        while True:
            try:
                wait(100)
            except Exception:
                print("caught")
    """, time_limit=1)
    assert result["end"]["reason"] == "time_limit"
    assert "caught" not in printed(result)


def test_step_limit(run):
    result = run("""
        while True:
            pass
    """, max_lines=1000)
    assert result["end"]["reason"] == "step_limit"


def test_frames_follow_the_robot(run):
    result = run("drive_base.straight(300)")
    frames = result["frames"]
    assert frames["t"][0] == 0
    assert result["frame_ms"] == 20
    assert all(b > a for a, b in zip(frames["t"], frames["t"][1:]))
    assert frames["x"][0] == 1500 and frames["x"][-1] == pytest.approx(1800, abs=0.5)
    assert set(frames["line"][5:-1]) == {SETUP_LINES + 1}


def test_steps_and_variables(run):
    result = run("""
        total = 0
        for i in range(3):
            total = total + i
    """, setup=False)
    lines = [line for _, line in result["steps"]]
    assert lines == [1, 2, 3, 2, 3, 2, 3, 2]
    last = dict((name, value) for name, value, _ in result["vars"][-1]["vars"])
    assert last == {"total": "3", "i": "2"}


def test_function_locals_are_marked(run):
    result = run("""
        def double(n):
            answer = n * 2
            return answer
        x = double(4)
    """, setup=False)
    scopes = {(name, scope) for change in result["vars"] for name, _, scope in change["vars"]}
    assert ("n", "local") in scopes
    assert ("answer", "local") in scopes
    assert ("x", "global") in scopes


def test_variable_display_formats(run):
    result = run("""
        speeds = [100, 200.456, "fast", [1, [2, [3]]]]
        seen = Color.BLACK
        done = True
    """)
    values = {name: value for name, value, _ in result["vars"][-1]["vars"]}
    assert values["speeds"] == "[100, 200.46, 'fast', [1, […]]]"
    assert values["seen"] == "Color.BLACK"
    assert "drive_base" not in values and "hub" not in values


def test_blocked_import(run):
    result = run("import os")
    assert result["end"]["reason"] == "error"
    assert "doesn't have a module called `os`" in result["end"]["error"]["kid_message"]


def test_allowed_imports(run):
    result = run("""
        import math, umath, random, urandom
        from micropython import const
        print(round(math.sqrt(16)), umath.pi > 3, const(5))
    """, setup=False)
    assert printed(result) == ["4 True 5"]


def test_input_is_not_available(run):
    result = run("x = input('speed?')", setup=False)
    assert "input()" in result["end"]["error"]["kid_message"]


def test_system_exit_finishes_normally(run):
    result = run("""
        print("a")
        raise SystemExit
        print("b")
    """, setup=False)
    assert result["end"]["reason"] == "finished"
    assert printed(result) == ["a"]


def test_random_is_repeatable(run):
    code = """
        import random
        print(random.randint(1, 1000000))
    """
    assert printed(run(code, setup=False, seed=3)) == printed(run(code, setup=False, seed=3))


def test_json_entry_point(robot, open_world):
    payload = json.dumps({"code": "print('hi')", "world": open_world, "robot": robot})
    result = json.loads(run_program_json(payload))
    assert result["prints"][0]["text"] == "hi"
    assert result["end"]["reason"] == "finished"
    assert result["goals"] == []


def test_long_line_follow_is_fast_enough(run):
    """A 60-second busy loop shouldn't take long to simulate."""
    result = run("""
        sensor = ColorSensor(Port.C)
        watch = StopWatch()
        while watch.time() < 60000:
            error = sensor.reflection() - 50
            drive_base.drive(100, error)
    """)
    assert result["stats"]["wall_ms"] < 3000
    assert result["end"]["reason"] == "finished"


def test_structure_describes_loops_and_ifs(run):
    result = run("""
        for side in range(4):
            if side == 2:
                print("two")
            elif side == 3:
                print("three")
            else:
                print("other")
        while False:
            pass
    """, setup=False)
    assert result["structure"] == [
        {"line": 1, "body": [2, 7], "kind": "for", "target": "side"},
        {"line": 2, "body": [3, 3], "kind": "if"},
        {"line": 4, "body": [5, 5], "kind": "elif"},
        {"line": 8, "body": [9, 9], "kind": "while"},
    ]


def test_print_times_line_up_with_steps(run):
    """A print's time equals the time of the next step, so the visualizer can match them."""
    result = run("""
        print("a")
        x = 1
    """, setup=False)
    step_times = [t for t, _ in result["steps"]]
    assert result["prints"][0]["t"] == step_times[1]

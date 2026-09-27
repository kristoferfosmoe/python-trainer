import pytest

from conftest import SETUP_LINES
from trainer_sim.errors import lint


def kid(result):
    assert result["end"]["reason"] == "error", result["end"]
    return result["end"]["error"]["kid_message"]


@pytest.mark.parametrize("code, expected", [
    ("for i in range(4)\n    print(i)", "need a colon"),
    ("for i in range(4):\nprint(i)", "indented"),
    ("x = 1\n    y = 2", "isn't inside a loop"),
    ("print('hi'", "never closed"),
    ("print('hi)", "missing its closing quote"),
    ("if x = 5:\n    pass", "=="),
    ("2nd = 5", "can't start with a number"),
    ("print(“hi”)", "curly quotes"),
    ("while True\n    pass", "need a colon"),
])
def test_syntax_errors(run, code, expected):
    result = run(code, setup=False)
    assert expected in kid(result)
    assert result["end"]["error"]["type"] in ("SyntaxError", "IndentationError")
    assert result["end"]["error"]["line"] in (1, 2)


def test_missing_import_suggests_import_line(run):
    message = kid(run("wait(100)", setup=False))
    assert "from pybricks.tools import wait" in message


def test_misspelled_variable_suggests_name(run):
    message = kid(run("drivebase.straight(100)"))
    assert "Did you mean `drive_base`?" in message


def test_misspelled_method_suggests_method(run):
    result = run("drive_base.straigt(100)")
    assert "Did you mean `straight`?" in kid(result)
    assert result["end"]["error"]["line"] == SETUP_LINES + 1
    assert result["end"]["error"]["python_message"].startswith("AttributeError:")


def test_bad_port(run):
    assert "Ports go from" in kid(run("Motor(Port.G)"))


def test_missing_argument(run):
    message = kid(run("drive_base.straight()"))
    assert "how far to drive" in message
    assert "drive_base.straight(200)" in message


def test_text_instead_of_number(run):
    result = run("drive_base.straight('200')")
    assert "Remove the quotes" in kid(result)
    assert result["end"]["error"]["type"] == "TypeError"


def test_mixing_text_and_numbers(run):
    assert "str(number)" in kid(run("print('Speed: ' + 200)", setup=False))


def test_zero_division(run):
    assert "divided by zero" in kid(run("x = 10 / 0", setup=False))


def test_list_index(run):
    assert "start counting at 0" in kid(run("moves = [1, 2]\nprint(moves[2])", setup=False))


def test_error_inside_function_points_at_student_line(run):
    result = run("""
        def go():
            drive_base.straight(None)
        go()
    """)
    assert result["end"]["error"]["line"] == SETUP_LINES + 2


def test_not_in_simulator(run):
    message = kid(run("""
        from pybricks.tools import multitask
        multitask()
    """))
    assert "doesn't support it yet" in message


def test_wrong_import_name(run):
    message = kid(run("from pybricks.pupdevices import ColourSensor", setup=False))
    assert "ColorSensor" in message


def test_misplaced_import(run):
    message = kid(run("from pybricks.pupdevices import DriveBase", setup=False))
    assert "from pybricks.robotics import DriveBase" in message


def test_same_motor_twice(run):
    message = kid(run("DriveBase(left_motor, left_motor, 56, 112)"))
    assert "same motor twice" in message


def test_drivebase_needs_motors(run):
    message = kid(run("DriveBase(Port.A, Port.B, 56, 112)"))
    assert "needs two Motor objects" in message


def test_lint_warnings():
    warnings = lint("drive_base.stop\nx == 5\nwait\ndrive_base.stop()\n")
    assert [w["line"] for w in warnings] == [1, 2, 3]
    assert "`drive_base.stop()`" in warnings[0]["message"]


def test_lint_ignores_bad_syntax():
    assert lint("for for for") == []

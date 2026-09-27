"""Kid-friendly explanations for Python errors, plus a few pre-run warnings.

Every error keeps the real Python message (so students learn to read them)
and adds a plain-English explanation with a pointer to the line.
"""

import ast
import builtins
import difflib
import re
import traceback

STUDENT_FILE = "main.py"


# --- Exceptions the simulator raises -------------------------------------------

class SimStop(BaseException):
    """Ends the program. BaseException so `except Exception` can't catch it."""


class TimeUp(SimStop):
    pass


class StepLimit(SimStop):
    pass


class ArgumentError(TypeError):
    def __init__(self, message, kid_message=None):
        super().__init__(message)
        self.kid_message = kid_message or message


class ArgumentValueError(ValueError):
    def __init__(self, message, kid_message=None):
        super().__init__(message)
        self.kid_message = kid_message or message


class DeviceError(OSError):
    """No device (or the wrong kind of device) on a port. Real hubs raise ENODEV."""

    NAMES = {
        "motor": "a motor",
        "color_sensor": "a color sensor",
        "ultrasonic_sensor": "an ultrasonic (distance) sensor",
        "force_sensor": "a force sensor",
    }

    def __init__(self, port, wanted, found):
        super().__init__(19, f"ENODEV: no {wanted.replace('_', ' ')} found on Port.{port}")
        want = self.NAMES.get(wanted, wanted)
        if found is None:
            self.kid_message = (
                f"Nothing is plugged into Port.{port} on this robot, so it can't be used as {want}. "
                "Check the robot's port map to see what's plugged in where."
            )
        else:
            self.kid_message = (
                f"Port.{port} has {self.NAMES.get(found, found)} plugged in, not {want}. "
                "Check the robot's port map."
            )

    @classmethod
    def bad_port(cls, value):
        err = ArgumentError(
            f"expected a Port, like Port.A, but got {value!r}",
            f"Devices need a port like `Port.A`, but this got `{value!r}`. "
            "Did you forget `Port.`?",
        )
        return err


class RobotError(RuntimeError):
    """Something the robot can't do, with a ready-made friendly message."""

    def __init__(self, message, kid_message):
        super().__init__(message)
        self.kid_message = kid_message


class NotInSimulator(NotImplementedError):
    def __init__(self, what):
        super().__init__(f"{what} is not available in the simulator yet")
        self.kid_message = (
            f"`{what}` is a real Pybricks feature, but the simulator doesn't support it yet. "
            "Try a different way, or test this part on your real robot."
        )


class BlockedImport(ImportError):
    ALLOWED = ("pybricks", "math", "umath", "random", "urandom", "micropython")

    def __init__(self, name):
        super().__init__(f"no module named '{name}'", name=name)
        self.kid_message = (
            f"The robot doesn't have a module called `{name}`. On the robot you can import "
            "`pybricks` modules, `math` (also called `umath`) and `random` (also called `urandom`)."
        )


# --- Helpers ----------------------------------------------------------------------

PYBRICKS_IMPORTS = {
    "PrimeHub": "from pybricks.hubs import PrimeHub",
    "Motor": "from pybricks.pupdevices import Motor",
    "ColorSensor": "from pybricks.pupdevices import ColorSensor",
    "UltrasonicSensor": "from pybricks.pupdevices import UltrasonicSensor",
    "ForceSensor": "from pybricks.pupdevices import ForceSensor",
    "Port": "from pybricks.parameters import Port",
    "Direction": "from pybricks.parameters import Direction",
    "Stop": "from pybricks.parameters import Stop",
    "Color": "from pybricks.parameters import Color",
    "Button": "from pybricks.parameters import Button",
    "Side": "from pybricks.parameters import Side",
    "Axis": "from pybricks.parameters import Axis",
    "Icon": "from pybricks.parameters import Icon",
    "DriveBase": "from pybricks.robotics import DriveBase",
    "wait": "from pybricks.tools import wait",
    "StopWatch": "from pybricks.tools import StopWatch",
}

ARGUMENT_HINTS = {
    "straight": ("how far to drive in millimeters", "drive_base.straight(200)"),
    "turn": ("how many degrees to turn (positive turns right)", "drive_base.turn(90)"),
    "curve": ("the curve's radius in mm and how many degrees to turn", "drive_base.curve(200, 90)"),
    "drive": ("a speed in mm/s and a turn rate in degrees per second", "drive_base.drive(150, 0)"),
    "wait": ("how many milliseconds to wait (1000 ms = 1 second)", "wait(1000)"),
    "run": ("a speed in degrees per second", "arm_motor.run(500)"),
    "run_angle": ("a speed and how many degrees to turn", "arm_motor.run_angle(500, 90)"),
    "run_target": ("a speed and the angle to go to", "arm_motor.run_target(500, 0)"),
    "run_time": ("a speed and a time in milliseconds", "arm_motor.run_time(500, 1000)"),
    "run_until_stalled": ("a speed", "arm_motor.run_until_stalled(300)"),
    "Motor": ("a port, like Port.A", "Motor(Port.A)"),
    "ColorSensor": ("a port, like Port.C", "ColorSensor(Port.C)"),
    "UltrasonicSensor": ("a port, like Port.D", "UltrasonicSensor(Port.D)"),
    "DriveBase": (
        "the left motor, the right motor, the wheel diameter and the axle track",
        "DriveBase(left_motor, right_motor, wheel_diameter=56, axle_track=112)",
    ),
    "beep": ("a frequency and a duration", "hub.speaker.beep(500, 100)"),
    "range": ("how many times to repeat", "range(4)"),
}


def _student_line(exc):
    line = None
    tb = exc.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == STUDENT_FILE:
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def _python_name(exc):
    """Name of the closest built-in exception (hides simulator-internal classes)."""
    for cls in type(exc).__mro__:
        if getattr(builtins, cls.__name__, None) is cls:
            return cls.__name__
    return type(exc).__name__


def _python_message(exc):
    name = _python_name(exc)
    if isinstance(exc, SyntaxError):
        return f"{name}: {exc.msg}"
    text = str(exc)
    return f"{name}: {text}" if text else name


def _close(word, options):
    matches = difflib.get_close_matches(word, list(options), n=1, cutoff=0.7)
    if not matches:
        lower = {o.lower(): o for o in options}
        if word.lower() in lower:
            return lower[word.lower()]
        return None
    return matches[0]


def _code_names(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.alias):
            names.add((node.asname or node.name).split(".")[0])
    return names


def _func_name(message):
    match = re.match(r"(?:[\w.]+\.)?(\w+)\(\)", message)
    return match.group(1) if match else None


# --- Explaining errors ------------------------------------------------------------

def _explain_syntax(exc, code):
    msg = exc.msg or ""
    line = exc.lineno
    name = type(exc).__name__
    lines = code.splitlines()
    text = lines[line - 1] if line and 0 < line <= len(lines) else ""

    if name == "TabError" or "inconsistent use of tabs" in msg:
        return "This line mixes tabs and spaces. Use only spaces to indent (4 spaces per level)."
    m = re.search(r"expected an indented block after '?(\w+)'? statement on line (\d+)", msg)
    if m:
        return (
            f"The lines inside your `{m.group(1)}` need to be indented: moved right by 4 spaces. "
            f"Indent the line after line {m.group(2)}."
        )
    if "expected an indented block" in msg:
        return "The line after a `:` needs to be indented: moved right by 4 spaces."
    if "unexpected indent" in msg:
        return (
            f"Line {line} is indented (moved to the right), but it isn't inside a loop, `if` or function. "
            "Line it up with the line above it."
        )
    if "unindent does not match" in msg:
        return (
            f"Line {line} doesn't line up with the lines above it. Lines in the same block must start "
            "at exactly the same spot."
        )
    if "expected ':'" in msg:
        return "Lines that start with `for`, `while`, `if`, `elif`, `else` or `def` need a colon `:` at the end."
    if "was never closed" in msg:
        bracket = re.search(r"'(.)' was never closed", msg)
        b = bracket.group(1) if bracket else "("
        closing = {"(": ")", "[": "]", "{": "}"}.get(b, ")")
        return f"A bracket `{b}` on line {line} is never closed. Add a `{closing}` to close it."
    if msg.startswith("unmatched"):
        return f"Line {line} has an extra closing bracket. Remove it, or add the matching opening bracket."
    if "does not match opening parenthesis" in msg:
        return f"The brackets on line {line} don't match. A `(` must close with `)`, and a `[` with `]`."
    if "unterminated string" in msg or "EOL while scanning" in msg:
        return "Some text is missing its closing quote. Text needs quotes at both ends, like `\"hello\"`."
    if "Maybe you meant '==' or ':=' instead of '='" in msg or "cannot assign to comparison" in msg:
        return (
            "To check if two things are equal, use `==` (two equals signs). "
            "A single `=` stores a value in a variable."
        )
    if "forgot a comma" in msg:
        return f"Line {line} looks like it's missing a comma `,` between two values."
    if "invalid decimal literal" in msg or "invalid digit" in msg:
        return "Names can't start with a number. Try `turn2` instead of `2turn`."
    if "cannot assign to" in msg:
        return "The left side of `=` must be a variable name, like `speed = 200`."
    if "invalid character" in msg or "invalid non-printable character" in msg:
        return (
            f"Line {line} has a character Python doesn't understand, like curly quotes “ ” or a "
            "special dash. Delete it and retype it with the keyboard."
        )
    if "Missing parentheses in call to 'print'" in msg:
        return "`print` needs brackets: `print(\"hello\")`."
    if "unexpected EOF" in msg or "expected an expression" in msg:
        return "Python reached the end of the code while something was unfinished, like a bracket or a line after `:`."
    if "'return' outside function" in msg:
        return "`return` can only be used inside a function (after `def`)."
    if "'break' outside loop" in msg or "'continue' not properly in loop" in msg:
        return "`break` and `continue` only work inside a `for` or `while` loop."
    if re.match(r"\s*(if|elif|while|for|def)\b", text) and not text.rstrip().endswith(":"):
        return "Lines that start with `for`, `while`, `if`, `elif` or `def` need a colon `:` at the end."
    if re.match(r"\s*else\s*$", text):
        return "`else` needs a colon: `else:`."
    return (
        f"Python couldn't understand line {line}. Look for a typo, a missing bracket, "
        "a missing colon `:`, or a missing quote."
    )


def _explain_name_error(exc, code):
    name = getattr(exc, "name", None)
    if not name:
        m = re.search(r"name '(\w+)' is not defined", str(exc))
        name = m.group(1) if m else None
    if name is None:
        return "Python doesn't know one of the names on this line."
    if isinstance(exc, UnboundLocalError):
        return (
            f"Inside this function, `{name}` is used before it gets a value. If `{name}` was created "
            "outside the function, pass it in as a parameter instead."
        )
    if name in PYBRICKS_IMPORTS:
        return f"Python doesn't know `{name}` yet. Import it at the top of your program:\n`{PYBRICKS_IMPORTS[name]}`"
    options = (_code_names(code) | set(dir(builtins)) | set(PYBRICKS_IMPORTS)) - {name}
    options = {o for o in options if not o.startswith("_")}
    guess = _close(name, options)
    if guess:
        hint = f" Import it first: `{PYBRICKS_IMPORTS[guess]}`" if guess in PYBRICKS_IMPORTS else ""
        return f"Python doesn't know `{name}`. Did you mean `{guess}`?{hint}"
    return (
        f"Python doesn't know what `{name}` is. Did you create it (like `{name} = ...`) before this line? "
        "Spelling and capital letters must match exactly."
    )


def _explain_attribute_error(exc):
    obj = getattr(exc, "obj", None)
    name = getattr(exc, "name", None)
    if name is None:
        return "That command doesn't exist on this object. Check the spelling."
    if obj is None and "NoneType" in str(exc):
        return (
            f"You used `.{name}` on something that is `None` (empty). Maybe a function didn't "
            "`return` a value, or a variable wasn't set."
        )
    type_name = obj.__name__ if isinstance(obj, type) else type(obj).__name__
    from pybricks.parameters import Port
    if obj is Port:
        return f"There's no `Port.{name}`. Ports go from `Port.A` to `Port.F`."
    public = [a for a in dir(obj) if not a.startswith("_")]
    guess = _close(name, public)
    if guess:
        return f"`{type_name}` doesn't have `{name}`. Did you mean `{guess}`?"
    if public and type(obj).__module__.startswith("pybricks"):
        shown = ", ".join(f"`{a}`" for a in public[:12])
        return f"`{type_name}` doesn't have `{name}`. It has: {shown}."
    return f"`{type_name}` doesn't have anything called `{name}`. Check the spelling."


def _explain_type_error(exc):
    msg = str(exc)
    func = _func_name(msg)
    hint = ARGUMENT_HINTS.get(func) if func else None
    if "missing" in msg and "required" in msg:
        if hint:
            return f"`{func}()` needs more information: {hint[0]}. Example: `{hint[1]}`"
        return f"`{func or 'This command'}()` needs more values between its brackets."
    if "positional argument" in msg and "given" in msg:
        if hint:
            return f"`{func}()` got too many values. It needs {hint[0]}. Example: `{hint[1]}`"
        return f"`{func or 'This command'}()` got too many values between its brackets."
    if "unexpected keyword argument" in msg:
        kw = re.search(r"'(\w+)'", msg.split("argument", 1)[-1])
        return f"`{func or 'This command'}()` doesn't have an option called `{kw.group(1) if kw else '?'}`. Check the spelling."
    if "can only concatenate str" in msg or ("unsupported operand" in msg and "str" in msg):
        return (
            "You're mixing text and numbers. Turn the number into text with `str(number)`, "
            "or use an f-string like `f\"Speed: {speed}\"`."
        )
    if "unsupported operand" in msg:
        return "These two values can't be combined with that math operator. Check what type each one is."
    if "is not callable" in msg:
        what = re.search(r"'(\w+)' object", msg)
        return (
            f"You put `()` after something that is a {what.group(1) if what else 'value'}, not a command. "
            "Maybe a variable has the same name as a function?"
        )
    if "not iterable" in msg:
        return "A `for` loop needs something to loop over, like `range(4)` or a list."
    if "not supported between instances" in msg:
        return "These two values can't be compared with `<` or `>`. Are they both numbers?"
    if "indices must be integers" in msg:
        return "List positions must be whole numbers, like `my_list[0]`."
    if "not subscriptable" in msg:
        return "You used `[ ]` on something that isn't a list or text."
    return "A value has the wrong type for this command. Check the values in the brackets."


def explain(exc, code):
    """Everything the UI needs to show an error."""
    try:
        if isinstance(exc, SyntaxError):
            line = exc.lineno
            kid = _explain_syntax(exc, code)
        else:
            line = _student_line(exc)
            kid = getattr(exc, "kid_message", None)
            if kid is None:
                if isinstance(exc, NameError):
                    kid = _explain_name_error(exc, code)
                elif isinstance(exc, AttributeError):
                    kid = _explain_attribute_error(exc)
                elif isinstance(exc, TypeError):
                    kid = _explain_type_error(exc)
                elif isinstance(exc, ZeroDivisionError):
                    kid = "You divided by zero. That's not allowed, even for robots! Check what's after the `/`."
                elif isinstance(exc, IndexError):
                    kid = (
                        "You asked for a list item that doesn't exist. Lists start counting at 0, "
                        "so a list with 3 items has positions 0, 1 and 2."
                    )
                elif isinstance(exc, KeyError):
                    kid = f"The dictionary doesn't have the key {exc.args[0]!r}."
                elif isinstance(exc, RecursionError):
                    kid = "A function keeps calling itself forever. Make sure it has a way to stop."
                elif isinstance(exc, ValueError) and "invalid literal" in str(exc):
                    kid = "That text can't be turned into a number."
                elif isinstance(exc, ModuleNotFoundError):
                    kid = f"There's no module called `{exc.name}`."
                elif isinstance(exc, ImportError):
                    kid = _explain_import_error(exc)
                elif isinstance(exc, (EOFError, OSError)) and "input" in str(exc):
                    kid = "The robot can't ask questions with `input()`. Put the value in a variable instead."
                else:
                    kid = "Something went wrong on this line. Read the Python message below for clues."
        return {
            "type": _python_name(exc),
            "line": line,
            "python_message": _python_message(exc),
            "kid_message": kid,
        }
    except Exception:  # never let the explainer itself crash a run
        return {
            "type": type(exc).__name__,
            "line": None,
            "python_message": "".join(traceback.format_exception_only(type(exc), exc)).strip(),
            "kid_message": "Something went wrong. Read the Python message for clues.",
        }


def _explain_import_error(exc):
    msg = str(exc)
    m = re.search(r"cannot import name '(\w+)' from '([\w.]+)'", msg)
    if m:
        name, module = m.groups()
        try:
            import importlib
            mod = importlib.import_module(module)
            guess = _close(name, [a for a in dir(mod) if not a.startswith("_")])
        except Exception:
            guess = None
        if name in PYBRICKS_IMPORTS:
            return f"`{name}` isn't in `{module}`. Use: `{PYBRICKS_IMPORTS[name]}`"
        if guess:
            return f"`{module}` doesn't have `{name}`. Did you mean `{guess}`?"
        return f"`{module}` doesn't have anything called `{name}`."
    return "Python couldn't import that. Check the spelling of the module and the name."


# --- Warnings before running -------------------------------------------------------

def lint(code):
    """Spot lines that probably don't do what the student meant."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    warnings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        value = node.value
        if isinstance(value, ast.Attribute):
            text = ast.unparse(value)
            warnings.append({
                "line": node.lineno,
                "message": f"`{text}` doesn't do anything by itself. To run it as a command, add brackets: `{text}()`.",
            })
        elif isinstance(value, ast.Name) and value.id in ("wait", "print"):
            warnings.append({
                "line": node.lineno,
                "message": f"`{value.id}` needs brackets to run, like `{value.id}(...)`.",
            })
        elif isinstance(value, ast.Compare) and any(isinstance(op, ast.Eq) for op in value.ops):
            warnings.append({
                "line": node.lineno,
                "message": "This line checks if two things are equal but doesn't use the answer. To store a value, use one `=`.",
            })
    return sorted(warnings, key=lambda w: w["line"])

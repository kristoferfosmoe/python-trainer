"""Run a student's program in the simulator and return a trace."""

import ast
import builtins
import io
import json
import random
import sys
import time

from . import __version__, context
from .errors import (
    STUDENT_FILE, BlockedImport, RobotError, StepLimit, StopButtonPressed, TimeUp, explain, lint,
)
from .goals import check_goals
from .sim import DT_MS, RECORD_EVERY, Simulation


class _Output(io.TextIOBase):
    """Sends print() output into the recording, with timestamps."""

    def __init__(self, sim):
        self.sim = sim

    def writable(self):
        return True

    def write(self, text):
        self.sim.write_output(text)
        return len(text)


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".")[0]
    if level == 0 and root not in BlockedImport.ALLOWED:
        raise BlockedImport(root)
    return builtins.__import__(name, globals, locals, fromlist, level)


def _no_input(*args, **kwargs):
    raise RobotError(
        "input() is not available on the robot",
        "The robot can't ask questions with `input()`. Put the value in a variable instead.",
    )


def _no_open(*args, **kwargs):
    raise RobotError(
        "open() is not available in the simulator",
        "Programs in the simulator can't open files.",
    )


STOP_GUARD = "__sim_stop__"


class _GuardExceptBlocks(ast.NodeTransformer):
    """Starts every `except` block with a call to Simulation.raise_if_stopped,
    so once the simulator stops the program, catching that can't keep it
    running. The call goes on the block's first line, so line numbers and
    line counts don't change."""

    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        guard = ast.Expr(ast.Call(ast.Name(STOP_GUARD, ast.Load()), [], []))
        node.body.insert(0, ast.copy_location(guard, node.body[0]))
        return node


def compile_student_code(code):
    """Compile `code` as the student's program. Raises SyntaxError."""
    tree = _GuardExceptBlocks().visit(ast.parse(code, STUDENT_FILE))
    return compile(ast.fix_missing_locations(tree), STUDENT_FILE, "exec")


def _student_builtins():
    names = dict(builtins.__dict__)
    names["__import__"] = _guarded_import
    names["input"] = _no_input
    names["open"] = _no_open
    return names


def _execute(sim, compiled, code, seed):
    namespace = {"__name__": "__main__", "__builtins__": _student_builtins(), STOP_GUARD: sim.raise_if_stopped}

    def trace_line(frame, event, arg):
        if event == "line":
            sim.on_line(frame)
        return trace_line

    def trace_call(frame, event, arg):
        # Only student code is traced; the simulator's own code runs "for free".
        if frame.f_code.co_filename == STUDENT_FILE:
            return trace_line
        return None

    old_stdout = sys.stdout
    random.seed(seed)
    context.set_current(sim)
    sys.stdout = _Output(sim)
    sys.settrace(trace_call)
    sim.program_running = True
    try:
        exec(compiled, namespace)
        return {"reason": "finished"}
    except StopButtonPressed as exc:
        error = explain(exc, code)
        error.update(type="SystemExit", python_message="SystemExit: stop button pressed")
        return {"reason": "error", "error": error}
    except TimeUp:
        return {"reason": "time_limit"}
    except StepLimit:
        return {"reason": "step_limit"}
    except SystemExit:
        return {"reason": "finished"}
    except BaseException as exc:  # noqa: BLE001 - any student error is reported, not raised
        return {"reason": "error", "error": explain(exc, code)}
    finally:
        sim.program_running = False
        sys.settrace(None)
        sys.stdout = old_stdout
        context.set_current(None)


def code_structure(code):
    """Loops and if-statements with the lines of their bodies, for the visualizer."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    lines = code.splitlines()
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While, ast.If)):
            entry = {
                "line": node.lineno,
                "body": [node.body[0].lineno, node.body[-1].end_lineno],
            }
            if isinstance(node, ast.For):
                entry["kind"] = "for"
                entry["target"] = ast.unparse(node.target)
            elif isinstance(node, ast.While):
                entry["kind"] = "while"
            else:
                text = lines[node.lineno - 1].lstrip() if node.lineno <= len(lines) else ""
                entry["kind"] = "elif" if text.startswith("elif") else "if"
            found.append(entry)
    return sorted(found, key=lambda e: e["line"])


def run_program(code, world, robot, options=None, goals=None):
    """Run `code` and return everything the browser needs to replay it."""
    options = options or {}
    started = time.perf_counter()
    sim = Simulation(world, robot, options)
    warnings = lint(code)
    try:
        compiled = compile_student_code(code)
    except SyntaxError as exc:
        end = {"reason": "error", "error": explain(exc, code)}
    else:
        end = _execute(sim, compiled, code, options.get("seed", 1))
    sim.finish()
    end["t"] = round(sim.now, 1)
    if end["reason"] == "error":
        end["line"] = end["error"]["line"]
    else:
        end["line"] = sim.current_line or None

    recording = sim.recorder.to_dict()
    result = {
        "sim_version": __version__,
        "frame_ms": DT_MS * RECORD_EVERY,
        "start": {"x": sim.start[0], "y": sim.start[1], "heading": sim.start[2]},
        "end": end,
        "warnings": warnings,
        "structure": code_structure(code),
        "goals": check_goals(goals, sim.world, recording, end, code, sim),
    }
    result.update(recording)
    result["stats"] = {
        "lines": sim.lines_executed,
        "sim_ms": round(sim.now),
        "wall_ms": round((time.perf_counter() - started) * 1000),
    }
    return result


def run_program_json(payload):
    """JSON in, JSON out: the entry point the browser's Web Worker calls."""
    request = json.loads(payload)
    result = run_program(
        request["code"],
        request["world"],
        request["robot"],
        request.get("options"),
        request.get("goals"),
    )
    return json.dumps(result, separators=(",", ":"))

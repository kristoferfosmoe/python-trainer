"""Challenge goals, checked against a finished run.

Goals are plain data (from lesson files) so teachers can write them
without writing code. Zone checks use the center of the robot.
"""

import ast

from .shapes import ShapeError

def _node(node_type):
    return lambda n: isinstance(n, node_type)


def _operator(op_type):
    return lambda n: isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, op_type)


# must_use constructs: (test for an AST node, how to describe it)
CONSTRUCTS = {
    "for": (_node(ast.For), "a `for` loop"),
    "while": (_node(ast.While), "a `while` loop"),
    "if": (_node(ast.If), "an `if` statement"),
    "def": (_node(ast.FunctionDef), "a function (`def`)"),
    "list": (_node(ast.List), "a list"),
    "variable": (_node(ast.Assign), "a variable"),
    "fstring": (_node(ast.JoinedStr), "an f-string, like `f\"{points} points\"`"),
    "floor_divide": (_operator(ast.FloorDiv), "whole-number division `//`"),
    "modulo": (_operator(ast.Mod), "the remainder operator `%`"),
}


def _calls(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and (
            (isinstance(n.func, ast.Attribute) and n.func.attr == name)
            or (isinstance(n.func, ast.Name) and n.func.id == name)
        ):
            yield n


class Goal:
    def __init__(self, spec, index):
        self.spec = spec
        self.type = spec.get("type")
        self.id = spec.get("id", f"goal-{index + 1}")
        self.label = spec.get("label")


def _zone_label(world, zone_id):
    zone = world.zone_at(zone_id)
    return zone.label or zone_id


def _positions(frames):
    return list(zip(frames["x"], frames["y"]))


def check_goal(spec, index, world, recording, end, code, sim):
    goal = Goal(spec, index)
    kind = goal.type
    frames = recording["frames"]
    passed, label, detail = False, goal.label, ""

    if kind == "end_in_zone":
        zone = world.zone_at(spec["zone"])
        label = label or f"Finish in {_zone_label(world, spec['zone'])}"
        passed = zone.contains(sim.x, sim.y)
        detail = "" if passed else "The robot didn't finish inside the zone."

    elif kind == "visit_zones":
        ids = spec["zones"]
        zones = [world.zone_at(z) for z in ids]
        in_order = spec.get("in_order", False)
        names = ", ".join(_zone_label(world, z) for z in ids)
        label = label or (f"Visit {names} in order" if in_order else f"Visit {names}")
        visited = []
        for x, y in _positions(frames):
            for zone_id, zone in zip(ids, zones):
                if zone.contains(x, y) and zone_id not in visited:
                    if not in_order or ids[len(visited)] == zone_id:
                        visited.append(zone_id)
        passed = len(visited) == len(ids)
        missing = [z for z in ids if z not in visited]
        detail = "" if passed else "Not visited" + (" in order" if in_order else "") + ": " + ", ".join(
            _zone_label(world, z) for z in missing)

    elif kind == "avoid_zones":
        ids = spec["zones"]
        zones = [world.zone_at(z) for z in ids]
        names = ", ".join(_zone_label(world, z) for z in ids)
        label = label or f"Stay out of {names}"
        entered = {
            zone_id for x, y in _positions(frames) for zone_id, zone in zip(ids, zones) if zone.contains(x, y)
        }
        passed = not entered
        detail = "" if passed else "Entered: " + ", ".join(_zone_label(world, z) for z in ids if z in entered)

    elif kind == "no_collisions":
        label = label or "Don't bump into anything"
        hits = [e for e in recording["events"] if e["type"] == "collision"]
        passed = not hits
        detail = "" if passed else f"Bumped into {hits[0]['what']} on line {hits[0]['line']}."

    elif kind == "max_time":
        seconds = float(spec["seconds"])
        label = label or f"Finish within {seconds:g} seconds"
        passed = end["reason"] == "finished" and end["t"] <= seconds * 1000
        detail = "" if passed else f"Your program took {end['t'] / 1000:.1f} seconds."

    elif kind == "must_use":
        construct = spec["construct"]
        if construct not in CONSTRUCTS:
            raise ShapeError(f"must_use: unknown construct '{construct}'")
        test, name = CONSTRUCTS[construct]
        label = label or f"Use {name}"
        try:
            tree = ast.parse(code)
            passed = any(test(n) for n in ast.walk(tree))
        except SyntaxError:
            passed = False
        detail = "" if passed else f"Your code needs {name}."

    elif kind == "max_calls":
        name, limit = spec["name"], int(spec["value"])
        if limit == 0:
            label = label or f"Don't use `{name}()`"
        else:
            label = label or f"Use `{name}()` at most {limit} time{'s' if limit != 1 else ''} in your code"
        try:
            count = len(list(_calls(ast.parse(code), name)))
        except SyntaxError:
            count = limit + 1
        passed = count <= limit
        if passed:
            detail = ""
        elif limit == 0:
            detail = f"Your code uses `{name}()`. Find another way!"
        else:
            detail = f"`{name}()` appears {count} times. Can a loop help?"

    elif kind == "min_calls":
        name, least = spec["name"], int(spec.get("value", 1))
        label = label or f"Use `{name}()` in your code"
        try:
            count = len(list(_calls(ast.parse(code), name)))
        except SyntaxError:
            count = 0
        passed = count >= least
        detail = "" if passed else f"Your code needs `{name}()`."

    elif kind == "uses_variable_in":
        name = spec["name"]
        label = label or f"Give `{name}()` a variable instead of a plain number"
        try:
            calls = list(_calls(ast.parse(code), name))
        except SyntaxError:
            calls = []
        passed = bool(calls) and all(
            c.args and any(isinstance(n, ast.Name) for n in ast.walk(c.args[0])) for c in calls
        )
        detail = "" if passed else f"Put a variable inside the brackets, like `{name}(distance)`."

    elif kind == "printed":
        text = str(spec["text"])
        label = label or f"Print {text!r}"
        passed = any(text in p["text"] for p in recording["prints"])
        detail = "" if passed else "That text never appeared in the console."

    else:
        raise ShapeError(f"unknown goal type '{kind}'")

    return {"id": goal.id, "type": kind, "label": label, "passed": bool(passed), "detail": detail}


def check_goals(goals, world, recording, end, code, sim):
    if not goals:
        return []
    results = [{
        "id": "no-errors",
        "type": "no_errors",
        "label": "Program runs without errors",
        "passed": end["reason"] in ("finished", "time_limit"),
        "detail": "" if end["reason"] in ("finished", "time_limit") else "Fix the error first.",
    }]
    for index, spec in enumerate(goals):
        results.append(check_goal(spec, index, world, recording, end, code, sim))
    return results

"""Load and check lesson content: courses, units, lessons and challenges.

Content lives in YAML files under content/ (see docs/ARCHITECTURE.md §7).
The tests use this to check every lesson, and the backend will use it to
import lessons and to validate lessons that teachers edit.

This package is not bundled into the browser; it needs PyYAML.
"""

import pathlib

import yaml

from trainer_sim.goals import CONSTRUCTS
from trainer_sim.runner import run_program
from trainer_sim.world import World

BLOCK_TYPES = ("text", "example", "visualize", "quiz", "challenge")
GOAL_TYPES = (
    "end_in_zone", "visit_zones", "avoid_zones", "no_collisions", "max_time",
    "must_use", "max_calls", "uses_variable_in", "printed",
)
# Console-only lessons still run in a world; the robot just sits there.
DEFAULT_WORLD = "practice-field"


class ContentError(ValueError):
    pass


def _load(path):
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ContentError(f"{path}: expected a YAML dictionary")
    return data


def resolve_blocks(lesson, playground_by_id):
    """A copy of the lesson with block ids filled in and playground refs expanded."""
    lesson = dict(lesson)
    blocks = lesson.get("blocks")
    if not isinstance(blocks, list):
        return lesson
    resolved = []
    for index, block in enumerate(blocks):
        block = dict(block)
        ref = block.get("ref")
        if block.get("type") == "challenge" and ref:
            base = playground_by_id.get(ref)
            if base is None:
                raise ContentError(f"{lesson.get('id')}: challenge ref '{ref}' is not a playground challenge")
            block = {**base, **block}
            block.setdefault("id", ref)
            block["type"] = "challenge"
        block.setdefault("id", f"block-{index + 1}")
        resolved.append(block)
    lesson["blocks"] = resolved
    return lesson


class Library:
    """Everything in a content/ folder: robot, worlds, playground challenges, courses.

    Lessons are kept exactly as written (`raw`); `lessons()` gives them with
    playground refs expanded and block ids filled in.
    """

    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.robot = _load(self.root / "robots" / "trainer-bot.yaml")
        self.worlds = {w["id"]: w for w in (_load(p) for p in sorted((self.root / "worlds").glob("*.yaml")))}
        self.playground = [_load(p) for p in sorted((self.root / "challenges").glob("*.yaml"))]
        self.playground_by_id = {c["id"]: c for c in self.playground}
        courses_dir = self.root / "courses"
        self.courses = [
            self.load_course(d) for d in sorted(courses_dir.iterdir()) if (d / "course.yaml").exists()
        ] if courses_dir.exists() else []

    def load_course(self, course_dir):
        course = _load(course_dir / "course.yaml")
        course["units"] = []
        for unit_dir in sorted(d for d in course_dir.iterdir() if d.is_dir()):
            unit = _load(unit_dir / "unit.yaml")
            unit["lessons"] = []
            for p in sorted(unit_dir.glob("*.yaml")):
                if p.name != "unit.yaml":
                    lesson = _load(p)
                    lesson["source"] = str(p)
                    unit["lessons"].append(lesson)
            course["units"].append(unit)
        return course

    def resolve_lesson(self, lesson):
        return resolve_blocks(lesson, self.playground_by_id)

    def lessons(self, resolved=True):
        for course in self.courses:
            for unit in course["units"]:
                for lesson in unit["lessons"]:
                    yield self.resolve_lesson(lesson) if resolved else lesson


# --- Checking -----------------------------------------------------------------------

def challenge_options(block):
    options = {"time_limit": block.get("time_limit", 150), "realism": block.get("realism", "off")}
    if block.get("start"):
        options["start"] = block["start"]
    return options


def _choice_text(choice):
    return choice["text"] if isinstance(choice, dict) else str(choice)


class Checker:
    """Finds problems in lessons. `run=False` skips running code (fast structural check).

    `library` is anything with `robot`, `worlds` and `playground_by_id`
    (a Library, or the backend's database equivalent). Lessons passed to
    check_lesson must already be resolved (see resolve_blocks).
    """

    def __init__(self, library, run=True):
        self.lib = library
        self.run_code = run

    def _run(self, code, world_id=None, block=None):
        world = self.lib.worlds[world_id or DEFAULT_WORLD]
        block = block or {}
        return run_program(code, world, self.lib.robot, challenge_options(block), block.get("goals"))

    def check_course(self, course):
        problems = []
        for key in ("id", "title"):
            if not course.get(key):
                problems.append(f"course is missing '{key}'")
        ids = set()
        for unit in course["units"]:
            for key in ("id", "title"):
                if not unit.get(key):
                    problems.append(f"unit {unit.get('id', '?')} is missing '{key}'")
            if not unit["lessons"]:
                problems.append(f"unit {unit.get('id')} has no lessons")
            for lesson in unit["lessons"]:
                if lesson.get("id") in ids:
                    problems.append(f"two lessons are called '{lesson.get('id')}'")
                ids.add(lesson.get("id"))
        return problems

    def check_lesson(self, lesson):
        name = lesson.get("id", lesson.get("source", "?"))
        problems = []
        for key in ("id", "title", "summary"):
            if not lesson.get(key):
                problems.append(f"{name}: missing '{key}'")
        blocks = lesson.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            return problems + [f"{name}: needs a list of blocks"]
        seen = set()
        for block in blocks:
            where = f"{name}/{block.get('id')}"
            if block["id"] in seen:
                problems.append(f"{where}: two blocks have this id")
            seen.add(block["id"])
            kind = block.get("type")
            if kind not in BLOCK_TYPES:
                problems.append(f"{where}: unknown block type '{kind}'")
                continue
            problems += getattr(self, f"_check_{kind}")(block, where)
        return problems

    def _check_text(self, block, where):
        return [] if block.get("markdown") else [f"{where}: text blocks need 'markdown'"]

    def _check_code_block(self, block, where, visualize):
        if not block.get("code"):
            return [f"{where}: needs 'code'"]
        if not self.run_code:
            return []
        result = self._run(block["code"], block.get("world"))
        problems = []
        errored = result["end"]["reason"] == "error"
        if errored and not block.get("expect_error"):
            problems.append(f"{where}: code has an error: {result['end']['error']['python_message']}")
        if block.get("expect_error") and not errored:
            problems.append(f"{where}: expect_error is set, but the code runs fine")
        if visualize and result["steps_truncated"]:
            problems.append(f"{where}: too many steps to visualize (over 5000)")
        return problems

    def _check_example(self, block, where):
        return self._check_code_block(block, where, visualize=False)

    def _check_visualize(self, block, where):
        return self._check_code_block(block, where, visualize=True)

    def _check_quiz(self, block, where):
        problems = []
        choices = block.get("choices")
        if not block.get("question"):
            problems.append(f"{where}: quiz needs a 'question'")
        if not isinstance(choices, list) or not 2 <= len(choices) <= 6:
            return problems + [f"{where}: quiz needs 2 to 6 'choices'"]
        answer = block.get("answer")
        if not isinstance(answer, int) or not 0 <= answer < len(choices):
            return problems + [f"{where}: 'answer' must be the index (from 0) of the right choice"]
        texts = [_choice_text(c) for c in choices]
        if len(set(texts)) != len(texts):
            problems.append(f"{where}: two choices are the same")
        if block.get("check") == "output" and self.run_code:
            if not block.get("code"):
                problems.append(f"{where}: check: output needs 'code'")
            else:
                result = self._run(block["code"])
                output = "\n".join(p["text"] for p in result["prints"])
                if output.strip() != texts[answer].strip():
                    problems.append(f"{where}: the code prints {output!r}, but the answer is {texts[answer]!r}")
        return problems

    def _check_challenge(self, block, where):
        problems = []
        if not block.get("starter"):
            problems.append(f"{where}: challenge needs 'starter' code")
        world_id = block.get("world")
        if world_id and world_id not in self.lib.worlds:
            return problems + [f"{where}: unknown world '{world_id}'"]
        world = World(self.lib.worlds[world_id or DEFAULT_WORLD])
        goals = block.get("goals") or []
        for goal in goals:
            if goal.get("type") not in GOAL_TYPES:
                problems.append(f"{where}: unknown goal type '{goal.get('type')}'")
                continue
            for zone in goal.get("zones", []) + ([goal["zone"]] if "zone" in goal else []):
                if zone not in world.zones:
                    problems.append(f"{where}: world '{world_id}' has no zone '{zone}'")
            if goal["type"] == "must_use" and goal.get("construct") not in CONSTRUCTS:
                problems.append(f"{where}: unknown must_use construct '{goal.get('construct')}'")
        if goals and not block.get("solution"):
            problems.append(f"{where}: challenges with goals need a 'solution'")
        if problems or not self.run_code or not block.get("starter"):
            return problems

        starter = self._run(block["starter"], world_id, block)
        if starter["end"]["reason"] == "error" and not block.get("expect_error"):
            problems.append(f"{where}: starter code has an error: {starter['end']['error']['python_message']}")
        if goals:
            if all(g["passed"] for g in starter["goals"]):
                problems.append(f"{where}: the starter code already passes every goal")
            solved = self._run(block["solution"], world_id, block)
            failed = [g["label"] for g in solved["goals"] if not g["passed"]]
            if failed:
                problems.append(f"{where}: the solution fails: {', '.join(failed)}")
        return problems

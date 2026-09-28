"""Mission Mode must not change how lessons and the playground run.

Every piece of code in the lessons and the playground (examples, quizzes,
challenge starters and solutions) is run, and a fingerprint of its trace is
compared with one saved before Mission Mode was added (unchanged_traces.json).
The fingerprint covers everything the browser plays back; it leaves out the
simulator's version, the wall-clock time, and Python's own error wording
(which changes between Python versions).

After a deliberate change to how lessons run, save new fingerprints with:

    uv run python tests/test_unchanged.py --update
"""

import hashlib
import json
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

from trainer_content import DEFAULT_WORLD, Library, challenge_options  # noqa: E402
from trainer_sim.runner import run_program  # noqa: E402

CONTENT = HERE.parents[1] / "content"
SAVED = HERE / "unchanged_traces.json"


def programs(library):
    """(name, code, world id, challenge block) for every program in the lessons and playground."""
    for challenge in library.playground:
        for part in ("starter", "solution"):
            if challenge.get(part):
                yield f"playground/{challenge['id']}/{part}", challenge[part], challenge.get("world"), challenge
    for lesson in library.lessons():
        for block in lesson["blocks"]:
            where = f"lesson/{lesson['id']}/{block['id']}"
            kind = block["type"]
            if kind in ("example", "visualize") or (kind == "quiz" and block.get("code")):
                yield where, block["code"], block.get("world"), None
            elif kind == "challenge":
                for part in ("starter", "solution"):
                    if block.get(part):
                        yield f"{where}/{part}", block[part], block.get("world"), block


def fingerprint(trace):
    trace = json.loads(json.dumps(trace))
    trace.pop("sim_version")
    trace["stats"].pop("wall_ms")
    error = trace["end"].get("error")
    if error:
        trace["end"]["error"] = {"type": error["type"], "line": error["line"]}
    text = json.dumps(trace, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def current_fingerprints():
    library = Library(CONTENT)
    found = {}
    for name, code, world_id, block in programs(library):
        world = library.worlds[world_id or DEFAULT_WORLD]
        options = challenge_options(block) if block else {"time_limit": 150, "realism": "off"}
        goals = block.get("goals") if block else None
        found[name] = fingerprint(run_program(code, world, library.robot, options, goals))
    return found


@pytest.fixture(scope="module")
def current():
    return current_fingerprints()


def test_every_saved_program_still_runs_the_same(current):
    saved = json.loads(SAVED.read_text())
    changed = sorted(name for name, digest in saved.items() if current.get(name, digest) != digest)
    assert not changed, f"These programs now run differently: {changed}"


def test_fingerprints_cover_all_lessons_and_playground(current):
    saved = json.loads(SAVED.read_text())
    assert len(saved) > 100
    missing = sorted(set(saved) - set(current))
    assert not missing, f"Saved programs that no longer exist (update the fingerprints): {missing}"


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        sys.exit("usage: python tests/test_unchanged.py --update")
    SAVED.write_text(json.dumps(current_fingerprints(), indent=1, sort_keys=True) + "\n")
    print(f"Saved {SAVED}")

"""Every lesson in content/courses must be well-formed and actually work.

- Examples and visualize blocks run (or fail, if they're meant to show an error).
- "What does this print?" quizzes are checked against the real output.
- Challenge solutions pass their goals; starter code runs but doesn't pass.
"""

import pytest

from conftest import CONTENT
from trainer_content import Checker, ContentError, Library

LIBRARY = Library(CONTENT)
LESSONS = list(LIBRARY.lessons())


def test_there_is_a_course():
    assert LIBRARY.courses
    assert len(LESSONS) >= 12


@pytest.mark.parametrize("course", LIBRARY.courses, ids=lambda c: c["id"])
def test_course_structure(course):
    assert Checker(LIBRARY, run=False).check_course(course) == []


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda lesson: lesson["id"])
def test_lesson(lesson):
    assert Checker(LIBRARY).check_lesson(lesson) == []


def test_challenge_refs_are_expanded():
    square = next(b for lesson in LESSONS for b in lesson["blocks"] if b.get("ref") == "square-dance")
    assert square["id"] == "square-dance"
    assert square["world"] == "practice-field"
    assert square["solution"]


def test_unknown_ref_is_an_error():
    with pytest.raises(ContentError):
        LIBRARY.resolve_lesson({"id": "x", "blocks": [{"type": "challenge", "ref": "nope"}]})


def test_checker_catches_mistakes():
    checker = Checker(LIBRARY)
    lesson = LIBRARY.resolve_lesson({
        "id": "broken",
        "title": "Broken",
        "summary": "Has problems",
        "blocks": [
            {"type": "text"},
            {"type": "dance"},
            {"type": "example", "code": "print(1 / 0)"},
            {"type": "quiz", "question": "?", "choices": ["1", "2"], "answer": 5},
            {"type": "quiz", "question": "?", "check": "output", "code": "print(2)", "choices": ["1", "2"], "answer": 0},
            {"type": "challenge", "starter": "x = 1", "world": "practice-field",
             "goals": [{"type": "end_in_zone", "zone": "moon"}]},
            {"type": "challenge", "starter": "print('hi')", "solution": "print('bye')",
             "goals": [{"type": "printed", "text": "hi"}]},
        ],
    })
    problems = "\n".join(checker.check_lesson(lesson))
    assert "text blocks need 'markdown'" in problems
    assert "unknown block type 'dance'" in problems
    assert "ZeroDivisionError" in problems
    assert "'answer' must be the index" in problems
    assert "the code prints '2', but the answer is '1'" in problems
    assert "no zone 'moon'" in problems
    assert "need a 'solution'" in problems
    assert "starter code already passes every goal" in problems
    assert "the solution fails" in problems

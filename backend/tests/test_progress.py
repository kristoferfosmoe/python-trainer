import pytest
from django.test import Client

from curriculum.models import Lesson
from progress.models import Attempt, LessonProgress

from .conftest import post, put

pytestmark = pytest.mark.django_db


def test_progress_needs_sign_in():
    assert Client().get("/api/me/state").status_code == 401
    assert put(Client(), "/api/progress/for-loops", {"page": 1}).status_code == 401


def test_progress_only_moves_forward(student, client_for):
    client = client_for(student)
    assert put(client, "/api/progress/for-loops", {"page": 2, "done": ["beep-boop"]}).json() == {
        "page": 2, "done": ["beep-boop"], "finished": False,
    }
    # An old save arriving late can't undo progress.
    merged = put(client, "/api/progress/for-loops", {"page": 1, "done": [], "finished": True}).json()
    assert merged == {"page": 2, "done": ["beep-boop"], "finished": True}
    assert put(client, "/api/progress/no-such-lesson", {"page": 1}).status_code == 404
    assert client.get("/api/me/state").json()["lessons"]["for-loops"]["page"] == 2


def test_drafts(student, client_for):
    client = client_for(student)
    assert put(client, "/api/drafts", {"key": "lesson/for-loops/square-dance", "code": "print(1)"}).status_code == 200
    assert put(client, "/api/drafts", {"key": "lesson/for-loops/square-dance", "code": "print(2)"}).status_code == 200
    assert client.get("/api/me/state").json()["drafts"] == {"lesson/for-loops/square-dance": "print(2)"}
    assert put(client, "/api/drafts", {"key": "../etc/passwd", "code": "x"}).status_code == 400
    assert put(client, "/api/drafts", {"key": "playground/free-drive", "code": "x" * 60_000}).status_code == 400


def test_attempts_record_and_mark_challenges_done(student, client_for):
    client = client_for(student)
    attempt = {
        "key": "lesson/for-loops/square-dance", "lesson_id": "for-loops", "block_id": "square-dance",
        "code": "for side in range(4): ...", "passed": False, "goals": [{"id": "no-errors", "passed": True}],
        "sim_version": "0.1.0",
    }
    assert post(client, "/api/attempts", attempt).status_code == 200
    assert not LessonProgress.objects.filter(user=student).exists()
    assert post(client, "/api/attempts", {**attempt, "passed": True}).status_code == 200
    saved = Attempt.objects.filter(user=student)
    assert saved.count() == 2
    assert saved.last().lesson_version == Lesson.objects.get(slug="for-loops").version
    assert client.get("/api/me/state").json()["lessons"]["for-loops"]["done"] == ["square-dance"]

    post(client, "/api/attempts", {"key": "playground/wall-stopper", "code": "x", "passed": True})
    assert client.get("/api/me/state").json()["solved"] == ["wall-stopper"]


def test_guest_progress_is_imported(student, client_for):
    client = client_for(student)
    put(client, "/api/progress/for-loops", {"page": 3})
    put(client, "/api/drafts", {"key": "playground/free-drive", "code": "server version"})
    state = post(client, "/api/me/import", {
        "lessons": {"for-loops": {"page": 1, "done": ["beep-boop"], "finished": False},
                    "hello-python": {"page": 4, "done": ["quotes"], "finished": True},
                    "not-a-lesson": {"page": 1}},
        "solved": ["first-drive", "../bad"],
        "drafts": {"playground/free-drive": "guest version", "playground/first-drive": "guest code"},
    }).json()
    assert state["lessons"]["for-loops"] == {"page": 3, "done": ["beep-boop"], "finished": False}
    assert state["lessons"]["hello-python"]["finished"] is True
    assert "not-a-lesson" not in state["lessons"]
    assert state["solved"] == ["first-drive"]
    # Code saved on the account wins over guest code.
    assert state["drafts"] == {"playground/free-drive": "server version", "playground/first-drive": "guest code"}

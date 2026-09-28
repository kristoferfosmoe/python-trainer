import shutil

import pytest
import yaml
from django.core.management import CommandError, call_command
from django.test import Client

from accounts.models import User
from missions.admin import MissionChallengeForm
from missions.models import MissionChallenge, MissionGame, MissionProgress

from .conftest import make_user, post, put

pytestmark = pytest.mark.django_db

FIRST, SECOND, THIRD = "crate-to-the-dock", "ring-the-bell", "there-and-back"


def ladder(client):
    return client.get("/api/missions").json()["games"][0]


def progress(client, slug, stars, score=70):
    return put(client, f"/api/missions/challenges/{slug}/progress", {"stars": stars, "score": score})


def test_import_loaded_the_harbor_game():
    game = MissionGame.objects.get(slug="harbor")
    assert game.source == "content/missions/harbor"
    assert game.spec["robot"]["id"] == "mission-bot"
    assert {a["id"] for a in game.spec["attachments"]} == {"forklift", "sweeper", "pusher"}
    challenges = list(game.challenges.all())
    assert len(challenges) == 17
    assert challenges[0].slug == FIRST and challenges[0].tier == 1
    assert challenges[-1].slug == "tournament" and challenges[-1].tier == 7
    assert challenges[0].source == "content/missions/harbor/challenges/1-01-crate-to-the-dock.yaml"
    # YAML's `on:` key comes through as "on", not true.
    lighthouse = next(m for m in game.spec["models"] if m["id"] == "lighthouse")
    assert lighthouse["on"] == {"lit": {"open": "harbor-gate"}}


def test_reimport_updates_in_place():
    before = list(MissionChallenge.objects.values_list("pk", "slug"))
    call_command("import_content", "--no-check", verbosity=0)
    assert list(MissionChallenge.objects.values_list("pk", "slug")) == before


def test_guests_see_the_ladder_without_locks_or_solutions():
    client = Client()
    game = ladder(client)
    assert game["id"] == "harbor" and game["title"] == "Harbor Rescue"
    assert [t["id"] for t in game["tiers"]] == [1, 2, 3, 4, 5, 6, 7]
    assert game["challenges"][0] == {
        "id": FIRST, "title": "Crate to the Dock", "tier": 1, "summary": "Push the crate onto the yellow dock.",
        "unlocked": None, "stars": 0, "best_score": 0,
    }
    # Guests unlock in their browser, so the server sends any challenge.
    data = client.get("/api/missions/challenges/tournament").json()
    assert "solution" not in data["challenge"] and "solution_attachments" not in data["challenge"]
    assert data["challenge"]["starter"]
    assert data["game"]["field"]["id"] == "harbor-field"
    assert "challenges" not in data["game"]
    assert client.get("/api/missions/challenges/no-such-thing").status_code == 404


def test_challenges_unlock_one_after_another(student, client_for):
    client = client_for(student)
    unlocked = [c["unlocked"] for c in ladder(client)["challenges"]]
    assert unlocked[:2] == [True, False] and not any(unlocked[1:])
    assert client.get(f"/api/missions/challenges/{FIRST}").status_code == 200
    locked = client.get(f"/api/missions/challenges/{SECOND}")
    assert locked.status_code == 403
    assert "unlock" in locked.json()["detail"]
    assert progress(client, SECOND, 3).status_code == 403

    # No stars: still locked.
    assert progress(client, FIRST, 0, 50).json() == {"stars": 0, "best_score": 50}
    assert client.get(f"/api/missions/challenges/{SECOND}").status_code == 403

    assert progress(client, FIRST, 1, 70).json() == {"stars": 1, "best_score": 70}
    assert client.get(f"/api/missions/challenges/{SECOND}").status_code == 200
    assert client.get(f"/api/missions/challenges/{THIRD}").status_code == 403
    challenges = ladder(client)["challenges"]
    assert [c["unlocked"] for c in challenges[:3]] == [True, True, False]
    assert challenges[0]["stars"] == 1 and challenges[0]["best_score"] == 70


def test_stars_only_go_up(student, client_for):
    client = client_for(student)
    progress(client, FIRST, 3, 70)
    assert progress(client, FIRST, 1, 20).json() == {"stars": 3, "best_score": 70}
    assert progress(client, FIRST, 2, 90).json() == {"stars": 3, "best_score": 90}
    assert progress(client, FIRST, 4).status_code == 422
    assert put(Client(), f"/api/missions/challenges/{FIRST}/progress", {"stars": 1}).status_code == 401


def test_staff_can_open_everything():
    staff = make_user("staffer", kind=User.Kind.ADULT, is_staff=True)
    client = Client()
    client.force_login(staff)
    assert all(c["unlocked"] for c in ladder(client)["challenges"])
    data = client.get("/api/missions/challenges/tournament").json()
    assert data["challenge"]["solution"]
    assert data["challenge"]["solution_attachments"][0] == {"E": "pusher"}


def test_coaches_see_solutions_students_dont(student, coach, client_for):
    assert "solution" not in client_for(student).get(f"/api/missions/challenges/{FIRST}").json()["challenge"]
    assert client_for(coach).get(f"/api/missions/challenges/{FIRST}").json()["challenge"]["solution"]


def test_unpublished_challenges_are_hidden(student, client_for):
    MissionChallenge.objects.filter(slug=SECOND).update(published=False)
    client = client_for(student)
    slugs = [c["id"] for c in ladder(client)["challenges"]]
    assert SECOND not in slugs
    progress(client, FIRST, 1)
    # The next one in line is now the third.
    assert client.get(f"/api/missions/challenges/{THIRD}").status_code == 200
    assert client.get(f"/api/missions/challenges/{SECOND}").status_code == 404


def test_state_drafts_and_attempts(student, client_for):
    client = client_for(student)
    progress(client, FIRST, 2, 60)
    assert put(client, "/api/drafts", {"key": f"mission/{FIRST}", "code": "print(1)"}).status_code == 200
    attempt = {"key": f"mission/{FIRST}", "code": "print(1)", "passed": True,
               "goals": [{"id": "no-errors", "passed": True}], "sim_version": "0.2.0"}
    assert post(client, "/api/attempts", attempt).status_code == 200
    state = client.get("/api/me/state").json()
    assert state["missions"] == {FIRST: {"stars": 2, "best_score": 60}}
    assert state["drafts"][f"mission/{FIRST}"] == "print(1)"
    assert state["solved"] == []  # mission attempts aren't playground challenges
    assert put(client, "/api/drafts", {"key": "mission/../x", "code": "x"}).status_code == 400


def test_guest_stars_are_imported_in_order(student, client_for):
    client = client_for(student)
    # The guest says they did 1 and 3, but not 2: 3 was never unlocked, so it isn't kept.
    state = post(client, "/api/me/import", {"missions": {
        THIRD: {"stars": 3, "best_score": 70},
        FIRST: {"stars": 2, "best_score": 70},
        "no-such-challenge": {"stars": 3},
    }}).json()
    assert state["missions"] == {FIRST: {"stars": 2, "best_score": 70}}
    state = post(client, "/api/me/import", {"missions": {
        FIRST: {"stars": 1, "best_score": 10}, SECOND: {"stars": 1, "best_score": 55}, THIRD: {"stars": 3, "best_score": 70},
    }}).json()
    assert state["missions"] == {
        FIRST: {"stars": 2, "best_score": 70},
        SECOND: {"stars": 1, "best_score": 55},
        THIRD: {"stars": 3, "best_score": 70},
    }
    assert MissionProgress.objects.filter(user=student).count() == 3


def test_import_refuses_a_broken_challenge(tmp_path, settings):
    content = tmp_path / "content"
    shutil.copytree(settings.CONTENT_DIR, content)
    path = content / "missions/harbor/challenges/1-01-crate-to-the-dock.yaml"
    challenge = yaml.safe_load(path.read_text())
    challenge["solution"] = challenge["starter"]
    path.write_text(yaml.safe_dump(challenge))
    with pytest.raises(CommandError, match="crate-to-the-dock: the solution gets 0 stars"):
        call_command("import_content", "--path", str(content), verbosity=0)


def challenge_form(spec, **fields):
    game = MissionGame.objects.get(slug="harbor")
    data = {"game": game.pk, "slug": "new-mission", "title": "New Mission", "tier": 1, "order": 99,
            "published": True, "spec_yaml": spec, **fields}
    return MissionChallengeForm(data=data)


GOOD = """
summary: Push the crate.
instructions: Push it.
runs: [{start: {x: 200, y: 330, heading: 0}}]
models: [crate]
goals: [{type: mission_done, mission: M01}]
starter: |
  from pybricks.pupdevices import Motor
  from pybricks.parameters import Port, Direction
  from pybricks.robotics import DriveBase
  drive_base = DriveBase(Motor(Port.A, Direction.COUNTERCLOCKWISE), Motor(Port.B), 56, 112)
  drive_base.straight(100)
solution: |
  from pybricks.pupdevices import Motor
  from pybricks.parameters import Port, Direction
  from pybricks.robotics import DriveBase
  drive_base = DriveBase(Motor(Port.A, Direction.COUNTERCLOCKWISE), Motor(Port.B), 56, 112)
  drive_base.straight(800)
"""


def test_admin_challenge_form_accepts_a_good_challenge():
    form = challenge_form(GOOD)
    assert form.is_valid(), form.errors
    saved = form.save()
    assert saved.spec["id"] == "new-mission" and saved.spec["title"] == "New Mission"


def test_admin_challenge_form_runs_the_solution():
    form = challenge_form(GOOD.replace("straight(800)", "straight(200)"))
    assert not form.is_valid()
    assert "the solution gets 0 stars" in str(form.errors)
    form = challenge_form(GOOD.replace("models: [crate]", "models: [spaceship]"))
    assert not form.is_valid()
    assert "the game has no model &#x27;spaceship&#x27;" in str(form.errors)


def test_admin_pages_load():
    admin = make_user("site_admin", kind=User.Kind.ADULT, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    game = MissionGame.objects.get(slug="harbor")
    challenge = MissionChallenge.objects.get(slug=FIRST)
    for url in ("/admin/missions/missiongame/", f"/admin/missions/missiongame/{game.pk}/change/",
                "/admin/missions/missionchallenge/", f"/admin/missions/missionchallenge/{challenge.pk}/change/",
                "/admin/missions/missionprogress/"):
        assert client.get(url).status_code == 200, url

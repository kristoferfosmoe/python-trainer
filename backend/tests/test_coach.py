from datetime import timedelta

import pytest
from django.core.management import CommandError, call_command
from django.test import Client
from django.utils import timezone

from accounts.models import User
from accounts.pins import pin_problem, random_pin
from teams.models import Membership, Team
from teams.permissions import sees_solutions
from teams.robot import RobotError, clean_robot

from .conftest import COACH_PASSWORD, PIN, make_user, post, put

pytestmark = pytest.mark.django_db

ROBOT = {
    "left_wheel": "E", "right_wheel": "F", "left_direction": "counterclockwise", "right_direction": "clockwise",
    "wheel_diameter": 88, "axle_track": 120, "color_sensor": "A", "ultrasonic_sensor": None,
    "left_arm": "C", "right_arm": "D",
}


def patch(client, path, data):
    return client.patch(path, data, content_type="application/json")


def sign_in(username, secret):
    client = Client()
    return post(client, "/api/auth/login", {"username": username, "secret": secret})


@pytest.fixture
def mentor(team):
    user = make_user("mentor_max")
    Membership.objects.create(user=user, team=team, role=Membership.Role.MENTOR)
    return user


@pytest.fixture
def on_team(student, team):
    Membership.objects.create(user=student, team=team)
    return student


# --- Teams -------------------------------------------------------------------------------

def test_coaches_make_teams_and_see_them(coach, team, on_team, client_for):
    client = client_for(coach)
    made = post(client, "/api/teams", {"name": "  Robo Rangers ", "season": "2026-27"}).json()
    assert made["name"] == "Robo Rangers" and len(made["join_code"]) == 6
    assert Membership.objects.get(user=coach, team_id=made["id"]).role == "coach"

    listing = client.get("/api/teams").json()
    assert listing["can_create"] is True
    assert [(t["name"], t["students"], t["role"]) for t in listing["teams"]] == [
        ("Brick Builders", 1, "coach"), ("Robo Rangers", 0, "coach"),
    ]
    assert post(client, "/api/teams", {"name": " "}).status_code == 400


def test_students_cant_make_teams_or_see_team_pages(on_team, team, client_for):
    client = client_for(on_team)
    assert post(client, "/api/teams", {"name": "My team"}).status_code == 403
    assert client.get("/api/teams").json() == {"teams": [], "can_create": False}
    assert client.get(f"/api/teams/{team.id}").status_code == 403
    assert Client().get("/api/teams").status_code == 401


def test_team_page_shows_progress_and_leaders(coach, mentor, team, on_team, client_for):
    student_client = client_for(on_team)
    put(student_client, "/api/progress/for-loops", {"page": 2, "done": ["beep-boop"], "finished": True})
    post(student_client, "/api/attempts", {"key": "playground/first-drive", "code": "x", "passed": True})
    post(student_client, "/api/attempts", {"key": "playground/first-drive", "code": "y", "passed": True})

    data = client_for(coach).get(f"/api/teams/{team.id}").json()
    assert data["role"] == "coach" and data["can_manage"] is True
    [row] = data["students"]
    assert row["lessons"]["for-loops"] == {"page": 2, "done": ["beep-boop"], "finished": True}
    assert (row["attempts"], row["solved"]) == (2, 1)
    assert row["last_active"] is not None and row["locked"] is False
    assert {(p["username"], p["role"]) for p in data["leaders"]} == {("coach_kim", "coach"), ("mentor_max", "mentor")}

    # Mentors can look, but not change anything.
    as_mentor = client_for(mentor).get(f"/api/teams/{team.id}").json()
    assert as_mentor["role"] == "mentor" and as_mentor["can_manage"] is False


def test_other_teams_coaches_see_nothing(team, on_team, client_for):
    other = make_user("other_coach", kind=User.Kind.ADULT)
    Membership.objects.create(user=other, team=Team.objects.create(name="Other"), role=Membership.Role.COACH)
    client = client_for(other)
    assert client.get(f"/api/teams/{team.id}").status_code == 403
    assert client.get(f"/api/teams/{team.id}/members/{on_team.username}").status_code == 403
    assert post(client, f"/api/teams/{team.id}/members/{on_team.username}/pin").status_code == 403


def test_staff_see_every_team(team, on_team, client_for):
    staff = make_user("site_admin", kind=User.Kind.ADULT, is_staff=True)
    client = client_for(staff)
    assert [t["role"] for t in client.get("/api/teams").json()["teams"]] == ["staff"]
    assert client.get(f"/api/teams/{team.id}").json()["can_manage"] is True


def test_new_join_code(coach, team, student, client_for):
    old = team.join_code
    new = post(client_for(coach), f"/api/teams/{team.id}/join-code").json()["join_code"]
    assert new != old
    client = client_for(student)
    assert post(client, "/api/teams/join", {"code": old}).status_code == 400
    assert post(client, "/api/teams/join", {"code": new}).status_code == 200


def test_rename_team(coach, mentor, team, client_for):
    assert patch(client_for(coach), f"/api/teams/{team.id}", {"name": "Brick Wizards"}).json()["name"] == "Brick Wizards"
    assert patch(client_for(coach), f"/api/teams/{team.id}", {"name": ""}).status_code == 400
    assert patch(client_for(mentor), f"/api/teams/{team.id}", {"name": "Mentor's team"}).status_code == 403


# --- Student accounts ---------------------------------------------------------------------

def test_coach_makes_student_accounts(coach, team, client_for):
    client = client_for(coach)
    response = post(client, f"/api/teams/{team.id}/members", {
        "students": [{"display_name": "Sam"}, {"display_name": "", "username": "RoboRita"}],
    })
    assert response.status_code == 200
    sam, rita = response.json()["created"]
    assert rita["username"] == "RoboRita" and rita["display_name"] == "RoboRita"
    assert sam["display_name"] == "Sam" and sam["username"][0].isupper()
    for made in (sam, rita):
        assert pin_problem(made["pin"]) is None
        user = User.objects.get(username=made["username"])
        assert user.kind == "student"
        assert Membership.objects.get(user=user, team=team).role == "student"
        assert sign_in(made["username"], made["pin"]).status_code == 200


def test_student_accounts_are_all_or_nothing(coach, team, student, client_for):
    client = client_for(coach)
    response = post(client, f"/api/teams/{team.id}/members", {
        "students": [{"username": "FreshName"}, {"username": student.username.lower()}, {"username": "x"}],
    })
    assert response.status_code == 400
    assert "already has the username" in response.json()["detail"]
    assert "3 to 20 letters" in response.json()["detail"]
    assert not User.objects.filter(username="FreshName").exists()
    assert post(client, f"/api/teams/{team.id}/members", {"students": []}).status_code == 400
    too_many = {"students": [{"display_name": f"Kid {i}"} for i in range(11)]}
    assert post(client, f"/api/teams/{team.id}/members", too_many).status_code == 400


def test_mentors_cant_make_accounts(mentor, team, client_for):
    response = post(client_for(mentor), f"/api/teams/{team.id}/members", {"students": [{"display_name": "Sam"}]})
    assert response.status_code == 403


def test_new_pin_unlocks_and_replaces_the_old_one(coach, team, on_team, client_for):
    on_team.locked_until = timezone.now() + timedelta(minutes=5)
    on_team.save()
    client = client_for(coach)
    assert client.get(f"/api/teams/{team.id}").json()["students"][0]["locked"] is True

    # Whoever has the new PIN can sign in as the student, so the coach types their password first.
    url = f"/api/teams/{team.id}/members/{on_team.username.lower()}/pin"
    asked = post(client, url)
    assert asked.status_code == 403 and asked.json()["code"] == "password_needed"
    assert post(client, "/api/auth/confirm", {"secret": "not my password"}).status_code == 400
    assert post(client, url).status_code == 403
    assert post(client, "/api/auth/confirm", {"secret": COACH_PASSWORD}).status_code == 200
    fresh = post(client, url).json()
    assert fresh["username"] == on_team.username and pin_problem(fresh["pin"]) is None
    assert sign_in(on_team.username, PIN).status_code == 401
    assert sign_in(on_team.username, fresh["pin"]).status_code == 200


def test_unlock(coach, team, on_team, client_for):
    on_team.locked_until = timezone.now() + timedelta(minutes=5)
    on_team.failed_logins = 3
    on_team.save()
    assert post(client_for(coach), f"/api/teams/{team.id}/members/{on_team.username}/unlock").status_code == 200
    on_team.refresh_from_db()
    assert on_team.locked_until is None and on_team.failed_logins == 0
    assert sign_in(on_team.username, PIN).status_code == 200


def test_coaches_only_change_kids_accounts(coach, mentor, team, on_team, client_for):
    other_coach = make_user("coach_two", kind=User.Kind.ADULT)
    Membership.objects.create(user=other_coach, team=team, role=Membership.Role.COACH)
    sneaky_admin = make_user("sneaky_admin", is_staff=True)  # a "student" account with admin rights
    Membership.objects.create(user=sneaky_admin, team=team)
    client = client_for(coach)
    assert post(client, "/api/auth/confirm", {"secret": COACH_PASSWORD}).status_code == 200
    for name in ("coach_two", "sneaky_admin"):
        assert post(client, f"/api/teams/{team.id}/members/{name}/pin").status_code == 403
        assert client.delete(f"/api/teams/{team.id}/members/{name}").status_code == 403
    assert post(client, f"/api/teams/{team.id}/members/nobody_here/pin").status_code == 404
    # Mentors can't reset PINs; coaches can reset a mentor's.
    assert post(client_for(mentor), f"/api/teams/{team.id}/members/{on_team.username}/pin").status_code == 403
    assert post(client, f"/api/teams/{team.id}/members/mentor_max/pin").status_code == 200


def test_mentor_role_and_removing_from_the_team(coach, team, on_team, client_for):
    client = client_for(coach)
    url = f"/api/teams/{team.id}/members/{on_team.username}"
    assert patch(client, url, {"role": "mentor"}).status_code == 200
    assert sees_solutions(on_team)
    data = client.get(f"/api/teams/{team.id}").json()
    assert data["students"] == [] and "BraveOtter42" in [p["username"] for p in data["leaders"]]
    assert patch(client, url, {"role": "coach"}).status_code == 400
    assert patch(client, url, {"role": "student"}).status_code == 200

    assert client.delete(url).status_code == 200
    assert not Membership.objects.filter(user=on_team, team=team).exists()
    assert User.objects.filter(username=on_team.username).exists()  # the account and its work stay


# --- One student's work ---------------------------------------------------------------------

def test_student_page_shows_challenges_with_code(coach, mentor, team, on_team, client_for):
    student_client = client_for(on_team)
    lesson_attempt = {"key": "lesson/for-loops/square-dance", "lesson_id": "for-loops", "block_id": "square-dance"}
    post(student_client, "/api/attempts", {**lesson_attempt, "code": "first try", "passed": False})
    post(student_client, "/api/attempts", {**lesson_attempt, "code": "it works", "passed": True})
    post(student_client, "/api/attempts", {**lesson_attempt, "code": "trying more", "passed": False})
    put(student_client, "/api/drafts", {"key": "lesson/for-loops/square-dance", "code": "editing now"})
    put(student_client, "/api/drafts", {"key": "playground/wall-stopper", "code": "never ran"})

    data = client_for(coach).get(f"/api/teams/{team.id}/members/{on_team.username}").json()
    assert data["student"]["username"] == "BraveOtter42"
    assert data["lessons"]["for-loops"]["done"] == ["square-dance"]
    by_key = {c["key"]: c for c in data["challenges"]}
    square = by_key["lesson/for-loops/square-dance"]
    assert (square["title"], square["where"], square["lesson"]) == ("Square Dance", "Repeat with for", "for-loops")
    assert (square["attempts"], square["passed"], square["last_passed"]) == (3, True, False)
    assert (square["last_code"], square["passed_code"], square["draft"]) == ("trying more", "it works", "editing now")
    wall = by_key["playground/wall-stopper"]
    assert (wall["title"], wall["where"], wall["attempts"], wall["draft"]) == ("Wall Stopper", "Playground", 0, "never ran")

    # Mentors can look at students, but only coaches can look at mentors.
    assert client_for(mentor).get(f"/api/teams/{team.id}/members/{on_team.username}").status_code == 200
    assert client_for(mentor).get(f"/api/teams/{team.id}/members/mentor_max").status_code == 403
    assert client_for(coach).get(f"/api/teams/{team.id}/members/mentor_max").status_code == 200
    assert client_for(coach).get(f"/api/teams/{team.id}/members/coach_kim").status_code == 403


# --- The team's robot ---------------------------------------------------------------------------

def test_team_robot_reaches_students(coach, mentor, team, on_team, client_for):
    client = client_for(coach)
    response = patch(client, f"/api/teams/{team.id}", {"robot": ROBOT})
    assert response.status_code == 200
    assert response.json()["robot"]["left_wheel"] == "E"
    me = client_for(on_team).get("/api/auth/me").json()["user"]
    assert me["teams"][0]["robot"]["wheel_diameter"] == 88

    bad = patch(client, f"/api/teams/{team.id}", {"robot": {**ROBOT, "color_sensor": "E"}})
    assert bad.status_code == 400 and "can't both use port E" in bad.json()["detail"]
    assert patch(client_for(mentor), f"/api/teams/{team.id}", {"robot": ROBOT}).status_code == 403
    # Back to "built like the Trainer Bot".
    assert patch(client, f"/api/teams/{team.id}", {"robot": {}}).json()["robot"] is None


@pytest.mark.parametrize("change, message", [
    ({"left_wheel": None}, "Pick a port for the left wheel motor"),
    ({"right_wheel": "G"}, "ports are A to F"),
    ({"left_direction": "sideways"}, "clockwise or counterclockwise"),
    ({"wheel_diameter": 5}, "from 20 to 200"),
    ({"axle_track": "wide"}, "from 40 to 400"),
    ({"wings": "A"}, "Unknown robot settings: wings"),
])
def test_robot_checks(change, message):
    with pytest.raises(RobotError, match=message):
        clean_robot({**ROBOT, **change})


def test_robot_is_tidied():
    robot = clean_robot({**ROBOT, "left_wheel": "e", "left_direction": "COUNTERCLOCKWISE", "axle_track": 120.0,
                         "wheel_diameter": 62.4})
    assert (robot["left_wheel"], robot["left_direction"]) == ("E", "counterclockwise")
    assert (robot["axle_track"], robot["wheel_diameter"]) == (120, 62.4)
    assert clean_robot({}) == {} and clean_robot(None) == {}


# --- Command line and PINs ------------------------------------------------------------------------

def test_create_coach_command():
    call_command("create_coach", "coach_lee", password="a long enough password", team="Robo Rangers",
                 season="2026-27", stdout=open("/dev/null", "w"))
    coach = User.objects.get(username="coach_lee")
    assert coach.kind == "adult" and coach.check_password("a long enough password")
    team = Team.objects.get(name="Robo Rangers")
    assert Membership.objects.get(user=coach, team=team).role == "coach"
    # Again: a new password, same team, no duplicates.
    call_command("create_coach", "coach_lee", password="another long password", team="robo rangers",
                 stdout=open("/dev/null", "w"))
    coach.refresh_from_db()
    assert coach.check_password("another long password")
    assert Team.objects.filter(name__iexact="Robo Rangers").count() == 1

    make_user("KidAccount")
    with pytest.raises(CommandError, match="student account"):
        call_command("create_coach", "kidaccount", password="a long enough password")
    with pytest.raises(CommandError):
        call_command("create_coach", "coach_short", password="short")


def test_random_pins_are_never_easy():
    assert all(pin_problem(random_pin()) is None for _ in range(500))

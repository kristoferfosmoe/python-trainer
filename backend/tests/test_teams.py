import pytest
from django.test import Client

from accounts.models import User
from teams.models import CODE_ALPHABET, Membership, Team
from teams.permissions import can_view_student, sees_solutions

from .conftest import make_user, post

pytestmark = pytest.mark.django_db


def test_join_codes_are_easy_to_read(team):
    assert len(team.join_code) == 6
    assert set(team.join_code) <= set(CODE_ALPHABET)
    codes = {Team.objects.create(name=f"T{i}").join_code for i in range(30)}
    assert len(codes) == 30


def test_join_a_team(student, team, client_for):
    client = client_for(student)
    response = post(client, "/api/teams/join", {"code": team.join_code})
    assert response.status_code == 200
    assert response.json()["user"]["teams"][0]["name"] == "Brick Builders"
    assert post(client, "/api/teams/join", {"code": team.join_code}).status_code == 200
    assert Membership.objects.filter(user=student).count() == 1
    assert post(client, "/api/teams/join", {"code": "ZZZZZZ"}).status_code == 400
    assert post(Client(), "/api/teams/join", {"code": team.join_code}).status_code == 401


def test_who_can_see_a_students_work(student, team, coach):
    Membership.objects.create(user=student, team=team)
    mentor = make_user("mentor_max")
    Membership.objects.create(user=mentor, team=team, role=Membership.Role.MENTOR)
    teammate = make_user("teammate")
    Membership.objects.create(user=teammate, team=team)
    other_coach = make_user("other_coach", kind=User.Kind.ADULT)
    Membership.objects.create(user=other_coach, team=Team.objects.create(name="Other"), role=Membership.Role.COACH)
    staff = make_user("staffer", kind=User.Kind.ADULT, is_staff=True)

    assert can_view_student(student, student)
    assert can_view_student(coach, student)
    assert can_view_student(mentor, student)
    assert can_view_student(staff, student)
    assert not can_view_student(teammate, student)
    assert not can_view_student(other_coach, student)
    assert not can_view_student(student, coach)  # coaches aren't "students" on the team

    assert sees_solutions(coach) and sees_solutions(mentor) and sees_solutions(staff)
    assert not sees_solutions(student) and not sees_solutions(teammate)


def test_team_view_for_coaches(student, team, coach, client_for):
    Membership.objects.create(user=student, team=team)
    post(client_for(student), "/api/attempts", {"key": "playground/first-drive", "code": "x", "passed": True})
    response = client_for(coach).get(f"/api/teams/{team.id}/students")
    assert response.status_code == 200
    data = response.json()
    assert data["team"]["join_code"] == team.join_code
    assert [s["username"] for s in data["students"]] == ["BraveOtter42"]
    assert data["students"][0]["attempts"] == 1
    assert client_for(student).get(f"/api/teams/{team.id}/students").status_code == 403
    assert Client().get(f"/api/teams/{team.id}/students").status_code == 401

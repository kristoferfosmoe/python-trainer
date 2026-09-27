"""Teams have at most settings.TEAM_MAX_MEMBERS members (students, mentors
and coaches all count). These tests use a small limit."""

import pytest
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from teams.models import Membership, Team

from .conftest import COACH_PASSWORD, PIN, make_user, post

pytestmark = pytest.mark.django_db


@pytest.fixture
def full_team(coach, team, settings):
    """Brick Builders with room for 3: the coach and two students fill it."""
    settings.TEAM_MAX_MEMBERS = 3
    for name in ("KidOne11", "KidTwo22"):
        Membership.objects.create(user=make_user(name), team=team)
    return team


def test_students_cant_join_a_full_team(full_team, student, client_for):
    response = post(client_for(student), "/api/teams/join", {"code": full_team.join_code})
    assert response.status_code == 409
    assert "Ask your coach to make room" in response.json()["detail"]
    assert not Membership.objects.filter(user=student).exists()
    # Someone already on the team can use the code again.
    one = User.objects.get(username="KidOne11")
    assert post(client_for(one), "/api/teams/join", {"code": full_team.join_code}).status_code == 200


def test_signing_up_with_a_full_teams_code_makes_no_account(full_team):
    response = post(Client(), "/api/auth/signup", {"username": "LateKid33", "pin": PIN, "join_code": full_team.join_code})
    assert response.status_code == 409
    assert "Ask your coach to make room" in response.json()["detail"]
    assert not User.objects.filter(username="LateKid33").exists()


def test_coaches_are_told_to_remove_a_member_first(full_team, coach, client_for):
    client = client_for(coach)
    page = client.get(f"/api/teams/{full_team.id}").json()
    assert (page["members"], page["max_members"]) == (3, 3)
    response = post(client, f"/api/teams/{full_team.id}/members", {"students": [{"display_name": "Sam"}]})
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Your team has 3 members, the most a team can have. Remove a member before adding another."
    )
    assert client.delete(f"/api/teams/{full_team.id}/members/KidOne11").status_code == 200
    too_many = post(client, f"/api/teams/{full_team.id}/members",
                    {"students": [{"display_name": "Sam"}, {"display_name": "Priya"}]})
    assert too_many.status_code == 409
    assert "room for 1 more member (a team can have 3)" in too_many.json()["detail"]
    assert post(client, f"/api/teams/{full_team.id}/members", {"students": [{"display_name": "Sam"}]}).status_code == 200
    assert full_team.memberships.count() == 3


def test_the_admin_wont_overfill_a_team(full_team):
    admin = make_user("site_admin", kind=User.Kind.ADULT, is_staff=True, is_superuser=True)
    extra = make_user("ExtraKid44")
    client = Client()
    client.force_login(admin)
    response = client.post("/admin/teams/membership/add/", {"user": extra.pk, "team": full_team.pk, "role": "student"})
    assert response.status_code == 200  # the form again, with the error
    assert "Remove a member before adding another" in response.content.decode()
    assert not Membership.objects.filter(user=extra).exists()


def test_create_coach_wont_overfill_a_team(full_team):
    make_user("coach_two", kind=User.Kind.ADULT, secret=COACH_PASSWORD)
    with pytest.raises(CommandError, match="is full"):
        call_command("create_coach", "coach_two", "--password", COACH_PASSWORD, "--team", full_team.name)


def test_the_teams_list_takes_the_same_queries_for_any_number_of_teams(coach, team, client_for):
    client = client_for(coach)

    def queries():
        with CaptureQueriesContext(connection) as captured:
            assert client.get("/api/teams").status_code == 200
        return len(captured)

    one_team = queries()
    for n in range(5):
        Membership.objects.create(user=coach, team=Team.objects.create(name=f"Team {n}"), role=Membership.Role.COACH)
    assert queries() == one_team

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import LoginFailure, User
from accounts.pins import pin_problem, random_pin, suggest_username, username_problem
from teams.models import Membership

from .conftest import PIN, make_user, post

pytestmark = pytest.mark.django_db


def signup(client, **data):
    body = {"username": "BraveOtter42", "pin": PIN, **data}
    return post(client, "/api/auth/signup", body)


def test_signup_signs_you_in():
    client = Client()
    response = signup(client, display_name="Sam", avatar="🦊")
    assert response.status_code == 200
    me = client.get("/api/auth/me").json()["user"]
    assert me["username"] == "BraveOtter42"
    assert me["display_name"] == "Sam"
    assert me["avatar"] == "🦊"
    assert me["kind"] == "student"
    user = User.objects.get(username="BraveOtter42")
    assert user.check_password(PIN)
    assert user.email == ""


@pytest.mark.parametrize("pin, message", [
    ("12345", "exactly 6 numbers"),
    ("12a456", "exactly 6 numbers"),
    ("111111", "all the same"),
    ("123456", "counting"),
    ("987654", "counting"),
    ("121212", "repeats"),
    ("408408", "repeats"),
])
def test_weak_pins_are_rejected(pin, message):
    assert message in pin_problem(pin)
    response = signup(Client(), pin=pin)
    assert response.status_code == 400
    assert message in response.json()["detail"]


@pytest.mark.parametrize("name", ["ab", "1abc", "has space", "admin", "x" * 21, "bad-dash"])
def test_bad_usernames_are_rejected(name):
    assert username_problem(name)
    assert signup(Client(), username=name).status_code == 400


def test_usernames_are_unique_ignoring_case():
    assert signup(Client()).status_code == 200
    response = signup(Client(), username="braveotter42")
    assert response.status_code == 400
    assert "already has that username" in response.json()["detail"]


def test_signup_with_a_team_code(team):
    client = Client()
    assert signup(client, join_code=team.join_code.lower()).status_code == 200
    me = client.get("/api/auth/me").json()["user"]
    assert me["teams"] == [{"id": team.id, "name": "Brick Builders", "role": "student", "robot": None}]
    assert signup(Client(), username="Other", join_code="NOPE99").status_code == 400
    assert not User.objects.filter(username="Other").exists()


def test_sign_in_and_out(student):
    client = Client()
    response = post(client, "/api/auth/login", {"username": "braveotter42", "secret": PIN})
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "BraveOtter42"
    assert post(client, "/api/auth/logout").json() == {"user": None}
    assert client.get("/api/auth/me").json() == {"user": None}


def test_wrong_pin(student):
    response = post(Client(), "/api/auth/login", {"username": "BraveOtter42", "secret": "000001"})
    assert response.status_code == 401
    assert "don't match" in response.json()["detail"]
    unknown = post(Client(), "/api/auth/login", {"username": "Nobody", "secret": PIN})
    assert unknown.json()["detail"] == response.json()["detail"]


def test_account_locks_after_too_many_wrong_pins(student, settings):
    settings.LOGIN_IP_MAX_FAILURES = 100
    client = Client()
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": "000001"})
    locked = post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": PIN})
    assert locked.status_code == 429
    assert "locked" in locked.json()["detail"]
    # After the lock runs out, the right PIN works again.
    User.objects.filter(pk=student.pk).update(locked_until=timezone.now() - timedelta(seconds=1))
    assert post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": PIN}).status_code == 200
    student.refresh_from_db()
    assert student.failed_logins == 0 and student.locked_until is None


def test_too_many_failures_from_one_computer(student, settings):
    settings.LOGIN_IP_MAX_FAILURES = 3
    client = Client()
    for name in ["a1x", "b2y", "c3z"]:
        post(client, "/api/auth/login", {"username": name, "secret": PIN})
    blocked = post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": PIN})
    assert blocked.status_code == 429
    assert "this computer" in blocked.json()["detail"]
    other_computer = Client(REMOTE_ADDR="10.0.0.9")
    assert post(other_computer, "/api/auth/login", {"username": "BraveOtter42", "secret": PIN}).status_code == 200


def test_forwarded_for_is_used_only_when_trusted(settings):
    from django.test import RequestFactory

    from accounts.auth import client_ip

    request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4", REMOTE_ADDR="172.18.0.2")
    settings.TRUST_FORWARDED_FOR = False
    assert client_ip(request) == "172.18.0.2"
    settings.TRUST_FORWARDED_FOR = True
    assert client_ip(request) == "1.2.3.4"


def test_csrf_is_required_for_sign_in(student):
    client = Client(enforce_csrf_checks=True)
    assert post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": PIN}).status_code == 403
    client.get("/api/csrf")
    token = client.cookies["csrftoken"].value
    response = client.post(
        "/api/auth/login", {"username": "BraveOtter42", "secret": PIN},
        content_type="application/json", HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200


def test_adults_sign_in_with_a_password(coach):
    response = post(Client(), "/api/auth/login", {"username": "coach_kim", "secret": "a long coach password"})
    assert response.status_code == 200
    assert response.json()["user"]["kind"] == "adult"
    assert response.json()["user"]["teams"][0]["role"] == "coach"


def test_suggested_names_and_pins_are_valid():
    for _ in range(50):
        assert username_problem(suggest_username()) is None
        assert pin_problem(random_pin()) is None
    name = Client().get("/api/auth/suggest-username").json()["username"]
    assert username_problem(name) is None


def test_reset_pin_admin_action(student, team):
    admin = make_user("site_admin", kind=User.Kind.ADULT, secret="a very long admin password",
                      is_staff=True, is_superuser=True)
    Membership.objects.create(user=student, team=team)
    client = Client()
    client.force_login(admin)
    response = client.post(
        "/admin/accounts/user/", {"action": "reset_pin", "_selected_action": [student.pk]}, follow=True,
    )
    messages = [str(m) for m in response.context["messages"]]
    assert any(m.startswith("New PIN for BraveOtter42: ") for m in messages)
    new_pin = next(m for m in messages if m.startswith("New PIN")).rsplit(" ", 1)[1]
    student.refresh_from_db()
    assert student.check_password(new_pin)


ADMIN_PASSWORD = "a very long admin password"


def admin_login(client, username, password):
    return client.post("/admin/login/?next=/admin/", {"username": username, "password": password})


def test_admin_sign_in_works_for_staff_only(student):
    make_user("site_admin", kind=User.Kind.ADULT, secret=ADMIN_PASSWORD, is_staff=True)
    client = Client()
    response = admin_login(client, "site_admin", ADMIN_PASSWORD)
    assert response.status_code == 302
    assert client.get("/admin/").status_code == 200
    kid = admin_login(Client(), "BraveOtter42", PIN)
    assert kid.status_code == 200
    assert "staff account" in kid.content.decode()


def test_admin_sign_in_locks_like_the_app(settings):
    settings.LOGIN_IP_MAX_FAILURES = 100
    make_user("site_admin", kind=User.Kind.ADULT, secret=ADMIN_PASSWORD, is_staff=True)
    client = Client()
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        assert admin_login(client, "site_admin", "guess guess guess").status_code == 200
    locked = admin_login(client, "site_admin", ADMIN_PASSWORD)
    assert locked.status_code == 200
    assert "locked for 5 more minutes after too many wrong passwords" in locked.content.decode()
    assert "_auth_user_id" not in client.session


def test_admin_sign_in_counts_toward_the_computer_block(student, settings):
    settings.LOGIN_IP_MAX_FAILURES = 2
    client = Client()
    for name in ["a1x", "b2y"]:
        admin_login(client, name, "guess guess guess")
    blocked = post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": PIN})
    assert blocked.status_code == 429
    assert "this computer" in admin_login(client, "BraveOtter42", PIN).content.decode()


def test_typos_followed_by_the_right_pin_dont_count_against_the_computer(student, settings):
    # A whole school shares one address; kids mistyping their own PIN shouldn't block it.
    settings.LOGIN_IP_MAX_FAILURES = 3
    client = Client()
    for _ in range(2):
        post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": "000001"})
    assert post(client, "/api/auth/login", {"username": "BraveOtter42", "secret": PIN}).status_code == 200
    assert not LoginFailure.objects.filter(username="braveotter42").exists()
    make_user("QuietFox11")
    for name in ["a1x", "b2y"]:
        post(Client(), "/api/auth/login", {"username": name, "secret": PIN})
    assert post(Client(), "/api/auth/login", {"username": "QuietFox11", "secret": PIN}).status_code == 200
    # Misses that were never followed by the right PIN still count.
    assert LoginFailure.objects.count() == 2


def test_limits_count_ipv6_addresses_by_network():
    from accounts.auth import limit_key

    assert limit_key("2001:db8:1:2:aaaa::1") == limit_key("2001:db8:1:2:bbbb::9") == "2001:db8:1:2::"
    assert limit_key("2001:db8:1:3::1") != limit_key("2001:db8:1:2::1")
    assert limit_key("::ffff:10.0.0.5") == "10.0.0.5"
    assert limit_key("10.0.0.5") == "10.0.0.5"
    assert limit_key("not an address") == "0.0.0.0"


def test_new_accounts_are_limited_per_computer(settings):
    settings.SIGNUP_MAX_PER_HOUR = 2
    for name in ["KidOne11", "KidTwo22"]:
        assert signup(Client(), username=name).status_code == 200
    third = signup(Client(), username="KidThree33")
    assert third.status_code == 429
    assert "ask your coach" in third.json()["detail"]
    assert signup(Client(REMOTE_ADDR="10.0.0.9"), username="KidThree33").status_code == 200


def test_wrong_team_codes_are_limited_per_computer(team, settings):
    settings.JOIN_CODE_MAX_FAILURES = 2
    for name in ["KidOne11", "KidTwo22"]:
        assert signup(Client(), username=name, join_code="NOPE99").status_code == 400
    blocked = signup(Client(), username="KidThree33", join_code=team.join_code)
    assert blocked.status_code == 429
    assert "wrong team codes" in blocked.json()["detail"]
    client = Client()
    client.force_login(make_user("KidFour44"))
    assert post(client, "/api/teams/join", {"code": team.join_code}).status_code == 429
    other = Client(REMOTE_ADDR="10.0.0.9")
    assert signup(other, username="KidThree33", join_code=team.join_code).status_code == 200

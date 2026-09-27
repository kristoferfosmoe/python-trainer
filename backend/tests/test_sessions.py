import time

import pytest

from accounts import sessions

from .conftest import COACH_PASSWORD, PIN, post

pytestmark = pytest.mark.django_db


def signed_in(client, username, secret):
    assert post(client, "/api/auth/login", {"username": username, "secret": secret}).status_code == 200
    assert client.get("/api/auth/me").json()["user"]["username"] == username
    return client


def set_session(client, **values):
    session = client.session
    session.update(values)
    session.save()


def test_coaches_are_signed_out_after_a_while_without_use(client, coach, settings):
    signed_in(client, "coach_kim", COACH_PASSWORD)
    assert client.session.get_expiry_age() == settings.ADULT_SESSION_HOURS * 3600
    set_session(client, **{sessions.SEEN: time.time() - settings.ADULT_IDLE_MINUTES * 60 + 30})
    assert client.get("/api/auth/me").json()["user"] is not None
    set_session(client, **{sessions.SEEN: time.time() - settings.ADULT_IDLE_MINUTES * 60 - 1})
    assert client.get("/api/auth/me").json()["user"] is None


def test_coaches_are_signed_out_at_the_end_of_the_day(client, coach, settings):
    signed_in(client, "coach_kim", COACH_PASSWORD)
    set_session(client, **{sessions.STARTED: time.time() - settings.ADULT_SESSION_HOURS * 3600 - 1})
    assert client.get("/api/auth/me").json()["user"] is None


def test_students_stay_signed_in_for_a_month(client, student, settings):
    signed_in(client, "BraveOtter42", PIN)
    assert client.session.get_expiry_age() == settings.SESSION_COOKIE_AGE
    assert sessions.STARTED not in client.session


def test_confirming_needs_the_right_password_and_a_sign_in(client, coach):
    assert post(client, "/api/auth/confirm", {"secret": COACH_PASSWORD}).status_code == 401
    signed_in(client, "coach_kim", COACH_PASSWORD)
    assert post(client, "/api/auth/confirm", {"secret": "nope nope nope"}).status_code == 400
    assert post(client, "/api/auth/confirm", {"secret": COACH_PASSWORD}).status_code == 200
    assert sessions.CONFIRMED in client.session

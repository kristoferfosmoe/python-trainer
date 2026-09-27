import pytest
from django.core.management import call_command
from django.test import Client

from accounts.models import User
from teams.models import Membership, Team

PIN = "314159"


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Import the real lessons once; each test runs in a transaction on top."""
    with django_db_blocker.unblock():
        call_command("import_content", "--no-check", verbosity=0)


def make_user(username, kind=User.Kind.STUDENT, secret=PIN, **extra):
    return User.objects.create_user(username=username, password=secret, kind=kind, **extra)


@pytest.fixture
def student(db):
    return make_user("BraveOtter42")


@pytest.fixture
def client_for(db):
    def _client(user):
        client = Client()
        client.force_login(user)
        return client
    return _client


@pytest.fixture
def team(db):
    return Team.objects.create(name="Brick Builders", season="2026-27")


@pytest.fixture
def coach(team):
    user = make_user("coach_kim", kind=User.Kind.ADULT, secret="a long coach password")
    Membership.objects.create(user=user, team=team, role=Membership.Role.COACH)
    return user


def post(client, path, data=None):
    return client.post(path, data or {}, content_type="application/json")


def put(client, path, data=None):
    return client.put(path, data or {}, content_type="application/json")

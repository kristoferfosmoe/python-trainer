"""Sign up, sign in and out, and who's signed in."""

from django.contrib.auth import login, logout
from django.db import IntegrityError, transaction
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.utils import check_csrf

from teams.models import Membership, Team

from . import limits
from .auth import SignInError, sign_in
from .models import AVATARS, User
from .pins import pin_problem, suggest_username, username_problem

router = Router(tags=["auth"])


class TeamOut(Schema):
    id: int
    name: str
    role: str
    robot: dict | None = None  # the team's real robot, for copying code to Pybricks


class MeOut(Schema):
    username: str
    display_name: str
    avatar: str
    kind: str
    is_staff: bool
    teams: list[TeamOut]


class MeResponse(Schema):
    user: MeOut | None = None


def me_data(user):
    if not user.is_authenticated:
        return None
    return {
        "username": user.username,
        "display_name": user.shown_name,
        "avatar": user.avatar,
        "kind": user.kind,
        "is_staff": user.is_staff,
        "teams": [
            {"id": m.team_id, "name": m.team.name, "role": m.role, "robot": m.team.robot or None}
            for m in user.memberships.select_related("team").order_by("team__name")
        ],
    }


def require_csrf(request):
    """Session endpoints without auth still need CSRF protection (login CSRF)."""
    if check_csrf(request) is not None:
        raise HttpError(403, "Your session expired. Reload the page and try again.")


def find_team(request, code):
    """The team with this join code. Wrong codes are limited per computer,
    so codes can't be found by trying them all."""
    limits.check(request, limits.WRONG_CODE)
    team = Team.objects.filter(join_code=(code or "").strip().upper()).first()
    if team is None:
        limits.count(request, limits.WRONG_CODE)
        raise HttpError(400, "We couldn't find a team with that code. Check it with your coach.")
    return team


class SignupIn(Schema):
    username: str
    pin: str
    display_name: str = ""
    avatar: str = AVATARS[0]
    join_code: str = ""


@router.post("/signup", response=MeResponse)
def signup(request, data: SignupIn):
    require_csrf(request)
    limits.check(request, limits.SIGNUP)
    username = data.username.strip()
    problem = username_problem(username) or pin_problem(data.pin)
    if problem:
        raise HttpError(400, problem)
    if User.objects.filter(username__iexact=username).exists():
        raise HttpError(400, "Someone already has that username. Try another one, or press 🎲 to make one up.")
    team = find_team(request, data.join_code) if data.join_code.strip() else None
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=data.pin,
                kind=User.Kind.STUDENT,
                display_name=data.display_name.strip()[:40],
                avatar=data.avatar if data.avatar in AVATARS else AVATARS[0],
            )
            if team:
                Membership.objects.create(user=user, team=team, role=Membership.Role.STUDENT)
    except IntegrityError:
        raise HttpError(400, "Someone already has that username. Try another one.")
    limits.count(request, limits.SIGNUP)
    login(request, user)
    return {"user": me_data(user)}


class LoginIn(Schema):
    username: str
    secret: str  # a PIN, or a password for adults


@router.post("/login", response=MeResponse)
def login_view(request, data: LoginIn):
    require_csrf(request)
    try:
        user = sign_in(request, data.username, data.secret)
    except SignInError as error:
        raise HttpError(error.status, str(error))
    return {"user": me_data(user)}


@router.post("/logout", response=MeResponse)
def logout_view(request):
    require_csrf(request)
    logout(request)
    return {"user": None}


@router.get("/me", response=MeResponse)
def me(request):
    return {"user": me_data(request.user)}


@router.get("/suggest-username")
def suggest(request):
    for _ in range(20):
        name = suggest_username()
        if not User.objects.filter(username__iexact=name).exists():
            return {"username": name}
    return {"username": suggest_username()}

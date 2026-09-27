"""Joining teams, and the coach tools.

Coaches and mentors can see their team's progress; only coaches change
things (see permissions.py). PINs are shown once, right after they're made,
and never stored where anyone can read them.
"""

import random
from collections import defaultdict

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

from accounts.api import MeResponse, find_team, me_data
from accounts.models import AVATARS, User
from accounts.pins import random_pin, suggest_username, username_problem
from curriculum.models import Lesson, PlaygroundChallenge
from progress.models import Attempt, CodeDraft, LessonProgress

from .models import Membership, Team, new_join_code
from .permissions import LEADER_ROLES, can_manage_account, coaches_team, leads_team
from .robot import RobotError, clean_robot

router = Router(tags=["teams"], auth=django_auth)

MAX_NEW_STUDENTS = 10  # per request: each new PIN takes a moment to hash
MAX_TEAM_SIZE = 200
MAX_ATTEMPTS_SHOWN = 2000
STUDENT = Membership.Role.STUDENT
MENTOR = Membership.Role.MENTOR
COACH = Membership.Role.COACH


# --- Helpers ---------------------------------------------------------------------------

def _team(request, team_id, manage=False):
    team = get_object_or_404(Team, id=team_id)
    if manage and not coaches_team(request.user, team):
        raise HttpError(403, "Only this team's coaches can change this.")
    if not leads_team(request.user, team):
        raise HttpError(403, "Only this team's coaches and mentors can see this.")
    return team


def _member(team, username):
    membership = team.memberships.select_related("user").filter(user__username__iexact=username).first()
    if membership is None:
        raise HttpError(404, "That person isn't on this team.")
    return membership


def _kid(membership):
    """A student or mentor whose account a coach may change."""
    if membership.role == COACH or not can_manage_account(membership.user):
        raise HttpError(403, "Coaches can only change students' and mentors' accounts.")
    return membership


def _iso(moment):
    return moment.isoformat() if moment else None


def _role(user, team):
    membership = Membership.objects.filter(user=user, team=team).first()
    if membership and membership.role in LEADER_ROLES:
        return membership.role
    return "staff"


def team_data(team):
    return {
        "id": team.id, "name": team.name, "season": team.season, "join_code": team.join_code,
        "robot": team.robot or None,
    }


def _person(membership, now):
    user = membership.user
    return {
        "username": user.username,
        "display_name": user.shown_name,
        "avatar": user.avatar,
        "role": membership.role,
        "locked": bool(user.locked_until and user.locked_until > now),
        "joined_at": _iso(membership.joined_at),
    }


def _last_active(users):
    """Each user's most recent sign-in, run, saved code or lesson step."""
    latest = {user.id: user.last_login for user in users}
    for model, field in ((Attempt, "created_at"), (LessonProgress, "updated_at"), (CodeDraft, "updated_at")):
        rows = model.objects.filter(user__in=latest).values("user").annotate(t=Max(field))
        for row in rows:
            if row["t"] and (latest[row["user"]] is None or row["t"] > latest[row["user"]]):
                latest[row["user"]] = row["t"]
    return latest


def _free_username(taken):
    for _ in range(50):
        name = suggest_username()
        if name.lower() not in taken and not User.objects.filter(username__iexact=name).exists():
            return name
    raise HttpError(503, "Couldn't make up enough usernames. Please try again.")


def _challenge_labels(keys):
    """What to call each editor: its challenge title and where it is."""
    slugs = {key.split("/")[1] for key in keys if key.startswith("lesson/")}
    lessons = {lesson.slug: lesson for lesson in Lesson.objects.filter(slug__in=slugs)}
    playground = dict(PlaygroundChallenge.objects.values_list("slug", "title"))
    labels = {}
    for key in keys:
        parts = key.split("/")
        if parts[0] == "playground":
            labels[key] = {"title": playground.get(parts[1], parts[1]), "where": "Playground", "lesson": None}
            continue
        lesson = lessons.get(parts[1])
        title = parts[2]
        if lesson:
            for index, block in enumerate(lesson.content.get("blocks", [])):
                if parts[2] in (block.get("id"), block.get("ref"), f"block-{index + 1}"):
                    title = block.get("title") or playground.get(block.get("ref"), parts[2])
                    break
        labels[key] = {"title": title, "where": lesson.title if lesson else parts[1], "lesson": parts[1]}
    return labels


# --- Joining -------------------------------------------------------------------------------

class JoinIn(Schema):
    code: str


@router.post("/join", response=MeResponse)
def join(request, data: JoinIn):
    team = find_team(data.code)
    Membership.objects.get_or_create(user=request.user, team=team, defaults={"role": STUDENT})
    return {"user": me_data(request.user)}


# --- Teams ------------------------------------------------------------------------------------

@router.get("")
def my_teams(request):
    """The teams you coach or mentor (staff: every team)."""
    user = request.user
    teams = Team.objects.all()
    if not user.is_staff:
        teams = teams.filter(id__in=Membership.objects.filter(user=user, role__in=LEADER_ROLES).values("team"))
    teams = teams.annotate(students=Count("memberships", filter=Q(memberships__role=STUDENT)))
    return {
        "teams": [
            {"id": team.id, "name": team.name, "season": team.season, "role": _role(user, team),
             "students": team.students}
            for team in teams.order_by("name")
        ],
        "can_create": user.kind == User.Kind.ADULT or user.is_staff,
    }


class TeamIn(Schema):
    name: str
    season: str = ""


@router.post("")
def create_team(request, data: TeamIn):
    user = request.user
    if not (user.kind == User.Kind.ADULT or user.is_staff):
        raise HttpError(403, "Only coaches can make teams.")
    name = data.name.strip()
    if not name:
        raise HttpError(400, "Give the team a name.")
    with transaction.atomic():
        team = Team.objects.create(name=name[:80], season=data.season.strip()[:40], created_by=user)
        Membership.objects.create(user=user, team=team, role=COACH)
    return team_data(team)


@router.get("/{team_id}")
def team_dashboard(request, team_id: int):
    """Everything on the team page: students with their progress, and the leaders."""
    team = _team(request, team_id)
    memberships = list(team.memberships.select_related("user").order_by("user__username"))
    students = [m for m in memberships if m.role == STUDENT]
    ids = [m.user_id for m in students]
    lessons = defaultdict(dict)
    for progress in LessonProgress.objects.filter(user__in=ids).select_related("lesson"):
        lessons[progress.user_id][progress.lesson.slug] = progress.as_dict()
    attempts = dict(
        Attempt.objects.filter(user__in=ids).values("user").annotate(n=Count("id")).values_list("user", "n")
    )
    solved = dict(
        Attempt.objects.filter(user__in=ids, passed=True, key__startswith="playground/")
        .values("user").annotate(n=Count("key", distinct=True)).values_list("user", "n")
    )
    active = _last_active([m.user for m in students])
    now = timezone.now()
    return {
        "team": team_data(team),
        "role": _role(request.user, team),
        "can_manage": coaches_team(request.user, team),
        "students": [
            {
                **_person(m, now),
                "lessons": lessons.get(m.user_id, {}),
                "attempts": attempts.get(m.user_id, 0),
                "solved": solved.get(m.user_id, 0),
                "last_active": _iso(active[m.user_id]),
            }
            for m in students
        ],
        "leaders": [_person(m, now) for m in memberships if m.role != STUDENT],
    }


class TeamChange(Schema):
    name: str | None = None
    season: str | None = None
    robot: dict | None = None


@router.patch("/{team_id}")
def change_team(request, team_id: int, data: TeamChange):
    team = _team(request, team_id, manage=True)
    if data.name is not None:
        if not data.name.strip():
            raise HttpError(400, "Give the team a name.")
        team.name = data.name.strip()[:80]
    if data.season is not None:
        team.season = data.season.strip()[:40]
    if data.robot is not None:
        try:
            team.robot = clean_robot(data.robot)
        except RobotError as error:
            raise HttpError(400, str(error))
    team.save()
    return team_data(team)


@router.post("/{team_id}/join-code")
def new_code(request, team_id: int):
    """A new join code, for when the old one got around. Current members stay."""
    team = _team(request, team_id, manage=True)
    team.join_code = new_join_code()
    team.save(update_fields=["join_code"])
    return team_data(team)


# --- Students and mentors ---------------------------------------------------------------------

class NewStudent(Schema):
    display_name: str = ""
    username: str = ""


class NewStudentsIn(Schema):
    students: list[NewStudent]


@router.post("/{team_id}/members")
def create_students(request, team_id: int, data: NewStudentsIn):
    """Make student accounts on the team. Each gets a username and a PIN, shown only now."""
    team = _team(request, team_id, manage=True)
    if not data.students:
        raise HttpError(400, "Add at least one student.")
    if len(data.students) > MAX_NEW_STUDENTS:
        raise HttpError(400, f"Add at most {MAX_NEW_STUDENTS} students at a time.")
    if team.memberships.count() + len(data.students) > MAX_TEAM_SIZE:
        raise HttpError(400, f"A team can have at most {MAX_TEAM_SIZE} members.")
    wanted, problems, taken = [], [], set()
    for number, student in enumerate(data.students, 1):
        username = student.username.strip()
        if username:
            problem = username_problem(username)
            if problem:
                problems.append(f"{username}: {problem}")
            elif username.lower() in taken or User.objects.filter(username__iexact=username).exists():
                problems.append(f"Someone already has the username {username}.")
        else:
            username = _free_username(taken)
        taken.add(username.lower())
        wanted.append((username, student.display_name.strip()[:40]))
    if problems:
        raise HttpError(400, " ".join(problems))
    created = []
    try:
        with transaction.atomic():
            for username, display_name in wanted:
                pin = random_pin()
                user = User.objects.create_user(
                    username=username, password=pin, kind=User.Kind.STUDENT,
                    display_name=display_name, avatar=random.choice(AVATARS),
                )
                Membership.objects.create(user=user, team=team, role=STUDENT)
                created.append({"username": user.username, "display_name": user.shown_name, "pin": pin})
    except IntegrityError:
        raise HttpError(409, "Someone just took one of those usernames. Please try again.")
    return {"created": created}


@router.get("/{team_id}/members/{username}")
def member_detail(request, team_id: int, username: str):
    """One student's lessons and challenges, with their latest code."""
    team = _team(request, team_id)
    membership = _member(team, username)
    can_manage = coaches_team(request.user, team)
    if membership.role == COACH or (membership.role == MENTOR and not can_manage):
        raise HttpError(403, "Only students' work can be looked at here.")
    user = membership.user

    lessons = {
        p.lesson.slug: {**p.as_dict(), "updated_at": _iso(p.updated_at)}
        for p in LessonProgress.objects.filter(user=user).select_related("lesson")
    }
    challenges = {}
    for attempt in Attempt.objects.filter(user=user).order_by("-created_at")[:MAX_ATTEMPTS_SHOWN]:
        entry = challenges.get(attempt.key)
        if entry is None:
            entry = challenges[attempt.key] = {
                "key": attempt.key, "attempts": 0, "passed": False, "last_at": _iso(attempt.created_at),
                "last_passed": attempt.passed, "last_code": attempt.code, "last_goals": attempt.goals,
                "passed_code": None, "draft": None,
            }
        entry["attempts"] += 1
        if attempt.passed and not entry["passed"]:
            entry["passed"] = True
            entry["passed_code"] = attempt.code
    for draft in CodeDraft.objects.filter(user=user):
        entry = challenges.setdefault(draft.key, {
            "key": draft.key, "attempts": 0, "passed": False, "last_at": _iso(draft.updated_at),
            "last_passed": None, "last_code": None, "last_goals": [], "passed_code": None,
        })
        entry["draft"] = draft.code
    labels = _challenge_labels(challenges)
    for key, entry in challenges.items():
        entry.update(labels[key])

    now = timezone.now()
    return {
        "team": {"id": team.id, "name": team.name},
        "student": {**_person(membership, now), "last_active": _iso(_last_active([user])[user.id])},
        "can_manage": can_manage,
        "lessons": lessons,
        "challenges": sorted(challenges.values(), key=lambda c: c["last_at"] or "", reverse=True),
    }


@router.post("/{team_id}/members/{username}/pin")
def new_pin(request, team_id: int, username: str):
    """A new PIN for a student who forgot theirs. It also unlocks the account."""
    team = _team(request, team_id, manage=True)
    user = _kid(_member(team, username)).user
    pin = random_pin()
    user.set_password(pin)
    user.failed_logins = 0
    user.locked_until = None
    user.save(update_fields=["password", "failed_logins", "locked_until"])
    return {"username": user.username, "display_name": user.shown_name, "pin": pin}


@router.post("/{team_id}/members/{username}/unlock")
def unlock(request, team_id: int, username: str):
    team = _team(request, team_id, manage=True)
    user = _kid(_member(team, username)).user
    user.failed_logins = 0
    user.locked_until = None
    user.save(update_fields=["failed_logins", "locked_until"])
    return {"ok": True}


class MemberChange(Schema):
    role: str


@router.patch("/{team_id}/members/{username}")
def change_member(request, team_id: int, username: str, data: MemberChange):
    """Make a student a mentor (an older student who helps), or back."""
    team = _team(request, team_id, manage=True)
    membership = _kid(_member(team, username))
    if data.role not in (STUDENT, MENTOR):
        raise HttpError(400, "A student can be a student or a mentor.")
    membership.role = data.role
    membership.save(update_fields=["role"])
    return {"ok": True}


@router.delete("/{team_id}/members/{username}")
def remove_member(request, team_id: int, username: str):
    """Take a student or mentor off the team. Their account and work are kept."""
    team = _team(request, team_id, manage=True)
    _kid(_member(team, username)).delete()
    return {"ok": True}

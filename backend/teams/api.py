"""Joining teams, and the read-only team view for coaches (the coach app's API)."""

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

from accounts.api import MeResponse, find_team, me_data

from .models import Membership, Team
from .permissions import leads_team

router = Router(tags=["teams"])


class JoinIn(Schema):
    code: str


@router.post("/join", response=MeResponse, auth=django_auth)
def join(request, data: JoinIn):
    team = find_team(data.code)
    Membership.objects.get_or_create(user=request.user, team=team, defaults={"role": Membership.Role.STUDENT})
    return {"user": me_data(request.user)}


@router.get("/{team_id}/students", auth=django_auth)
def team_students(request, team_id: int):
    """Each student on the team with their lesson progress. Coaches and mentors only."""
    from progress.models import Attempt, LessonProgress

    team = get_object_or_404(Team, id=team_id)
    if not leads_team(request.user, team):
        raise HttpError(403, "Only this team's coaches and mentors can see this.")
    students = []
    memberships = team.memberships.filter(role=Membership.Role.STUDENT).select_related("user")
    for membership in memberships.order_by("user__username"):
        user = membership.user
        progress = LessonProgress.objects.filter(user=user).select_related("lesson")
        last = Attempt.objects.filter(user=user).order_by("-created_at").first()
        students.append({
            "username": user.username,
            "display_name": user.shown_name,
            "avatar": user.avatar,
            "lessons": {p.lesson.slug: {"page": p.page, "done": p.done, "finished": p.finished} for p in progress},
            "attempts": Attempt.objects.filter(user=user).count(),
            "last_active": last.created_at.isoformat() if last else None,
        })
    return {"team": {"id": team.id, "name": team.name, "join_code": team.join_code}, "students": students}

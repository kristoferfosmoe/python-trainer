"""Lessons and everything needed to run them. Challenge solutions are only
sent to coaches, mentors and staff."""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja import Router

from teams.permissions import sees_solutions
from trainer_content import resolve_blocks

from .models import Course, Lesson, PlaygroundChallenge, Robot, World

router = Router(tags=["content"])


def visible_courses(user):
    courses = Course.objects.all()
    if user.is_authenticated and user.is_staff:
        return courses
    courses = courses.filter(published=True)
    if user.is_authenticated:
        return courses.filter(Q(owner_team__isnull=True) | Q(owner_team__memberships__user=user)).distinct()
    return courses.filter(owner_team__isnull=True)


def _strip(block, keep_solution):
    block = dict(block)
    if not keep_solution:
        block.pop("solution", None)
    return block


@router.get("/catalog")
def catalog(request):
    """Courses (lesson titles only), playground challenges, worlds and the robot."""
    user = request.user
    staff = user.is_authenticated and user.is_staff
    keep = sees_solutions(user)
    courses = []
    for course in visible_courses(user).prefetch_related("units__lessons"):
        units = []
        for unit in course.units.all():
            lessons = [
                {"id": lesson.slug, "title": lesson.title, "summary": lesson.summary}
                for lesson in unit.lessons.all()
                if lesson.published or staff
            ]
            if lessons:
                units.append({
                    "id": unit.slug, "title": unit.title, "icon": unit.icon, "summary": unit.summary,
                    "lessons": lessons,
                })
        courses.append({"id": course.slug, "title": course.title, "summary": course.summary, "units": units})
    playground = [
        _strip(challenge.spec, keep)
        for challenge in PlaygroundChallenge.objects.filter(**({} if staff else {"published": True}))
    ]
    robot = Robot.objects.order_by("id").first()
    return {
        "courses": courses,
        "playground": playground,
        "worlds": {world.slug: world.spec for world in World.objects.all()},
        "robot": robot.spec if robot else None,
        "solutions_included": keep,
    }


@router.get("/lessons/{slug}")
def lesson(request, slug: str):
    user = request.user
    filters = {"slug": slug, "unit__course__in": visible_courses(user)}
    if not (user.is_authenticated and user.is_staff):
        filters["published"] = True
    found = get_object_or_404(Lesson, **filters)
    playground = {c.slug: c.spec for c in PlaygroundChallenge.objects.all()}
    resolved = resolve_blocks(found.as_dict(), playground)
    keep = sees_solutions(user)
    resolved["blocks"] = [_strip(block, keep) for block in resolved["blocks"]]
    resolved["version"] = found.version
    return resolved

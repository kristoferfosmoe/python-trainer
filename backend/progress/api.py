"""A signed-in student's progress, saved code and challenge attempts."""

import re

from django.db import transaction
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth

from curriculum.models import Lesson

from .models import Attempt, CodeDraft, LessonProgress

router = Router(tags=["progress"], auth=django_auth)

MAX_CODE = 50_000
KEY_RE = re.compile(r"^(lesson/[\w-]{1,80}/[\w-]{1,80}|playground/[\w-]{1,80})$")
PLAYGROUND = "playground/"


def _check_key(key):
    if not KEY_RE.match(key):
        raise HttpError(400, "Unknown editor.")
    return key


def _check_code(code):
    if len(code) > MAX_CODE:
        raise HttpError(400, "That program is too long to save.")
    return code


def state_for(user):
    lessons = {
        p.lesson.slug: p.as_dict()
        for p in LessonProgress.objects.filter(user=user).select_related("lesson")
    }
    solved = sorted({
        key[len(PLAYGROUND):]
        for key in Attempt.objects.filter(user=user, passed=True, key__startswith=PLAYGROUND)
        .values_list("key", flat=True)
    })
    drafts = dict(CodeDraft.objects.filter(user=user).values_list("key", "code"))
    return {"lessons": lessons, "solved": solved, "drafts": drafts}


class ProgressIn(Schema):
    page: int = 0
    done: list[str] = []
    finished: bool = False


def _merge_progress(user, slug, data):
    lesson = Lesson.objects.filter(slug=slug).first()
    if lesson is None:
        return None
    progress, _ = LessonProgress.objects.select_for_update().get_or_create(user=user, lesson=lesson)
    progress.merge(data.page, data.done, data.finished)
    progress.save()
    return progress


@router.get("/me/state")
def my_state(request):
    return state_for(request.user)


@router.put("/progress/{slug}")
def save_progress(request, slug: str, data: ProgressIn):
    with transaction.atomic():
        progress = _merge_progress(request.user, slug, data)
    if progress is None:
        raise HttpError(404, "No such lesson.")
    return progress.as_dict()


class DraftIn(Schema):
    key: str
    code: str


@router.put("/drafts")
def save_draft(request, data: DraftIn):
    CodeDraft.objects.update_or_create(
        user=request.user, key=_check_key(data.key), defaults={"code": _check_code(data.code)},
    )
    return {"ok": True}


class AttemptIn(Schema):
    key: str
    code: str
    passed: bool
    goals: list[dict] = []
    sim_version: str = ""
    lesson_id: str | None = None
    block_id: str | None = None


@router.post("/attempts")
def record_attempt(request, data: AttemptIn):
    key = _check_key(data.key)
    lesson = Lesson.objects.filter(slug=data.lesson_id).first() if data.lesson_id else None
    with transaction.atomic():
        Attempt.objects.create(
            user=request.user, key=key, lesson=lesson, block_id=(data.block_id or "")[:100],
            lesson_version=lesson.version if lesson else None, code=_check_code(data.code),
            passed=data.passed, goals=data.goals[:20], sim_version=data.sim_version[:20],
        )
        if data.passed and lesson and data.block_id:
            _merge_progress(request.user, lesson.slug, ProgressIn(done=[data.block_id]))
    return {"ok": True}


class ImportIn(Schema):
    lessons: dict[str, ProgressIn] = {}
    solved: list[str] = []
    drafts: dict[str, str] = {}


@router.post("/me/import")
def import_guest_progress(request, data: ImportIn):
    """Keep what a student did as a guest when they sign up or sign in."""
    user = request.user
    with transaction.atomic():
        for slug, progress in list(data.lessons.items())[:500]:
            _merge_progress(user, slug, progress)
        for key, code in list(data.drafts.items())[:500]:
            if KEY_RE.match(key) and len(code) <= MAX_CODE:
                CodeDraft.objects.get_or_create(user=user, key=key, defaults={"code": code})
        existing = set(Attempt.objects.filter(user=user, passed=True, key__startswith=PLAYGROUND).values_list("key", flat=True))
        for challenge in data.solved[:100]:
            key = PLAYGROUND + challenge
            if KEY_RE.match(key) and key not in existing:
                # Solved as a guest: remember it (the code wasn't kept).
                Attempt.objects.create(user=user, key=key, code="", passed=True, sim_version="guest")
    return state_for(user)

"""Mission Mode: the ladder, one challenge at a time, and stars.

Challenges unlock in order: a challenge opens when the one before it (in
its game) has at least one star. Signed-in students can't fetch a locked
challenge, or save stars for one. Guests' progress lives in their browser,
so their locks are worked out there. Solutions are only sent to coaches,
mentors and staff (teams.permissions.sees_solutions), as for lessons.
"""

from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.security import django_auth
from pydantic import Field

from teams.permissions import sees_solutions

from .models import MissionGame
from .progress import MAX_SCORE, merge_progress, progress_for, unlocked_slugs, visible_challenges

router = Router(tags=["missions"])

SOLUTION_KEYS = ("solution", "solution_attachments")
GAME_SUMMARY_KEYS = ("id", "title", "summary", "tiers")


def _strip(spec, keep_solution):
    return {k: v for k, v in spec.items() if keep_solution or k not in SOLUTION_KEYS}


def _game_for_run(game):
    """Everything the simulator needs to run the game's challenges."""
    return {k: v for k, v in game.spec.items() if k != "challenges"}


@router.get("/missions")
def ladder(request):
    """Every game, its tiers and its challenges (titles only), with your stars and what's unlocked."""
    user = request.user
    challenges = list(visible_challenges(user))
    signed_in = user.is_authenticated
    unlocked = unlocked_slugs(user, challenges) if signed_in else None
    progress = progress_for(user)
    games = []
    for game in MissionGame.objects.all():
        if not game.published and not (signed_in and user.is_staff):
            continue
        ladder = [c for c in challenges if c.game_id == game.id]
        if not ladder:
            continue
        games.append({
            **{k: game.spec.get(k) for k in GAME_SUMMARY_KEYS},
            "id": game.slug,
            "challenges": [{
                "id": c.slug,
                "title": c.title,
                "tier": c.tier,
                "summary": c.spec.get("summary", ""),
                "unlocked": None if unlocked is None else c.slug in unlocked,
                "stars": progress.get(c.slug, {}).get("stars", 0),
                "best_score": progress.get(c.slug, {}).get("best_score", 0),
            } for c in ladder],
        })
    return {"games": games, "signed_in": signed_in}


def _challenge_or_404(request, slug):
    user = request.user
    challenge = get_object_or_404(visible_challenges(user), slug=slug)
    if user.is_authenticated and challenge.slug not in unlocked_slugs(user):
        raise HttpError(403, "Finish the challenge before this one to unlock it.")
    return challenge


@router.get("/missions/challenges/{slug}")
def challenge(request, slug: str):
    """One challenge, with its game (field, models, attachments, robot) for running it."""
    found = _challenge_or_404(request, slug)
    keep = sees_solutions(request.user)
    return {"game": _game_for_run(found.game), "challenge": _strip(found.spec, keep)}


class ResultIn(Schema):
    stars: int = Field(0, ge=0, le=3)
    score: int = Field(0, ge=-MAX_SCORE, le=MAX_SCORE)


@router.put("/missions/challenges/{slug}/progress", auth=django_auth)
def save_result(request, slug: str, data: ResultIn):
    """Keep the best stars and score (an old or worse result never lowers them)."""
    found = _challenge_or_404(request, slug)
    return merge_progress(request.user, found, data.stars, data.score).as_dict()

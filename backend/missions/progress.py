"""Stars and unlocking. Shared by the missions API and /api/me (progress app)."""

from django.db import transaction

from .models import MissionChallenge, MissionProgress

MAX_SCORE = 100_000


def visible_challenges(user):
    challenges = MissionChallenge.objects.select_related("game")
    if user.is_authenticated and user.is_staff:
        return challenges
    return challenges.filter(published=True, game__published=True)


def progress_for(user):
    """{challenge slug: {stars, best_score}} for a signed-in student."""
    if not user.is_authenticated:
        return {}
    return {
        p.challenge.slug: p.as_dict()
        for p in MissionProgress.objects.filter(user=user).select_related("challenge")
    }


def unlocked_slugs(user, challenges=None):
    """Challenges open to this user: each one unlocks when the one before it (in its game) has a star.
    Staff can open everything. None means "anyone may open it" (guests unlock in the browser)."""
    challenges = list(challenges if challenges is not None else visible_challenges(user))
    if user.is_authenticated and user.is_staff:
        return {c.slug for c in challenges}
    stars = {slug: p["stars"] for slug, p in progress_for(user).items()}
    unlocked = set()
    by_game = {}
    for challenge in sorted(challenges, key=lambda c: (c.game.order, c.game.slug, c.order, c.slug)):
        by_game.setdefault(challenge.game_id, []).append(challenge)
    for ladder in by_game.values():
        for index, challenge in enumerate(ladder):
            if index == 0 or stars.get(ladder[index - 1].slug, 0) >= 1:
                unlocked.add(challenge.slug)
            else:
                break
    return unlocked


def merge_progress(user, challenge, stars, score):
    with transaction.atomic():
        progress, _ = MissionProgress.objects.select_for_update().get_or_create(user=user, challenge=challenge)
        progress.merge(stars, max(-MAX_SCORE, min(MAX_SCORE, int(score))))
        progress.save()
    return progress


def import_guest_progress(user, missions):
    """Stars earned as a guest, kept when the student signs up or in (in ladder order, so locks stay honest)."""
    by_slug = {c.slug: c for c in visible_challenges(user)}
    wanted = {slug: data for slug, data in list(missions.items())[:500] if slug in by_slug}
    ordered = sorted(wanted, key=lambda s: (by_slug[s].game.order, by_slug[s].order))
    for slug in ordered:
        if slug in unlocked_slugs(user):
            merge_progress(user, by_slug[slug], wanted[slug].stars, wanted[slug].best_score)

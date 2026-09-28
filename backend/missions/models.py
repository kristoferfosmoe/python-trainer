"""Mission Mode: robot games, their ladders of challenges, and each
student's stars (see docs/MISSION_MODE.md). Like lessons, games come from
the YAML files in content/missions/ (`manage.py import_content`)."""

from django.conf import settings
from django.db import models


class MissionGame(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    summary = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=True)
    spec = models.JSONField(help_text="The game: field, models, missions, tiers, attachments, robot...")
    source = models.CharField(max_length=300, blank=True, help_text="The folder this game was imported from.")

    class Meta:
        ordering = ["order", "slug"]

    def __str__(self):
        return self.title


class MissionChallenge(models.Model):
    game = models.ForeignKey(MissionGame, on_delete=models.CASCADE, related_name="challenges")
    slug = models.SlugField(unique=True, help_text="Used in the challenge's web address.")
    title = models.CharField(max_length=120)
    tier = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=0, help_text="Challenges unlock one after another, in this order.")
    published = models.BooleanField(default=True)
    spec = models.JSONField(help_text="The whole challenge: runs, models, goals, stars, starter, solution...")
    source = models.CharField(max_length=300, blank=True, help_text="The file this challenge was imported from.")

    class Meta:
        ordering = ["game", "order", "slug"]

    def __str__(self):
        return self.title


class MissionProgress(models.Model):
    """A student's best result on a challenge. Only ever moves up."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mission_progress")
    challenge = models.ForeignKey(MissionChallenge, on_delete=models.CASCADE, related_name="progress")
    stars = models.PositiveSmallIntegerField(default=0)
    best_score = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "challenge"], name="one_progress_per_mission_challenge")]
        verbose_name_plural = "mission progress"

    @property
    def completed(self):
        return self.stars >= 1

    def merge(self, stars=0, score=0):
        self.stars = max(self.stars, min(3, max(0, int(stars))))
        self.best_score = max(self.best_score, int(score))

    def as_dict(self):
        return {"stars": self.stars, "best_score": self.best_score}

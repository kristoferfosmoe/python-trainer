from django.conf import settings
from django.db import models

from curriculum.models import Lesson


class LessonProgress(models.Model):
    """How far a student got in a lesson. Only ever moves forward, so saves
    from two laptops (or a slow network) can't undo progress."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="progress")
    page = models.PositiveIntegerField(default=0, help_text="Furthest page reached (from 0)")
    done = models.JSONField(default=list, help_text="Ids of finished quizzes and challenges")
    finished = models.BooleanField(default=False, help_text="Reached the end of the lesson")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="one_progress_per_lesson")]
        verbose_name_plural = "lesson progress"

    def merge(self, page=0, done=(), finished=False):
        self.page = max(self.page, int(page))
        self.done = sorted(set(self.done) | {str(d)[:100] for d in done})
        self.finished = self.finished or bool(finished)

    def as_dict(self):
        return {"page": self.page, "done": self.done, "finished": self.finished}


class CodeDraft(models.Model):
    """The code a student last had in an editor, so they can pick up where they left off."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="drafts")
    key = models.CharField(max_length=200, help_text="lesson/<lesson>/<block> or playground/<challenge>")
    code = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="one_draft_per_editor")]


class Attempt(models.Model):
    """Every run of a challenge with goals. The coach app will show these."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attempts")
    key = models.CharField(max_length=200)
    lesson = models.ForeignKey(Lesson, null=True, blank=True, on_delete=models.SET_NULL, related_name="attempts")
    block_id = models.CharField(max_length=100, blank=True)
    lesson_version = models.PositiveIntegerField(null=True, blank=True)
    code = models.TextField()
    passed = models.BooleanField(default=False)
    goals = models.JSONField(default=list)
    sim_version = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "key"]), models.Index(fields=["user", "-created_at"])]

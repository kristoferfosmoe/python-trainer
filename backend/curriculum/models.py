"""Lessons and the things they use. The database is the source of truth at
runtime; `manage.py import_content` loads the YAML files from content/."""

from django.db import models


class World(models.Model):
    """A mat the robot drives on (see docs/ARCHITECTURE.md §4.4)."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    spec = models.JSONField()

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.name


class Robot(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    spec = models.JSONField()

    def __str__(self):
        return self.name


class PlaygroundChallenge(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=True)
    spec = models.JSONField(help_text="The whole challenge: world, goals, starter, solution...")

    class Meta:
        ordering = ["order", "slug"]

    def __str__(self):
        return self.title


class Course(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    summary = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=True)
    owner_team = models.ForeignKey(
        "teams.Team", null=True, blank=True, on_delete=models.CASCADE,
        help_text="Leave empty for everyone. Set a team to make the course visible to that team only.",
    )

    class Meta:
        ordering = ["order", "slug"]

    def __str__(self):
        return self.title


class Unit(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="units")
    slug = models.SlugField()
    title = models.CharField(max_length=120)
    icon = models.CharField(max_length=8, blank=True)
    summary = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["course__order", "order", "slug"]
        constraints = [models.UniqueConstraint(fields=["course", "slug"], name="unique_unit_per_course")]

    def __str__(self):
        return f"{self.icon} {self.title}".strip()


class Lesson(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="lessons")
    slug = models.SlugField(unique=True, help_text="Used in the lesson's web address.")
    title = models.CharField(max_length=120)
    summary = models.CharField(max_length=240)
    order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=True)
    content = models.JSONField(default=dict, help_text='{"concepts": [...], "blocks": [...]}')
    version = models.PositiveIntegerField(default=1, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["unit__course__order", "unit__order", "order", "slug"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Attempts remember the version they were made against.
        if self.pk:
            old = Lesson.objects.filter(pk=self.pk).values_list("content", flat=True).first()
            if old is not None and old != self.content:
                self.version += 1
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"/#/lesson/{self.slug}"

    def as_dict(self):
        """The lesson as trainer_content expects it (blocks as written, refs not expanded)."""
        return {
            "id": self.slug,
            "title": self.title,
            "summary": self.summary,
            "concepts": self.content.get("concepts", []),
            "blocks": self.content.get("blocks", []),
        }

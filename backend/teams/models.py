import secrets

from django.conf import settings
from django.db import models

# No 0/O or 1/I, so codes are easy to read aloud and type.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def new_join_code():
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if not Team.objects.filter(join_code=code).exists():
            return code


class Team(models.Model):
    name = models.CharField(max_length=80)
    season = models.CharField(max_length=40, blank=True, help_text="For example 2026-27")
    join_code = models.CharField(max_length=CODE_LENGTH, unique=True, blank=True,
                                 help_text="Students type this to join. Made automatically.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = new_join_code()
        self.join_code = self.join_code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        MENTOR = "mentor", "Mentor (older student)"
        COACH = "coach", "Coach"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "team"], name="one_membership_per_team")]

    def __str__(self):
        return f"{self.user} in {self.team} ({self.role})"

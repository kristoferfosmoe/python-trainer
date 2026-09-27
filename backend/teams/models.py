import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction

from .robot import RobotError, clean_robot

# No 0/O or 1/I, so codes are easy to read aloud and type.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


class TeamFull(Exception):
    """The team has settings.TEAM_MAX_MEMBERS members already."""


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
    robot = models.JSONField(
        default=dict, blank=True,
        help_text="The team's real robot (ports and wheel sizes), used when students copy code to "
                  "Pybricks. Empty means it's built like the Trainer Bot. Coaches set it on the team page.",
    )

    def clean(self):
        try:
            self.robot = clean_robot(self.robot)
        except RobotError as error:
            raise ValidationError({"robot": str(error)})

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = new_join_code()
        self.join_code = self.join_code.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def room(self):
        """How many more members the team can have (everyone counts: students, mentors, coaches)."""
        return max(0, settings.TEAM_MAX_MEMBERS - self.memberships.count())

    def lock(self):
        """Inside a transaction: make changes to this team's members take turns,
        so two people can't both take its last place."""
        Team.objects.select_for_update().filter(pk=self.pk).first()

    def add_member(self, user, role):
        """Put `user` on the team (unless they're on it already) and return
        their membership. Raises TeamFull."""
        with transaction.atomic():
            self.lock()
            membership = self.memberships.filter(user=user).first()
            if membership:
                return membership
            if self.room() == 0:
                raise TeamFull()
            return Membership.objects.create(user=user, team=self, role=role)


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

    def clean(self):
        # For the admin; the app uses Team.add_member.
        if self._state.adding and self.team_id and self.team.room() == 0:
            raise ValidationError(
                f"{self.team} has {settings.TEAM_MAX_MEMBERS} members, the most a team can have. "
                "Remove a member before adding another."
            )

    def __str__(self):
        return f"{self.user} in {self.team} ({self.role})"

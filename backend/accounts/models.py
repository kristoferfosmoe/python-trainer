from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.functions import Lower

AVATARS = ["🤖", "🦊", "🐼", "🐙", "🦄", "🐢", "🦖", "🐝", "🦉", "🐬", "🚀", "⚡"]


class CaseInsensitiveUserManager(UserManager):
    def get_by_natural_key(self, username):
        return self.get(username__iexact=username)


class User(AbstractUser):
    """Students sign in with a username and a PIN (stored like a password).
    Adults (coaches, teachers, admins) use a real password.

    Students have no email, real name or birth date on purpose.
    """

    class Kind(models.TextChoices):
        STUDENT = "student", "Student"
        ADULT = "adult", "Adult (coach or teacher)"

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.STUDENT)
    display_name = models.CharField(max_length=40, blank=True)
    avatar = models.CharField(max_length=8, default=AVATARS[0])
    failed_logins = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    objects = CaseInsensitiveUserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("username"), name="unique_username_ignoring_case")]

    @property
    def shown_name(self):
        return self.display_name or self.username


class LoginFailure(models.Model):
    """Failed sign-ins per IP address (IPv6: per /64 network), to slow down
    PIN guessing. A sign-in is recorded here while it's being checked, and
    the record is removed if the PIN was right. A right PIN also removes the
    earlier misses for that username from that address: those were typos,
    not guesses (see accounts.auth)."""

    ip = models.GenericIPAddressField()
    username = models.CharField(max_length=150, blank=True, default="", help_text="As typed, in lowercase")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["ip", "created_at"])]


class RateLimitHit(models.Model):
    """One use of something that's limited: a new account, a wrong team code
    (see accounts.limits)."""

    scope = models.CharField(max_length=20)
    key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["scope", "key", "created_at"])]

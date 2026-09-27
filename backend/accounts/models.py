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
    """Failed sign-ins per IP address, to slow down PIN guessing."""

    ip = models.GenericIPAddressField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["ip", "created_at"])]

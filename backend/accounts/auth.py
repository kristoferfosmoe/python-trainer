"""Signing in, with protection against guessing PINs.

- An account is locked for a few minutes after too many wrong PINs.
- An IP address is blocked for a while after too many failures overall.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.utils import timezone

from .models import LoginFailure, User


class SignInError(Exception):
    def __init__(self, message, status=401):
        super().__init__(message)
        self.status = status


def client_ip(request):
    if settings.TRUST_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


def _ip_blocked(ip):
    since = timezone.now() - timedelta(minutes=settings.LOGIN_IP_WINDOW_MINUTES)
    return LoginFailure.objects.filter(ip=ip, created_at__gte=since).count() >= settings.LOGIN_IP_MAX_FAILURES


def sign_in(request, username, secret):
    ip = client_ip(request)
    if _ip_blocked(ip):
        raise SignInError(
            f"Too many wrong tries from this computer. Please wait {settings.LOGIN_IP_WINDOW_MINUTES} minutes.",
            status=429,
        )
    now = timezone.now()
    user = User.objects.filter(username__iexact=(username or "").strip()).first()
    if user and user.locked_until and user.locked_until > now:
        minutes = max(1, round((user.locked_until - now).total_seconds() / 60))
        raise SignInError(
            f"This account is locked for {minutes} more minute{'s' if minutes != 1 else ''} after too many wrong PINs.",
            status=429,
        )
    if user is None or not user.is_active or not user.check_password(secret or ""):
        forget_old_failures()
        LoginFailure.objects.create(ip=ip)
        if user is not None:
            user.failed_logins += 1
            if user.failed_logins >= settings.LOGIN_ACCOUNT_MAX_FAILURES:
                user.failed_logins = 0
                user.locked_until = now + timedelta(minutes=settings.LOGIN_ACCOUNT_LOCK_MINUTES)
            user.save(update_fields=["failed_logins", "locked_until"])
        raise SignInError("That username and PIN don't match. Check them and try again.")
    if user.failed_logins or user.locked_until:
        user.failed_logins = 0
        user.locked_until = None
        user.save(update_fields=["failed_logins", "locked_until"])
    login(request, user)
    return user


def forget_old_failures():
    """Housekeeping: drop failure records older than a day."""
    LoginFailure.objects.filter(created_at__lt=timezone.now() - timedelta(days=1)).delete()

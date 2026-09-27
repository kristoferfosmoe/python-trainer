"""Limits on things worth guessing or spamming: new accounts and team codes
from one address. They're counted in the database, so every server process
sees the same numbers. (Sign-ins have their own rules in accounts.auth;
challenge attempts are counted per student in progress.api.)"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from ninja.errors import HttpError

from .auth import client_ip, limit_key
from .models import RateLimitHit

SIGNUP = "signup"
WRONG_CODE = "wrong-code"


def _rules(scope):
    return {
        SIGNUP: (settings.SIGNUP_MAX_PER_HOUR, 60,
                 "Lots of accounts were just made from this computer. Please try again in an hour, "
                 "or ask your coach to make your account."),
        WRONG_CODE: (settings.JOIN_CODE_MAX_FAILURES, 15,
                     "Too many wrong team codes from this computer. Check the code with your coach, "
                     "then try again in 15 minutes."),
    }[scope]


def check(request, scope):
    """Stop with 429 if this computer has used up `scope` for now."""
    limit, minutes, message = _rules(scope)
    since = timezone.now() - timedelta(minutes=minutes)
    if RateLimitHit.objects.filter(scope=scope, key=limit_key(client_ip(request)), created_at__gte=since).count() >= limit:
        raise HttpError(429, message)


def count(request, scope):
    """Count one use of `scope` by this computer."""
    RateLimitHit.objects.filter(created_at__lt=timezone.now() - timedelta(days=1)).delete()
    RateLimitHit.objects.create(scope=scope, key=limit_key(client_ip(request)))

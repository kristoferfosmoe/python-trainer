"""Signing in, with protection against guessing PINs and passwords.

- An account is locked for a few minutes after too many wrong PINs.
- An IP address is blocked for a while after too many failures overall.
  A school shares one address, so misses followed by the right PIN for the
  same username are forgiven: those were typos, not guesses.
- IPv6 addresses count per /64 network, since one home or phone usually
  gets a whole /64.
- Usernames that don't exist take as long to check as ones that do.

The app's sign-in and the admin's (accounts.forms) both go through
check_credentials(), so neither is an easier way in.
"""

import ipaddress
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import login
from django.db import transaction
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


def limit_key(ip):
    """The address that limits count against: an IPv6 address's /64 network."""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return "0.0.0.0"
    if address.version == 6:
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.ip_network(f"{address}/64", strict=False).network_address)
    return str(address)


def _recent_failures(ip):
    since = timezone.now() - timedelta(minutes=settings.LOGIN_IP_WINDOW_MINUTES)
    return LoginFailure.objects.filter(ip=ip, created_at__gte=since).count()


def sign_in(request, username, secret):
    user = check_credentials(request, username, secret)
    login(request, user)
    return user


def check_credentials(request, username, secret):
    """The user with this username and PIN (or password). Raises SignInError."""
    ip = limit_key(client_ip(request))
    username = (username or "").strip()
    secret = secret or ""
    # Counted as a failure until the PIN turns out to be right, so sign-ins
    # that arrive at the same moment can't all slip in under the limit.
    attempt = LoginFailure.objects.create(ip=ip, username=username.lower()[:150])
    if _recent_failures(ip) > settings.LOGIN_IP_MAX_FAILURES:
        attempt.delete()
        raise SignInError(
            f"Too many wrong tries from this computer. Please wait {settings.LOGIN_IP_WINDOW_MINUTES} minutes.",
            status=429,
        )
    with transaction.atomic():
        # Locking the account's row makes sign-ins to one account take turns,
        # so a burst of guesses can't all get past the lock.
        user = User.objects.select_for_update().filter(username__iexact=username).first()
        error = _check(user, secret)
    if error:
        if error.status == 429:
            attempt.delete()  # the account's own lock; not a guess
        else:
            forget_old_failures()
        raise error
    LoginFailure.objects.filter(ip=ip, username=attempt.username).delete()
    return user


def _check(user, secret):
    """None if `secret` is right for `user`, else the SignInError to raise.
    Updates the account's failure count and lock."""
    now = timezone.now()
    if user and user.locked_until and user.locked_until > now:
        minutes = max(1, round((user.locked_until - now).total_seconds() / 60))
        tries = "PINs" if user.kind == User.Kind.STUDENT else "passwords"
        return SignInError(
            f"This account is locked for {minutes} more minute{'s' if minutes != 1 else ''} after too many wrong {tries}.",
            status=429,
        )
    if user is None:
        User().set_password(secret)  # as slow as checking a real PIN
    if user is None or not user.is_active or not user.check_password(secret):
        if user is not None:
            user.failed_logins += 1
            if user.failed_logins >= settings.LOGIN_ACCOUNT_MAX_FAILURES:
                user.failed_logins = 0
                user.locked_until = now + timedelta(minutes=settings.LOGIN_ACCOUNT_LOCK_MINUTES)
            user.save(update_fields=["failed_logins", "locked_until"])
        return SignInError("That username and PIN don't match. Check them and try again.")
    if user.failed_logins or user.locked_until:
        user.failed_logins = 0
        user.locked_until = None
        user.save(update_fields=["failed_logins", "locked_until"])
    return None


def forget_old_failures():
    """Housekeeping: drop failure records older than a day."""
    LoginFailure.objects.filter(created_at__lt=timezone.now() - timedelta(days=1)).delete()

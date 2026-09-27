"""How long people stay signed in, and typing your password again.

Students stay signed in for a month on their own laptop (SESSION_COOKIE_AGE).
Coaches and admins can do much more from a signed-in browser: make new PINs
and read every kid's work. School computers are shared, so their sessions
end after ADULT_IDLE_MINUTES without use, and ADULT_SESSION_HOURS after
signing in. Before making a new PIN (which lets whoever has it sign in as
that student), a coach types their password again.
"""

import time

from django.conf import settings
from django.contrib.auth import logout

STARTED = "adult_session_started"
SEEN = "adult_session_seen"
CONFIRMED = "password_confirmed_at"


def is_adult(user):
    return user.is_authenticated and (user.kind == user.Kind.ADULT or user.is_staff)


def start_adult_session(session):
    session[STARTED] = session[SEEN] = time.time()
    session.set_expiry(settings.ADULT_SESSION_HOURS * 3600)


def on_sign_in(sender, request, user, **kwargs):
    """At sign-in (the app's or the admin's), so even that response's cookie is short-lived."""
    if request is not None and is_adult(user):
        start_adult_session(request.session)


class AdultSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_adult(request.user):
            session = request.session
            now = time.time()
            started, seen = session.get(STARTED), session.get(SEEN)
            if started is None or seen is None:
                start_adult_session(session)  # signed in before this rule existed
            elif now - started > settings.ADULT_SESSION_HOURS * 3600 or now - seen > settings.ADULT_IDLE_MINUTES * 60:
                logout(request)
            elif now - seen > 60:  # saving the session on every request would be wasteful
                session[SEEN] = now
        return self.get_response(request)


class PasswordNeeded(Exception):
    """The API answers 403 with code "password_needed" (see trainer.api)."""


def password_confirmed(request):
    """Remember that the user just typed their password again."""
    request.session[CONFIRMED] = time.time()


def require_recent_password(request):
    confirmed = request.session.get(CONFIRMED, 0)
    if time.time() - confirmed > settings.PASSWORD_CONFIRM_MINUTES * 60:
        raise PasswordNeeded()

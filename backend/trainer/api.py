from django.middleware.csrf import get_token
from ninja import NinjaAPI

from accounts.api import router as auth_router
from accounts.sessions import PasswordNeeded
from curriculum.api import router as content_router
from missions.api import router as missions_router
from progress.api import router as progress_router
from teams.api import router as teams_router

api = NinjaAPI(title="Python Trainer API", version="1", urls_namespace="api")
api.add_router("/auth", auth_router)
api.add_router("/teams", teams_router)
api.add_router("", content_router)
api.add_router("", progress_router)
api.add_router("", missions_router)


@api.exception_handler(PasswordNeeded)
def password_needed(request, exc):
    """The web app asks for the password, then tries again."""
    return api.create_response(
        request, {"detail": "Please type your password again first.", "code": "password_needed"}, status=403,
    )


@api.get("/csrf", tags=["auth"])
def csrf(request):
    """Sets the CSRF cookie the web app sends back with every change."""
    get_token(request)
    return {"ok": True}


@api.get("/health", tags=["ops"])
def health(request):
    """For uptime checks: the web server is up and the database answers.
    `version` is the git commit, so a deploy can check the new code is live."""
    from django.conf import settings
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return {"ok": True, "version": settings.APP_VERSION}

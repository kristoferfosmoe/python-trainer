from django.middleware.csrf import get_token
from ninja import NinjaAPI

from accounts.api import router as auth_router
from curriculum.api import router as content_router
from progress.api import router as progress_router
from teams.api import router as teams_router

api = NinjaAPI(title="Python Trainer API", version="1", urls_namespace="api")
api.add_router("/auth", auth_router)
api.add_router("/teams", teams_router)
api.add_router("", content_router)
api.add_router("", progress_router)


@api.get("/csrf", tags=["auth"])
def csrf(request):
    """Sets the CSRF cookie the web app sends back with every change."""
    get_token(request)
    return {"ok": True}

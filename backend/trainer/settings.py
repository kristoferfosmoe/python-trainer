"""Django settings. Everything that differs between computers comes from
environment variables (see deploy/.env.example)."""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent

# The simulator package (lesson checks) and the content folder (lesson import).
SIM_SRC = Path(os.environ.get("TRAINER_SIM_SRC", REPO_DIR / "sim" / "src"))
CONTENT_DIR = Path(os.environ.get("TRAINER_CONTENT_DIR", REPO_DIR / "content"))
if str(SIM_SRC) not in sys.path:
    sys.path.insert(0, str(SIM_SRC))


def env_bool(name, default=False):
    value = os.environ.get(name)
    return default if value is None else value.lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


PRODUCTION = os.environ.get("DJANGO_ENV") == "production"
DEBUG = env_bool("DJANGO_DEBUG", not PRODUCTION)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if PRODUCTION:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in production.")
    SECRET_KEY = "development-only-not-secret"

# Health checks inside the server call http://127.0.0.1:8000, so loopback is
# always allowed. Caddy only passes on requests for the site's own domain.
ALLOWED_HOSTS = [*env_list("DJANGO_ALLOWED_HOSTS", "localhost"), "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "teams",
    "curriculum",
    "progress",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.sessions.AdultSessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "trainer.urls"
WSGI_APPLICATION = "trainer.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
            "NAME": os.environ.get("POSTGRES_DB", "trainer"),
            "USER": os.environ.get("POSTGRES_USER", "trainer"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DJANGO_SQLITE_PATH", BASE_DIR / "db.sqlite3"),
            # Sign-ins read and then update an account in one transaction
            # (accounts.auth). IMMEDIATE makes SQLite wait its turn when another
            # request is writing, instead of failing with "database is locked".
            "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
        }
    }

AUTH_USER_MODEL = "accounts.User"
# Adults (coaches, teachers) use real passwords. Students use PINs, which
# accounts.pins checks instead.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if PRODUCTION
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Kids stay signed in for a month on their own laptop. Coaches and admins,
# who can do much more, are signed out sooner (accounts.sessions), and type
# their password again before making a student a new PIN.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
ADULT_SESSION_HOURS = 12
ADULT_IDLE_MINUTES = 120
PASSWORD_CONFIRM_MINUTES = 15
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Cookies only over HTTPS in production. (DJANGO_SECURE_COOKIES=false is only
# for testing the production setup on plain http://localhost.)
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", PRODUCTION)

# Behind Caddy, the client's address is the last X-Forwarded-For entry.
TRUST_FORWARDED_FOR = env_bool("DJANGO_TRUST_FORWARDED_FOR", PRODUCTION)

# Sign-in protection (accounts.auth).
LOGIN_ACCOUNT_MAX_FAILURES = 5
LOGIN_ACCOUNT_LOCK_MINUTES = 5
LOGIN_IP_MAX_FAILURES = 30
LOGIN_IP_WINDOW_MINUTES = 15
# Per computer (accounts.limits) and per student (progress.api).
SIGNUP_MAX_PER_HOUR = 50
JOIN_CODE_MAX_FAILURES = 40  # per 15 minutes
ATTEMPTS_MAX_PER_HOUR = 600
# Members of every role count: students, mentors and coaches.
TEAM_MAX_MEMBERS = 100

# Lessons saved in the admin are checked in a separate process: in production,
# in the checker container, reached through this socket (see curriculum.library).
LESSON_CHECK_TIMEOUT = int(os.environ.get("LESSON_CHECK_TIMEOUT", "90"))
LESSON_CHECKER_SOCKET = os.environ.get("LESSON_CHECKER_SOCKET", "")

# The git commit this server runs, baked into the image by CI (see deploy/Dockerfile).
APP_VERSION = os.environ.get("APP_VERSION", "dev")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
    # runserver's request log (quieted in browser tests)
    "loggers": {"django.server": {"level": os.environ.get("DJANGO_SERVER_LOG_LEVEL", "INFO")}},
}

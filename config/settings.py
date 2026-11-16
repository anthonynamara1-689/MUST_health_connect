"""Settings for MUST HealthConnect."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# Connectivity feature 1: every secret and password comes from .env, never from code.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]
# Hosting on Render: Render sets RENDER_EXTERNAL_HOSTNAME (e.g. must-healthconnect.onrender.com).
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("127.0.0.1", "localhost")]
# Render ends HTTPS at its proxy and tells Django through this header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "portal",
    "tracker",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Connectivity feature 8: friendly page when PostgreSQL cannot be reached.
    "tracker.middleware.DatabaseDownMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.ui",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# DATABASE: PostgreSQL through psycopg 3.
# Connectivity feature 2: two connections with different privileges.
#   "default" -> hc_app    (owns the tables; reads and writes)
#   "reports" -> hc_report (may only SELECT from the reporting views)
# Connectivity feature 3: connection pooling (psycopg_pool), switchable with DB_POOL.


RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == "test"


def pool_options():
    """Connection pool settings, or False to open a fresh connection per request.

    The pool is switched off while tests run: pooled connections stay open,
    which stops Django from dropping the test database at the end.
    """
    if RUNNING_TESTS or not env_bool("DB_POOL", True):
        return False
    return {"min_size": 2, "max_size": 10, "timeout": 3}


DB_COMMON = {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("DB_NAME", "healthconnect"),
    "HOST": os.getenv("DB_HOST", "localhost"),
    "PORT": os.getenv("DB_PORT", "5432"),
    # Test each connection before handing it out, so the site recovers on its
    # own after PostgreSQL restarts (with the pool on, this is the pool's check).
    "CONN_HEALTH_CHECKS": True,
}

DATABASES = {
    "default": {
        **DB_COMMON,
        "USER": os.environ["DB_APP_USER"],
        "PASSWORD": os.environ["DB_APP_PASSWORD"],
        "OPTIONS": {"pool": pool_options()},
    },
    "reports": {
        **DB_COMMON,
        "USER": os.environ["DB_REPORT_USER"],
        "PASSWORD": os.environ["DB_REPORT_PASSWORD"],
        "OPTIONS": {"pool": pool_options()},
        # Tests use the default test database instead of creating a second one.
        "TEST": {"MIRROR": "default"},
    },
}

DATABASE_ROUTERS = ["config.db_router.ReportsRouter"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Sessions and messages live in signed cookies, not the database,
# so the friendly "database down" page still works when PostgreSQL is off.
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "tracker:report"
LOGOUT_REDIRECT_URL = "portal:home"

# Switches for the connectivity demos (see README, "Demos")
HC_LOCK_DEMO_SECONDS = int(os.getenv("HC_LOCK_DEMO_SECONDS", "0"))
HC_FAIL_AFTER_UPDATE = env_bool("HC_FAIL_AFTER_UPDATE", False)

# Styling: False uses the prebuilt static/css/tailwind.css (works offline).
# True loads the Tailwind CDN instead, so new classes work while you edit (needs internet).
HC_TAILWIND_CDN = env_bool("HC_TAILWIND_CDN", False)

# Print every SQL query in the terminal while developing: set HC_SHOW_SQL=True in .env
if DEBUG and env_bool("HC_SHOW_SQL", False):
    LOGGING = {
        "version": 1,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "loggers": {"django.db.backends": {"handlers": ["console"], "level": "DEBUG"}},
    }

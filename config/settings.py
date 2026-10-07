import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(
    BASE_DIR / ".env.example"
)


SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "",
)

DEBUG = os.getenv(
    "DEBUG",
    "True",
).lower() == "true"

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "unsafe-dev-only-9z!NovaCart#change-this-before-any-real-deployment-2026"
    else:
        raise RuntimeError("SECRET_KEY must be set when DEBUG=False")


ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost",
    ).split(",")
    if host.strip()
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "store",
    "knowledge",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth."
                    "context_processors.auth"
                ),
                (
                    "django.contrib.messages."
                    "context_processors.messages"
                ),
            ],
        },
    },
]


WSGI_APPLICATION = "config.wsgi.application"


# PostgreSQL is used when POSTGRES_DB exists.
# Otherwise the project uses SQLite.
if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": (
                "django.db.backends.postgresql"
            ),
            "NAME": os.getenv(
                "POSTGRES_DB"
            ),
            "USER": os.getenv(
                "POSTGRES_USER"
            ),
            "PASSWORD": os.getenv(
                "POSTGRES_PASSWORD"
            ),
            "HOST": os.getenv(
                "POSTGRES_HOST",
                "localhost",
            ),
            "PORT": os.getenv(
                "POSTGRES_PORT",
                "5432",
            ),
        }
    }

else:
    DATABASES = {
        "default": {
            "ENGINE": (
                "django.db.backends.sqlite3"
            ),
            "NAME": (
                BASE_DIR / "db.sqlite3"
            ),
        }
    }


AUTH_PASSWORD_VALIDATORS = []


LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Kolkata"

USE_I18N = True

USE_TZ = True


STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = (
    BASE_DIR / "staticfiles"
)


MEDIA_URL = "/media/"

MEDIA_ROOT = (
    BASE_DIR / "media"
)


DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)


LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/customer/dashboard/"

LOGOUT_REDIRECT_URL = "/"


# Groq configuration
GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    "",
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)

# Optional multimodal model used only for product-image analysis.
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "")


# Maximum evidence sent to the chatbot.
# This prevents HTTP 413 Payload Too Large.
RAG_MAX_EVIDENCE_CHARS = int(
    os.getenv(
        "RAG_MAX_EVIDENCE_CHARS",
        "7500",
    )
)


# Website crawling configuration
MAX_CRAWL_PAGES = int(
    os.getenv(
        "MAX_CRAWL_PAGES",
        "15",
    )
)


# Document upload configuration
MAX_UPLOAD_MB = int(
    os.getenv(
        "MAX_UPLOAD_MB",
        "10",
    )
)

CHAT_MAX_MESSAGE_CHARS = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "2000"))
CRAWL_PAGE_TIMEOUT = int(os.getenv("CRAWL_PAGE_TIMEOUT", "45"))
CRAWL_INITIAL_WAIT = float(os.getenv("CRAWL_INITIAL_WAIT", "2"))
CRAWL_SCROLL_ROUNDS = int(os.getenv("CRAWL_SCROLL_ROUNDS", "8"))
CRAWL_SCROLL_WAIT = float(os.getenv("CRAWL_SCROLL_WAIT", "1"))
CRAWL_ALLOW_PRIVATE_HOSTS = os.getenv("CRAWL_ALLOW_PRIVATE_HOSTS", "False").lower() == "true"
PINCODE_API_BASE_URL = os.getenv("PINCODE_API_BASE_URL", "https://api.zippopotam.us")

CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
X_FRAME_OPTIONS = "DENY"

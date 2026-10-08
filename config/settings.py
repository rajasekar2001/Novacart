
# import os
# from pathlib import Path

# import dj_database_url
# from dotenv import load_dotenv


# # ============================================================
# # BASE DIRECTORY AND ENVIRONMENT
# # ============================================================

# BASE_DIR = Path(__file__).resolve().parent.parent

# # Load local development variables.
# # Render environment variables take precedence.
# load_dotenv(BASE_DIR / ".env.example")


# # ============================================================
# # SECURITY
# # ============================================================

# SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

# DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# if not SECRET_KEY:
#     if DEBUG:
#         SECRET_KEY = "unsafe-local-development-only-change-me"
#     else:
#         raise RuntimeError(
#             "SECRET_KEY environment variable is required in production."
#         )


# ALLOWED_HOSTS = [
#     host.strip()
#     for host in os.getenv(
#         "ALLOWED_HOSTS",
#         "127.0.0.1,localhost",
#     ).split(",")
#     if host.strip()
# ]

# RENDER_EXTERNAL_HOSTNAME = os.getenv(
#     "RENDER_EXTERNAL_HOSTNAME", ""
# ).strip()

# if (
#     RENDER_EXTERNAL_HOSTNAME
#     and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS
# ):
#     ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)


# CSRF_TRUSTED_ORIGINS = [
#     origin.strip()
#     for origin in os.getenv(
#         "CSRF_TRUSTED_ORIGINS", ""
#     ).split(",")
#     if origin.strip()
# ]

# if RENDER_EXTERNAL_HOSTNAME:
#     render_origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"

#     if render_origin not in CSRF_TRUSTED_ORIGINS:
#         CSRF_TRUSTED_ORIGINS.append(render_origin)


# # ============================================================
# # APPLICATIONS
# # ============================================================

# INSTALLED_APPS = [
#     "django.contrib.admin",
#     "django.contrib.auth",
#     "django.contrib.contenttypes",
#     "django.contrib.sessions",
#     "django.contrib.messages",

#     # Cloudinary image storage
#     "cloudinary_storage",

#     "django.contrib.staticfiles",

#     # NovaCart applications
#     "store",
#     "knowledge",
# ]


# # ============================================================
# # MIDDLEWARE
# # ============================================================

# MIDDLEWARE = [
#     "django.middleware.security.SecurityMiddleware",

#     # Serve static CSS, JavaScript and icons on Render
#     "whitenoise.middleware.WhiteNoiseMiddleware",

#     "django.contrib.sessions.middleware.SessionMiddleware",
#     "django.middleware.common.CommonMiddleware",
#     "django.middleware.csrf.CsrfViewMiddleware",
#     "django.contrib.auth.middleware.AuthenticationMiddleware",
#     "django.contrib.messages.middleware.MessageMiddleware",
#     "django.middleware.clickjacking.XFrameOptionsMiddleware",
# ]


# # ============================================================
# # URLS AND TEMPLATES
# # ============================================================

# ROOT_URLCONF = "config.urls"

# TEMPLATES = [
#     {
#         "BACKEND": "django.template.backends.django.DjangoTemplates",
#         "DIRS": [
#             BASE_DIR / "templates",
#         ],
#         "APP_DIRS": True,
#         "OPTIONS": {
#             "context_processors": [
#                 "django.template.context_processors.debug",
#                 "django.template.context_processors.request",
#                 "django.contrib.auth.context_processors.auth",
#                 "django.contrib.messages.context_processors.messages",
#             ],
#         },
#     },
# ]

# WSGI_APPLICATION = "config.wsgi.application"


# # ============================================================
# # DATABASE
# # ============================================================

# DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# if DATABASE_URL:

#     # Render PostgreSQL
#     DATABASES = {
#         "default": dj_database_url.config(
#             default=DATABASE_URL,
#             conn_max_age=600,
#             ssl_require=True,
#         )
#     }

# elif os.getenv("POSTGRES_DB"):

#     # Optional PostgreSQL configuration
#     DATABASES = {
#         "default": {
#             "ENGINE": "django.db.backends.postgresql",
#             "NAME": os.getenv("POSTGRES_DB"),
#             "USER": os.getenv("POSTGRES_USER"),
#             "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
#             "HOST": os.getenv("POSTGRES_HOST", "localhost"),
#             "PORT": os.getenv("POSTGRES_PORT", "5432"),
#         }
#     }

# else:

#     # Local SQLite database
#     DATABASES = {
#         "default": {
#             "ENGINE": "django.db.backends.sqlite3",
#             "NAME": BASE_DIR / "db.sqlite3",
#         }
#     }


# # ============================================================
# # PASSWORD VALIDATION
# # ============================================================

# AUTH_PASSWORD_VALIDATORS = [
#     {
#         "NAME": (
#             "django.contrib.auth.password_validation."
#             "UserAttributeSimilarityValidator"
#         ),
#     },
#     {
#         "NAME": (
#             "django.contrib.auth.password_validation."
#             "MinimumLengthValidator"
#         ),
#     },
#     {
#         "NAME": (
#             "django.contrib.auth.password_validation."
#             "CommonPasswordValidator"
#         ),
#     },
#     {
#         "NAME": (
#             "django.contrib.auth.password_validation."
#             "NumericPasswordValidator"
#         ),
#     },
# ]


# # ============================================================
# # INTERNATIONALIZATION
# # ============================================================

# LANGUAGE_CODE = "en-us"

# TIME_ZONE = "Asia/Kolkata"

# USE_I18N = True

# USE_TZ = True


# # ============================================================
# # STATIC FILES (CSS / JS / ICONS)
# # ============================================================

# STATIC_URL = "/static/"

# STATICFILES_DIRS = [
#     BASE_DIR / "static",
# ]

# STATIC_ROOT = BASE_DIR / "staticfiles"


# # ============================================================
# # MEDIA FILES (PRODUCT / CATEGORY IMAGES)
# # ============================================================

# MEDIA_URL = "/media/"

# MEDIA_ROOT = BASE_DIR / "media"

# CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()

# # Cloudinary for production uploads, local filesystem otherwise.
# MEDIA_STORAGE_BACKEND = (
#     "cloudinary_storage.storage.MediaCloudinaryStorage"
#     if CLOUDINARY_URL
#     else "django.core.files.storage.FileSystemStorage"
# )

# STORAGES = {
#     "default": {
#         "BACKEND": (
#             "cloudinary_storage.storage.MediaCloudinaryStorage"
#             if CLOUDINARY_URL
#             else "django.core.files.storage.FileSystemStorage"
#         ),
#     },
#     "staticfiles": {
#         "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
#     },
# }


# # ============================================================
# # DJANGO DEFAULTS
# # ============================================================

# DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# # ============================================================
# # LOGIN / LOGOUT
# # ============================================================

# LOGIN_URL = "/accounts/login/"

# LOGIN_REDIRECT_URL = "/customer/dashboard/"

# LOGOUT_REDIRECT_URL = "/"


# # ============================================================
# # GROQ AI
# # ============================================================

# GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

# GROQ_MODEL = os.getenv(
#     "GROQ_MODEL",
#     "openai/gpt-oss-120b",
# )

# GROQ_VISION_MODEL = os.getenv(
#     "GROQ_VISION_MODEL",
#     "",
# )


# # ============================================================
# # RAG / CHATBOT
# # ============================================================

# RAG_MAX_EVIDENCE_CHARS = int(
#     os.getenv("RAG_MAX_EVIDENCE_CHARS", "7500")
# )

# CHAT_MAX_MESSAGE_CHARS = int(
#     os.getenv("CHAT_MAX_MESSAGE_CHARS", "2000")
# )


# # ============================================================
# # WEBSITE CRAWLING
# # ============================================================

# MAX_CRAWL_PAGES = int(
#     os.getenv("MAX_CRAWL_PAGES", "15")
# )

# CRAWL_PAGE_TIMEOUT = int(
#     os.getenv("CRAWL_PAGE_TIMEOUT", "45")
# )

# CRAWL_INITIAL_WAIT = float(
#     os.getenv("CRAWL_INITIAL_WAIT", "2")
# )

# CRAWL_SCROLL_ROUNDS = int(
#     os.getenv("CRAWL_SCROLL_ROUNDS", "8")
# )

# CRAWL_SCROLL_WAIT = float(
#     os.getenv("CRAWL_SCROLL_WAIT", "1")
# )

# CRAWL_ALLOW_PRIVATE_HOSTS = (
#     os.getenv("CRAWL_ALLOW_PRIVATE_HOSTS", "False").lower()
#     == "true"
# )


# # ============================================================
# # DOCUMENT UPLOADS
# # ============================================================

# MAX_UPLOAD_MB = int(
#     os.getenv("MAX_UPLOAD_MB", "10")
# )


# # ============================================================
# # PINCODE API
# # ============================================================

# INDIA_PINCODE_API_BASE_URL = os.getenv(
#     "INDIA_PINCODE_API_BASE_URL",
#     "https://api.postalpincode.in/pincode",
# )

# PINCODE_API_BASE_URL = os.getenv(
#     "PINCODE_API_BASE_URL",
#     "https://api.zippopotam.us",
# )


# # ============================================================
# # PRODUCTION HTTPS / SECURITY
# # ============================================================

# CSRF_COOKIE_SECURE = not DEBUG

# SESSION_COOKIE_SECURE = not DEBUG

# SECURE_CONTENT_TYPE_NOSNIFF = True

# SECURE_SSL_REDIRECT = not DEBUG

# SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0

# SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG

# SECURE_HSTS_PRELOAD = False

# X_FRAME_OPTIONS = "DENY"

# SECURE_PROXY_SSL_HEADER = (
#     "HTTP_X_FORWARDED_PROTO",
#     "https",
# )





import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


# Local development only.
#
# Render supplies its environment variables directly.
load_dotenv(BASE_DIR / ".env")


SECRET_KEY = os.getenv("SECRET_KEY", "")

DEBUG = os.getenv(
    "DEBUG",
    "True",
).lower() == "true"


if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = (
            "unsafe-dev-only-change-this-before-production"
        )
    else:
        raise RuntimeError(
            "SECRET_KEY must be set when DEBUG=False"
        )


ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost",
    ).split(",")
    if host.strip()
]


RENDER_EXTERNAL_HOSTNAME = os.getenv(
    "RENDER_EXTERNAL_HOSTNAME"
)

if (
    RENDER_EXTERNAL_HOSTNAME
    and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS
):
    ALLOWED_HOSTS.append(
        RENDER_EXTERNAL_HOSTNAME
    )


CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CSRF_TRUSTED_ORIGINS",
        "",
    ).split(",")
    if origin.strip()
]

if RENDER_EXTERNAL_HOSTNAME:
    render_origin = (
        f"https://{RENDER_EXTERNAL_HOSTNAME}"
    )

    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(
            render_origin
        )


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

WSGI_APPLICATION = "config.wsgi.application"


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


# ============================================================
# DATABASE
# ============================================================

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "",
).strip()


if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }

elif os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
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
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
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

STATIC_ROOT = BASE_DIR / "staticfiles"


STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)


LOGIN_URL = "/accounts/login/"

LOGIN_REDIRECT_URL = "/customer/dashboard/"

LOGOUT_REDIRECT_URL = "/"


# ============================================================
# GROQ
# ============================================================

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    "",
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

GROQ_VISION_MODEL = os.getenv(
    "GROQ_VISION_MODEL",
    "",
)


# ============================================================
# RAG
# ============================================================

RAG_MAX_EVIDENCE_CHARS = int(
    os.getenv(
        "RAG_MAX_EVIDENCE_CHARS",
        "7500",
    )
)


# ============================================================
# CRAWLER
# ============================================================

MAX_CRAWL_PAGES = int(
    os.getenv(
        "MAX_CRAWL_PAGES",
        "15",
    )
)

CRAWL_PAGE_TIMEOUT = int(
    os.getenv(
        "CRAWL_PAGE_TIMEOUT",
        "45",
    )
)

CRAWL_INITIAL_WAIT = float(
    os.getenv(
        "CRAWL_INITIAL_WAIT",
        "2",
    )
)

CRAWL_SCROLL_ROUNDS = int(
    os.getenv(
        "CRAWL_SCROLL_ROUNDS",
        "8",
    )
)

CRAWL_SCROLL_WAIT = float(
    os.getenv(
        "CRAWL_SCROLL_WAIT",
        "1",
    )
)

CRAWL_ALLOW_PRIVATE_HOSTS = (
    os.getenv(
        "CRAWL_ALLOW_PRIVATE_HOSTS",
        "False",
    ).lower()
    == "true"
)


# ============================================================
# UPLOAD / CHAT
# ============================================================

MAX_UPLOAD_MB = int(
    os.getenv(
        "MAX_UPLOAD_MB",
        "10",
    )
)

CHAT_MAX_MESSAGE_CHARS = int(
    os.getenv(
        "CHAT_MAX_MESSAGE_CHARS",
        "2000",
    )
)


# ============================================================
# PINCODE APIs
# ============================================================

INDIA_PINCODE_API_BASE_URL = os.getenv(
    "INDIA_PINCODE_API_BASE_URL",
    "https://api.postalpincode.in/pincode",
)

PINCODE_API_BASE_URL = os.getenv(
    "PINCODE_API_BASE_URL",
    "https://api.zippopotam.us",
)


# ============================================================
# PRODUCTION SECURITY
# ============================================================

CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_SECURE = not DEBUG

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_SSL_REDIRECT = not DEBUG

SECURE_HSTS_SECONDS = (
    31536000 if not DEBUG else 0
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    not DEBUG
)

SECURE_HSTS_PRELOAD = (
    not DEBUG
)

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

X_FRAME_OPTIONS = "DENY"


# import os
# from pathlib import Path

# from dotenv import load_dotenv


# BASE_DIR = Path(__file__).resolve().parent.parent

# load_dotenv(
#     BASE_DIR / ".env.example"
# )


# SECRET_KEY = os.getenv(
#     "SECRET_KEY",
#     "",
# )

# DEBUG = os.getenv(
#     "DEBUG",
#     "True",
# ).lower() == "true"

# if not SECRET_KEY:
#     if DEBUG:
#         SECRET_KEY = "unsafe-dev-only-9z!NovaCart#change-this-before-any-real-deployment-2026"
#     else:
#         raise RuntimeError("SECRET_KEY must be set when DEBUG=False")


# ALLOWED_HOSTS = [
#     host.strip()
#     for host in os.getenv(
#         "ALLOWED_HOSTS",
#         "127.0.0.1,localhost",
#     ).split(",")
#     if host.strip()
# ]


# INSTALLED_APPS = [
#     "django.contrib.admin",
#     "django.contrib.auth",
#     "django.contrib.contenttypes",
#     "django.contrib.sessions",
#     "django.contrib.messages",
#     "django.contrib.staticfiles",
#     "store",
#     "knowledge",
# ]


# MIDDLEWARE = [
#     "django.middleware.security.SecurityMiddleware",
#     "whitenoise.middleware.WhiteNoiseMiddleware",
#     "django.contrib.sessions.middleware.SessionMiddleware",
#     "django.middleware.common.CommonMiddleware",
#     "django.middleware.csrf.CsrfViewMiddleware",
#     "django.contrib.auth.middleware.AuthenticationMiddleware",
#     "django.contrib.messages.middleware.MessageMiddleware",
#     "django.middleware.clickjacking.XFrameOptionsMiddleware",
# ]


# ROOT_URLCONF = "config.urls"


# TEMPLATES = [
#     {
#         "BACKEND": (
#             "django.template.backends.django."
#             "DjangoTemplates"
#         ),
#         "DIRS": [
#             BASE_DIR / "templates",
#         ],
#         "APP_DIRS": True,
#         "OPTIONS": {
#             "context_processors": [
#                 (
#                     "django.template.context_processors."
#                     "request"
#                 ),
#                 (
#                     "django.contrib.auth."
#                     "context_processors.auth"
#                 ),
#                 (
#                     "django.contrib.messages."
#                     "context_processors.messages"
#                 ),
#             ],
#         },
#     },
# ]


# WSGI_APPLICATION = "config.wsgi.application"


# # PostgreSQL is used when POSTGRES_DB exists.
# # Otherwise the project uses SQLite.
# if os.getenv("POSTGRES_DB"):
#     DATABASES = {
#         "default": {
#             "ENGINE": (
#                 "django.db.backends.postgresql"
#             ),
#             "NAME": os.getenv(
#                 "POSTGRES_DB"
#             ),
#             "USER": os.getenv(
#                 "POSTGRES_USER"
#             ),
#             "PASSWORD": os.getenv(
#                 "POSTGRES_PASSWORD"
#             ),
#             "HOST": os.getenv(
#                 "POSTGRES_HOST",
#                 "localhost",
#             ),
#             "PORT": os.getenv(
#                 "POSTGRES_PORT",
#                 "5432",
#             ),
#         }
#     }

# else:
#     DATABASES = {
#         "default": {
#             "ENGINE": (
#                 "django.db.backends.sqlite3"
#             ),
#             "NAME": (
#                 BASE_DIR / "db.sqlite3"
#             ),
#         }
#     }


# AUTH_PASSWORD_VALIDATORS = []


# LANGUAGE_CODE = "en-us"

# TIME_ZONE = "Asia/Kolkata"

# USE_I18N = True

# USE_TZ = True


# STATIC_URL = "/static/"

# STATICFILES_DIRS = [
#     BASE_DIR / "static",
# ]

# STATIC_ROOT = (
#     BASE_DIR / "staticfiles"
# )


# MEDIA_URL = "/media/"

# MEDIA_ROOT = (
#     BASE_DIR / "media"
# )


# DEFAULT_AUTO_FIELD = (
#     "django.db.models.BigAutoField"
# )


# LOGIN_URL = "/accounts/login/"
# LOGIN_REDIRECT_URL = "/customer/dashboard/"

# LOGOUT_REDIRECT_URL = "/"


# # Groq configuration
# GROQ_API_KEY = os.getenv(
#     "GROQ_API_KEY",
#     "",
# )

# GROQ_MODEL = os.getenv(
#     "GROQ_MODEL",
#     "openai/gpt-oss-20b",
# )

# # Optional multimodal model used only for product-image analysis.
# GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "")


# # Maximum evidence sent to the chatbot.
# # This prevents HTTP 413 Payload Too Large.
# RAG_MAX_EVIDENCE_CHARS = int(
#     os.getenv(
#         "RAG_MAX_EVIDENCE_CHARS",
#         "7500",
#     )
# )


# # Website crawling configuration
# MAX_CRAWL_PAGES = int(
#     os.getenv(
#         "MAX_CRAWL_PAGES",
#         "15",
#     )
# )


# # Document upload configuration
# MAX_UPLOAD_MB = int(
#     os.getenv(
#         "MAX_UPLOAD_MB",
#         "10",
#     )
# )

# CHAT_MAX_MESSAGE_CHARS = int(os.getenv("CHAT_MAX_MESSAGE_CHARS", "2000"))
# CRAWL_PAGE_TIMEOUT = int(os.getenv("CRAWL_PAGE_TIMEOUT", "45"))
# CRAWL_INITIAL_WAIT = float(os.getenv("CRAWL_INITIAL_WAIT", "2"))
# CRAWL_SCROLL_ROUNDS = int(os.getenv("CRAWL_SCROLL_ROUNDS", "8"))
# CRAWL_SCROLL_WAIT = float(os.getenv("CRAWL_SCROLL_WAIT", "1"))
# CRAWL_ALLOW_PRIVATE_HOSTS = os.getenv("CRAWL_ALLOW_PRIVATE_HOSTS", "False").lower() == "true"
# PINCODE_API_BASE_URL = os.getenv("PINCODE_API_BASE_URL", "https://api.zippopotam.us")

# CSRF_COOKIE_SECURE = not DEBUG
# SESSION_COOKIE_SECURE = not DEBUG
# SECURE_CONTENT_TYPE_NOSNIFF = True
# SECURE_SSL_REDIRECT = not DEBUG
# SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
# SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
# SECURE_HSTS_PRELOAD = not DEBUG
# X_FRAME_OPTIONS = "DENY"

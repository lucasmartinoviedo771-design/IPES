# academia_project/settings.py
from pathlib import Path
import os
import sys
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------
# Logging (silenciar ruidos puntuales)
# -----------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "null": {"class": "logging.NullHandler"},
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "academia_core.forms_carga": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "ui": {"handlers": ["console"], "level": "INFO"},
        "django.request": {"handlers": ["console"], "level": "ERROR"},
    },
}

# -----------------------------
# .env (opcional)
# -----------------------------
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


# -----------------------------
# Seguridad / Debug
# -----------------------------
def getenv_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in {"1", "true", "t", "yes", "y"}


# EN PRODUCCIÓN, SIEMPRE DEBUG=False
# En el entorno de pruebas, Django lo setea a False automáticamente.
DEBUG = getenv_bool("DJANGO_DEBUG", default=False)

# IMPORTANTE: Esta clave es solo para desarrollo.
# En producción, DEBES usar una clave segura y única desde una variable de entorno.
DEFAULT_DEV_SECRET = (
    "django-insecure-7p6^%e4ayapj2o4tu7wx^&qlaczf8cj=(uh45aq*(((@vc1a8_"
)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_DEV_SECRET)

# Permitir todos los hosts en desarrollo/pruebas, pero requerir configuración en producción.
ALLOWED_HOSTS = ["*"]

# --- Configuraciones de seguridad para Producción ---
if not DEBUG and "test" not in sys.argv:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # ALLOWED_HOSTS no puede estar vacío en producción
    hosts = os.getenv("DJANGO_ALLOWED_HOSTS")
    if not hosts:
        raise ImproperlyConfigured(
            "En producción, la variable de entorno DJANGO_ALLOWED_HOSTS no puede estar vacía."
        )
    ALLOWED_HOSTS = [h.strip() for h in hosts.split(",") if h.strip()]

    # La SECRET_KEY de desarrollo no es segura para producción
    if SECRET_KEY == DEFAULT_DEV_SECRET:
        raise ImproperlyConfigured(
            "En producción, debes configurar la variable de entorno DJANGO_SECRET_KEY con un valor seguro."
        )

# -----------------------------
# Apps
# -----------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    # Apps propias
    "academia_core.apps.AcademiaCoreConfig",
    "ui",
]

# -----------------------------
# Middleware
# -----------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "academia_project.urls"

# -----------------------------
# Templates
# -----------------------------
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Directorio(s) de templates a nivel de proyecto (opcional)
        "DIRS": [BASE_DIR / "templates"],
        # Busca automáticamente en 'templates' dentro de cada app instalada
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ui.context_processors.menu",
                "ui.context_processors.ui_globals",
            ],
            # Cargar tags/filters globales (opcional)
            "builtins": [
                "ui.templatetags.icons",
            ],
        },
    },
]


WSGI_APPLICATION = "academia_project.wsgi.application"

# -----------------------------
# Base de datos (MySQL)
# -----------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "academia"),
        "USER": os.getenv("DB_USER", "academia"),
        "PASSWORD": os.getenv("DB_PASSWORD", "TuClaveSegura123"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# -----------------------------
# Password validators
# -----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# -----------------------------
# i18n
# -----------------------------
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# -----------------------------
# Static & Media
# -----------------------------
STATIC_URL = "/static/"

# Agrega solo las carpetas de estáticos que existan para evitar warnings
_static_candidates = [
    BASE_DIR / "ui" / "static",  # donde suele estar ui/img/avatar-placeholder.svg, etc.
    BASE_DIR / "static",  # opcional si la usás
]
STATICFILES_DIRS = [p for p in _static_candidates if p.exists()]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -----------------------------
# Login / Logout
# -----------------------------
LOGIN_URL = "login"  # o "ui:login" si tu URL está namespaced
LOGIN_REDIRECT_URL = "/dashboard"
LOGOUT_REDIRECT_URL = "login"

# -----------------------------
# DRF (básico)
# -----------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# -----------------------------
# Varios
# -----------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

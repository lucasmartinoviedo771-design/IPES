from pathlib import Path
import os
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Logging: silenciado para academia_core.forms_carga ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        # Handler “nulo” para descartar mensajes
        "null": {"class": "logging.NullHandler"},
        # Si querés ver algo en consola, podés reactivar este:
        # "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        # Apaga por completo los logs del form de inscripción a espacio
        "academia_core.forms_carga": {
            "handlers": ["null"],
            "level": "CRITICAL",  # nada va a pasar por acá
            "propagate": False,
        },
        # Si alguna vez querés ver SQL, podés habilitar esto:
        # "django.db.backends": {
        #     "handlers": ["console"],
        #     "level": "WARNING",
        #     "propagate": False,
        # },
    },
}

# (Opcional) .env para credenciales sin hardcodear
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# -----------------------------
# Seguridad / Debug (dev-friendly)
# -----------------------------

def getenv_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in {"1", "true", "t", "yes", "y"}

# Por defecto arrancamos en desarrollo
DEBUG = getenv_bool("DJANGO_DEBUG", default=True)

# Clave por defecto SOLO para desarrollo (podés cambiarla si querés)
DEFAULT_DEV_SECRET = "django-insecure-7p6^%e4ayapj2o4tu7wx^&qlaczf8cj=(uh45aq*(((@vc1a8_"

if DEBUG:
    # En desarrollo permitimos no tener variables de entorno
    SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", DEFAULT_DEV_SECRET)
    ALLOWED_HOSTS = []
else:
    # En producción exigimos variables de entorno correctas
    SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
    if not SECRET_KEY:
        raise ImproperlyConfigured("Set the DJANGO_SECRET_KEY environment variable")

    hosts = os.getenv("DJANGO_ALLOWED_HOSTS")
    if not hosts:
        raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS (comma separated)")

    ALLOWED_HOSTS = [h.strip() for h in hosts.split(",") if h.strip()]

# Security headers (podés habilitarlas en prod)
# SECURE_SSL_REDIRECT = not DEBUG
# SECURE_HSTS_SECONDS = 31536000  # 1 año
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SECURE_CONTENT_TYPE_NOSNIFF = True
# SECURE_BROWSER_XSS_FILTER = True
# X_FRAME_OPTIONS = "DENY"  # Ya lo setea XFrameOptionsMiddleware por defecto

# Cookies de sesión/CSRF: seguras en prod, flexibles en dev
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG

# --- Apps ---
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
    # App propia (usar AppConfig para cargar signals en ready())
    "academia_core.apps.AcademiaCoreConfig",
]

# --- Middleware ---
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

# --- Templates ---
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",  # carpeta de templates del proyecto (opcional)
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # expone login_url y logout_url en todos los templates
                "academia_core.context_processors.auth_urls",
            ],
        },
    },
]

WSGI_APPLICATION = "academia_project.wsgi.application"

# --- Base de datos (MySQL) ---
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

# --- Password validators ---
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Internacionalización ---
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# --- Archivos estáticos y de medios ---
STATIC_URL = "/static/"
# STATICFILES_DIRS = [BASE_DIR / "static"]  # si usás una carpeta global

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Login/Logout (para vistas protegidas) ---
LOGIN_URL = "/accounts/login/"  # explícito
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# --- DRF básico (opcional)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# --- Misc ---
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

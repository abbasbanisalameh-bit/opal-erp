"""
Django settings for Opal School Management System.
"""

import os
from pathlib import Path

# -------------------------
# المسارات
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    """Read a boolean environment flag using one consistent policy."""
    fallback = "True" if default else "False"
    return os.environ.get(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default):
    value = os.environ.get(name, "")
    if not value.strip():
        return list(default)
    return [item.strip() for item in value.split(",") if item.strip()]


# -------------------------
# الأمان
# -------------------------
SECRET_KEY = os.environ.get(
    "OPAL_SECRET_KEY",
    "django-insecure-change-this-key-before-production",
)

DEBUG = env_bool("OPAL_DEBUG", False)

# Optional foundations stay outside the production school surface by default.
# They can be enabled explicitly in a dedicated environment without deleting code.
OPAL_ENABLE_OPENEMIS = env_bool("OPAL_ENABLE_OPENEMIS", True)
OPAL_ENABLE_DEVELOPMENT_CENTER = env_bool("OPAL_ENABLE_DEVELOPMENT_CENTER", True)

ALLOWED_HOSTS = env_list("OPAL_ALLOWED_HOSTS", [
    "Opalschool2016.pythonanywhere.com",
    "opalschool2016.pythonanywhere.com",
    "localhost",
    "127.0.0.1",
])


# -------------------------
# التطبيقات
# -------------------------
INSTALLED_APPS = [
    'attendance_v2',
    'parent_portal',
    'openemis_integration',
    'accounting',
    'exams',
    'documents',
    'announcements',
    'admissions',
    'academics',
    'core',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'dashboard',
    'accounts',
    'students',
    'teachers',
    'timetable',
    'curriculum',
    'enterprise_ops.apps.EnterpriseOpsConfig',
]

if OPAL_ENABLE_DEVELOPMENT_CENTER:
    INSTALLED_APPS.insert(0, 'development_center')


# -------------------------
# Middleware
# -------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'parent_portal.middleware.ParentPortalAccessMiddleware',
    'teachers.middleware.TeacherPortalAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'config.urls'


# -------------------------
# Templates
# -------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'announcements.context_processors.active_announcement',
                'core.context_processors.opal_identity',
                'enterprise_ops.context_processors.enterprise_notifications',
            ],
        },
    },
]


WSGI_APPLICATION = 'config.wsgi.application'


# -------------------------
# قاعدة البيانات
# -------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# -------------------------
# كلمات المرور
# -------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# -------------------------
# اللغة والتوقيت
# -------------------------
LANGUAGE_CODE = 'ar'

TIME_ZONE = 'Asia/Amman'

USE_I18N = True

USE_TZ = True


# -------------------------
# الملفات الثابتة
# -------------------------
STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'


# -------------------------
# ملفات الوسائط
# -------------------------
MEDIA_URL = '/media/'

MEDIA_ROOT = BASE_DIR / 'media'


# -------------------------
# المفتاح الافتراضي
# -------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

CSRF_TRUSTED_ORIGINS = env_list("OPAL_CSRF_TRUSTED_ORIGINS", [
    "https://opalschool2016.pythonanywhere.com",
])
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Keep CSRF protection enabled, but replace Django's technical failure page with
# an OPAL-safe recovery flow.  In particular, a stale cached login form is
# refreshed without retrying or exposing the submitted credentials.
CSRF_FAILURE_VIEW = "core.security.csrf_failure"


# Production hardening is enabled automatically when OPAL_DEBUG=False.
if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_SSL_REDIRECT = env_bool("OPAL_SECURE_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = int(os.environ.get("OPAL_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
    SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0

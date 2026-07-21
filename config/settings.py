"""
Django settings for Opal School Management System.
"""

from pathlib import Path

from .app_registry import build_installed_apps
from .deployment_security import build_production_security, build_proxy_ssl_header, get_secret_key
from .environment import env_bool
from .operational_registry import (
    build_allowed_hosts,
    build_csrf_trusted_origins,
    build_feature_flags,
    get_default_auto_field,
)
from .runtime_registry import build_context_processors, build_middleware
from .resource_registry import build_media_paths, build_static_paths, build_templates
from .security_registry import build_databases, build_password_validators
from .site_preferences import build_auth_navigation, build_localization, build_session_preferences

# -------------------------
# المسارات
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent



# -------------------------
# الأمان
# -------------------------
SECRET_KEY = get_secret_key()

DEBUG = env_bool("OPAL_DEBUG", False)

# Existing modules remain enabled by default so no feature is hidden or deleted.
# An environment may disable an optional foundation explicitly without removing its code.
_FEATURE_FLAGS = build_feature_flags()
OPAL_ENABLE_OPENEMIS = _FEATURE_FLAGS["openemis"]
OPAL_ENABLE_DEVELOPMENT_CENTER = _FEATURE_FLAGS["development_center"]

ALLOWED_HOSTS = build_allowed_hosts()


# -------------------------
# التطبيقات
# -------------------------
INSTALLED_APPS = build_installed_apps(
    enable_development_center=OPAL_ENABLE_DEVELOPMENT_CENTER,
)


# -------------------------
# Middleware
# -------------------------
MIDDLEWARE = build_middleware()


ROOT_URLCONF = 'config.urls'


# -------------------------
# Templates
# -------------------------
TEMPLATES = build_templates(
    BASE_DIR,
    build_context_processors(),
)


WSGI_APPLICATION = 'config.wsgi.application'


# -------------------------
# قاعدة البيانات
# -------------------------
DATABASES = build_databases(BASE_DIR)


# -------------------------
# كلمات المرور
# -------------------------
AUTH_PASSWORD_VALIDATORS = build_password_validators()


# -------------------------
# اللغة والتوقيت
# -------------------------
LANGUAGE_CODE, TIME_ZONE, USE_I18N, USE_TZ = build_localization()


# -------------------------
# الملفات الثابتة
# -------------------------
STATIC_URL, STATICFILES_DIRS, STATIC_ROOT = build_static_paths(BASE_DIR)


# -------------------------
# ملفات الوسائط
# -------------------------
MEDIA_URL, MEDIA_ROOT = build_media_paths(BASE_DIR)


# -------------------------
# تفضيلات الموقع والجلسات
# -------------------------
DEFAULT_AUTO_FIELD = get_default_auto_field()
LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL = build_auth_navigation()
SESSION_COOKIE_SAMESITE, CSRF_COOKIE_SAMESITE, CSRF_FAILURE_VIEW = build_session_preferences()

CSRF_TRUSTED_ORIGINS = build_csrf_trusted_origins()
SECURE_PROXY_SSL_HEADER = build_proxy_ssl_header()


# Production hardening is enabled automatically when OPAL_DEBUG=False.
globals().update(build_production_security(debug=DEBUG))

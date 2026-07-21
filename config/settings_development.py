"""Dedicated settings for the OPAL development-center deployment.

The school production site uses ``config.settings``. A separate private WSGI
application can use this module while preserving the established app and
middleware ordering.
"""

from .settings import *  # noqa: F401,F403
from .app_registry import ensure_development_center_app
from .runtime_registry import ensure_development_center_middleware

OPAL_ENABLE_DEVELOPMENT_CENTER = True
INSTALLED_APPS = ensure_development_center_app(INSTALLED_APPS)
MIDDLEWARE = ensure_development_center_middleware(MIDDLEWARE)

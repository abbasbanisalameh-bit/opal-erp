"""Dedicated settings for the OPAL development-center deployment.

The school production site uses ``config.settings`` and does not install or expose
the development center.  A separate private WSGI application can use this module.
"""

from .settings import *  # noqa: F401,F403

OPAL_ENABLE_DEVELOPMENT_CENTER = True

if "development_center" not in INSTALLED_APPS:
    INSTALLED_APPS.insert(0, "development_center")

auth_index = MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
MIDDLEWARE.insert(auth_index + 1, "core.middleware.DevelopmentCenterAccessMiddleware")

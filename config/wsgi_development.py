"""WSGI entry point for the private OPAL development-center site."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_development")

application = get_wsgi_application()

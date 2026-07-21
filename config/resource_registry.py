"""Central registry for template, static, and media resource settings."""


def build_templates(base_dir, context_processors):
    """Return the existing Django template backend configuration unchanged."""
    return [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [base_dir / "templates"],
            "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": list(context_processors),
            },
        },
    ]


def build_static_paths(base_dir):
    """Return STATIC_URL, STATICFILES_DIRS, and STATIC_ROOT."""
    return "static/", [base_dir / "static"], base_dir / "staticfiles"


def build_media_paths(base_dir):
    """Return MEDIA_URL and MEDIA_ROOT."""
    return "/media/", base_dir / "media"

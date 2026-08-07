"""Failure isolation for notifications, integrations and other side effects."""

import logging


logger = logging.getLogger("opal.secondary_effects")


def run_secondary_effect(callback, *args, label="secondary effect", default=None, **kwargs):
    """Run a non-critical callback without failing the saved school operation."""
    try:
        return callback(*args, **kwargs)
    except Exception:
        logger.exception("Secondary OPAL effect failed: %s", label)
        return default

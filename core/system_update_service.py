"""Stable public entry point for the self-updating OPAL update center."""

from . import update_engine_runtime as _runtime

globals().update(
    {
        name: value
        for name, value in vars(_runtime).items()
        if not name.startswith("__")
    }
)

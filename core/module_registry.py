"""Canonical modular registry for OPAL ERP.

The registry is deliberately derived from the existing workflow catalogue so each
module keeps one source of truth while exposing stable metadata for isolation,
visibility and future maintenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from django.conf import settings

from .workflow_catalog import MODULES


@dataclass(frozen=True)
class ModuleDefinition:
    key: str
    label: str
    icon: str
    color: str
    order: int
    enabled: bool = True


def _enabled(key: str) -> bool:
    if key == "openemis":
        return bool(getattr(settings, "OPAL_ENABLE_OPENEMIS", False))
    if key == "development":
        return bool(getattr(settings, "OPAL_ENABLE_DEVELOPMENT_CENTER", False))
    return True


def build_module_registry() -> tuple[ModuleDefinition, ...]:
    """Return the single canonical module registry in display order."""
    items = []
    for key, meta in MODULES.items():
        items.append(ModuleDefinition(
            key=key,
            label=meta["label"],
            icon=meta["icon"],
            color=meta["color"],
            order=int(meta["order"]),
            enabled=_enabled(key),
        ))
    return tuple(sorted(items, key=lambda item: (item.order, item.key)))


def enabled_module_registry() -> tuple[ModuleDefinition, ...]:
    return tuple(item for item in build_module_registry() if item.enabled)

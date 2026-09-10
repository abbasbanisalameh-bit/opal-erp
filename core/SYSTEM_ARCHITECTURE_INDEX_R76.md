# OPAL R76 — System Architecture Index

## Sources of truth
- `core/workflow_catalog.py`: canonical operations and sidebar entry doors.
- `core/information_architecture.py`: canonical information gateways.
- `core/module_registry.py`: normalized module metadata derived from `workflow_catalog.MODULES`.
- `templates/base/base.html`: one global UI shell.
- `static/css/opal_theme_system.css`: final CSS authority.

## Single-path rule
A business operation has one canonical entry route. Compatibility/detail routes remain inside the owning workflow and are not promoted into a second navigation path.

## UI rule
All global interface changes are applied through the shared shell and canonical theme whenever possible. Page-specific code should only supply business content, not a parallel visual system.

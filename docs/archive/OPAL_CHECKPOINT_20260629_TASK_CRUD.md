# OPAL ERP Checkpoint - Task CRUD

Date: 2026-06-29

## Scope
Development Center / Task CRUD checkpoint.

## Changes
- Fixed missing `TaskForm` import in `development_center/views.py`.
- Added task list view and route: `/development/tasks/`.
- Moved Kanban board route to: `/development/tasks/board/`.
- Added task detail view and route: `/development/tasks/<id>/`.
- Added task list template: `templates/development_center/tasks/list.html`.
- Added task detail template: `templates/development_center/tasks/detail.html`.
- Improved Kanban status update to register `ActivityLog` entries.
- When a task is moved to Done, progress is set to 100%.

## Verification
- `python manage.py check` passed.
- `python manage.py makemigrations --check --dry-run development_center` reported no model changes.
- Existing applied migrations for `development_center` are complete through `0011_activitylog_user`.

## Next Step
Manually test the browser flow:
1. Open `/development/tasks/`.
2. Add a task.
3. View task details.
4. Edit the task.
5. Open `/development/tasks/board/` and move task status.
6. Confirm Activity Log and Module progress update.

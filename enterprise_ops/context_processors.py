from django.db.models import Count, Max, Q

from .services import visible_notifications_for_user


def enterprise_notifications(request):
    """Expose the notification bell without running operational writes.

    Global context processors execute on every authenticated page.  Earlier
    code also synchronized attendance registers here, which could scan and
    update SQLite records while a user was merely opening an unrelated page.
    Attendance synchronization remains available from its canonical attendance
    dashboard/report workflows; this shared context is intentionally read-only.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    qs = visible_notifications_for_user(request.user)
    summary = qs.aggregate(
        unread_count=Count("pk", filter=Q(is_read=False)),
        latest_sound_id=Max("pk", filter=Q(is_read=False, sound_enabled=True)),
    )
    return {
        "opal_unread_notifications_count": summary["unread_count"] or 0,
        "opal_recent_notifications": qs[:5],
        "opal_latest_unread_notification_id": summary["latest_sound_id"] or "",
    }

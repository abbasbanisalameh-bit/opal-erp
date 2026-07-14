def enterprise_notifications(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    qs = request.user.opal_notifications.all()
    return {
        "opal_unread_notifications_count": qs.filter(is_read=False).count(),
        "opal_recent_notifications": qs[:5],
    }

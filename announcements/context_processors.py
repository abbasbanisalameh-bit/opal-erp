from .models import Announcement


def active_announcement(request):
    if hasattr(request, "_opal_active_announcement"):
        announcement = request._opal_active_announcement
    else:
        announcement = Announcement.objects.filter(is_active=True).first()
    return {
        "active_announcement": announcement
    }

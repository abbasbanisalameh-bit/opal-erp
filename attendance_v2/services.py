from enterprise_ops.services import notify
from django.urls import reverse


def notify_parent_for_attendance(record):
    if record.status not in {"absent", "departed"}:
        return []
    recipients = {}
    for link in record.student.family_links.select_related("family__user").filter(is_active=True):
        if link.family.user_id:
            recipients[link.family.user_id] = link.family.user
    label = record.get_status_display()
    title = f"تنبيه حضور: {record.student.full_name}"
    message = f"تم تسجيل حالة الطالب {label} بتاريخ {record.date}."
    return [
        notify(
            user,
            title,
            message,
            "warning",
            f"{reverse('parent_portal:attendance')}?student={record.student_id}&date={record.date.isoformat()}",
            event_key=f"attendance:{record.pk}:{record.status}:user:{user.pk}",
        )
        for user in recipients.values()
    ]

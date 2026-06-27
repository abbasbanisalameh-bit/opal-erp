from django.db import models


class Announcement(models.Model):
    ANNOUNCEMENT_TYPES = [
        ("info", "معلومة"),
        ("success", "نجاح"),
        ("warning", "تنبيه"),
        ("danger", "عاجل"),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPES, default="info")
    is_active = models.BooleanField(default=True)
    speed_seconds = models.PositiveIntegerField(default=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

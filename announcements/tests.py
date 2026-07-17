from django.test import RequestFactory, TestCase

from .context_processors import active_announcement
from .models import Announcement


class AnnouncementContextTests(TestCase):
    def test_only_active_announcement_is_exposed(self):
        Announcement.objects.create(title="متوقف", message="قديم", is_active=False)
        active = Announcement.objects.create(title="تنبيه المدرسة", message="رسالة", is_active=True)
        context = active_announcement(RequestFactory().get("/"))
        self.assertEqual(context["active_announcement"], active)

    def test_empty_context_is_safe(self):
        context = active_announcement(RequestFactory().get("/"))
        self.assertIsNone(context["active_announcement"])

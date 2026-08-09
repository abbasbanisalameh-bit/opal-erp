from django.test import SimpleTestCase

from .views import _lesson_video_player


class R32InPageLessonVideoPlayerTests(SimpleTestCase):
    def test_youtube_watch_url_becomes_privacy_enhanced_embed(self):
        player = _lesson_video_player("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(player["kind"], "iframe")
        self.assertEqual(player["provider"], "YouTube")
        self.assertEqual(player["url"], "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")

    def test_youtube_short_url_becomes_embed(self):
        player = _lesson_video_player("https://youtu.be/dQw4w9WgXcQ?t=15")
        self.assertEqual(player["url"], "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ")

    def test_vimeo_url_becomes_official_embed(self):
        player = _lesson_video_player("https://vimeo.com/123456789")
        self.assertEqual(player["kind"], "iframe")
        self.assertEqual(player["url"], "https://player.vimeo.com/video/123456789")

    def test_direct_video_uses_native_player(self):
        player = _lesson_video_player("https://cdn.example.com/lesson/video.mp4?token=abc")
        self.assertEqual(player["kind"], "video")
        self.assertEqual(player["url"], "https://cdn.example.com/lesson/video.mp4?token=abc")

    def test_other_https_url_stays_in_sandboxed_frame_contract(self):
        player = _lesson_video_player("https://video.example.com/watch/lesson-1")
        self.assertEqual(player["kind"], "iframe")
        self.assertEqual(player["url"], "https://video.example.com/watch/lesson-1")
        self.assertEqual(player["provider"], "video.example.com")

    def test_non_http_scheme_is_rejected(self):
        self.assertIsNone(_lesson_video_player("javascript:alert(1)"))

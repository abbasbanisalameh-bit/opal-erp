from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class R32InPageLessonVideoPlayerContractTests(unittest.TestCase):
    def source(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_lesson_template_uses_in_page_player_without_new_window_link(self):
        template = self.source("templates/learning_platform/lesson_detail.html")
        self.assertIn('class="learning-video-browser"', template)
        self.assertIn('class="learning-video-browser-screen"', template)
        self.assertIn("lesson_video_player.kind", template)
        self.assertIn("<iframe", template)
        self.assertIn("<video", template)
        self.assertNotIn('href="{{ lesson.video_url }}" target="_blank"', template)
        self.assertIn("دون مغادرة صفحة الدرس", template)

    def test_player_helper_supports_known_embeds_and_direct_video(self):
        source = self.source("learning_platform/views.py")
        self.assertIn("def _lesson_video_player(video_url):", source)
        self.assertIn("youtube-nocookie.com/embed", source)
        self.assertIn("player.vimeo.com/video", source)
        self.assertIn('"kind": "video"', source)
        self.assertIn('"kind": "iframe"', source)

    def test_lesson_detail_passes_player_context_to_template(self):
        source = self.source("learning_platform/views.py")
        lesson_detail = source.split("def lesson_detail(request, course_slug, lesson_slug):", 1)[1]
        lesson_detail = lesson_detail.split("def lesson_complete", 1)[0]
        self.assertIn("lesson_video_player=_lesson_video_player(lesson.video_url)", lesson_detail)

    def test_embedded_frame_is_sandboxed(self):
        template = self.source("templates/learning_platform/lesson_detail.html")
        self.assertIn('sandbox="allow-scripts allow-same-origin allow-presentation allow-forms"', template)
        self.assertIn('referrerpolicy="strict-origin-when-cross-origin"', template)
        self.assertIn("allowfullscreen", template)

    def test_responsive_player_styles_exist(self):
        css = self.source("static/learning_platform/css/platform.css")
        self.assertIn(".learning-video-browser", css)
        self.assertIn("aspect-ratio:16/9", css)
        self.assertIn(".learning-video-browser-screen iframe", css)


if __name__ == "__main__":
    unittest.main()

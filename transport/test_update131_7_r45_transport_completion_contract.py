from pathlib import Path

from django.test import SimpleTestCase


class R45TransportCompletionContractTests(SimpleTestCase):
    def test_driver_return_context_and_session_reassertion_exist(self):
        views = (Path(__file__).resolve().parent / "views.py").read_text(encoding="utf-8")
        self.assertIn('"management_return_user_id"', views)
        self.assertIn("request.session.modified = True", views)
        self.assertIn("TRANSPORT_DRIVER_IMPERSONATED_SESSION_KEY", views)

    def test_all_tracking_maps_have_real_viewport_fullscreen_rules(self):
        base = Path(__file__).resolve().parent / "templates" / "transport"
        for relative, wrapper in (
            ("driver/dashboard.html", "driver-map-wrap"),
            ("tracking/manager.html", "manager-map-wrap"),
            ("parent/dashboard.html", "parent-map-wrap"),
        ):
            text = (base / relative).read_text(encoding="utf-8")
            self.assertIn(f"#{wrapper}.opal-map-fullscreen", text)
            self.assertIn("height: 100vh !important", text)
            self.assertIn("height: 100% !important", text)
            self.assertIn("invalidateSize(true)", text)

    def test_stop_actions_are_backed_by_student_event_recording(self):
        services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
        self.assertIn("_record_stop_student_events", services)
        self.assertIn('event_type="arrived"', services)
        self.assertIn('event_type=("boarded" if stop.trip.direction == "morning" else "dropped_off")', services)

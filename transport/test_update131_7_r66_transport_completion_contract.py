from pathlib import Path


def test_r66_trip_payload_uses_assignment_and_stable_group_fallback():
    root = Path(__file__).resolve().parent
    views = (root / "views.py").read_text(encoding="utf-8")
    services = (root / "services.py").read_text(encoding="utf-8")
    assert "transport_registrations_for_trip" in views
    assert "Stable group membership" in services
    assert "planning_group_id__in=group_ids" in services


def test_r66_parent_tracking_finds_group_backed_active_trip():
    services = (Path(__file__).resolve().parent / "services.py").read_text(encoding="utf-8")
    section = services.split("def active_trip_for_parent", 1)[1].split("def transport_registrations_for_trip", 1)[0]
    assert "TransportGroupMember" in section
    assert "TransportTrip.ACTIVE" in section


def test_r66_return_trip_reports_children_still_on_bus():
    views = (Path(__file__).resolve().parent / "views.py").read_text(encoding="utf-8")
    assert '"on_bus": "داخل الحافلة"' in views
    assert 'remaining_students = [row for row in student_rows if row["status"] == "on_bus"' in views


def test_r66_parent_middleware_keeps_the_unified_transport_gateway():
    middleware = (Path(__file__).resolve().parents[1] / "parent_portal" / "middleware.py").read_text(encoding="utf-8")
    assert '"/transport/",' in middleware


def test_r66_explicit_role_entrypoints_exist():
    urls = (Path(__file__).resolve().parent / "urls.py").read_text(encoding="utf-8")
    assert 'name="driver-transport-dashboard"' in urls
    assert 'name="parent-transport-dashboard"' in urls

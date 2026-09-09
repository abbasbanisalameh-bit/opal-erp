from pathlib import Path


def test_parent_has_explicit_transport_route_and_portal_link():
    root = Path(__file__).resolve().parents[1]
    urls = (root / 'transport' / 'urls.py').read_text(encoding='utf-8')
    dashboard = (root / 'templates' / 'parent_portal' / 'dashboard.html').read_text(encoding='utf-8')
    assert 'parent-transport-dashboard' in urls
    assert 'parent-transport-dashboard' in dashboard


def test_driver_dashboard_receives_planned_or_active_map_trip():
    root = Path(__file__).resolve().parents[1]
    views = (root / 'transport' / 'views.py').read_text(encoding='utf-8')
    template = (root / 'transport' / 'templates' / 'transport' / 'driver' / 'dashboard.html').read_text(encoding='utf-8')
    assert 'map_trip = active_trip or' in views
    assert 'map_trip_payload' in views
    assert 'driver-trip-data' in template


def test_parent_dashboard_uses_canonical_transport_route():
    root = Path(__file__).resolve().parents[1]
    dashboard = (root / 'templates' / 'parent_portal' / 'dashboard.html').read_text(encoding='utf-8')
    assert 'href="/transport/parent/"' in dashboard


def test_driver_stop_bootstrap_has_planning_group_fallback():
    root = Path(__file__).resolve().parents[1]
    services = (root / 'transport' / 'services.py').read_text(encoding='utf-8')
    assert 'planning_group_id' in services
    assert 'TransportGroupMember.objects' in services

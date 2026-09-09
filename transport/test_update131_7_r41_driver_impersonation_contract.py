from pathlib import Path


def test_driver_impersonation_contract_source():
    root = Path(__file__).resolve().parents[1]
    views = (root / "transport" / "views.py").read_text(encoding="utf-8")
    urls = (root / "transport" / "urls.py").read_text(encoding="utf-8")
    template = (root / "transport" / "templates" / "transport" / "drivers" / "list.html").read_text(encoding="utf-8")
    base = (root / "templates" / "base" / "base.html").read_text(encoding="utf-8")

    assert "def driver_impersonate(" in views
    assert "def driver_impersonate_stop(" in views
    assert "@require_POST" in views
    assert "is_management_user(request.user)" in views
    assert "user__profile__school=school" in views
    assert "auth_login(request, driver.user" in views
    assert "opal_transport_driver_impersonator_user_id" in views
    assert 'name="driver-impersonate"' in urls
    assert 'name="driver-impersonate-stop"' in urls
    assert "دخول إلى حساب السائق" in template
    assert "driver-impersonate-stop" in base

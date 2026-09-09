from pathlib import Path


def test_r60_automatic_transport_command_and_ui_contract():
    root = Path(__file__).resolve().parent
    services = (root / "services.py").read_text()
    dashboard = (root / "templates/transport/dashboard.html").read_text()
    command = (root / "management/commands/auto_prepare_transport.py").read_text()

    assert "def synchronize_transport_operations" in services
    assert "التجهيز الجولات" not in dashboard
    assert "تجهيز جولات اليوم" not in dashboard
    assert "synchronize_transport_operations(" in command


def test_r60_no_registration_updated_at_dependency():
    services = (Path(__file__).resolve().parent / "services.py").read_text()
    assert "registration.updated_at" not in services

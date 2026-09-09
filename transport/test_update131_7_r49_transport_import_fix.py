from pathlib import Path

from django.test import SimpleTestCase


class R49TransportImportFixContractTests(SimpleTestCase):
    def test_trip_stop_bootstrap_uses_expected_models(self):
        text = (Path(__file__).resolve().parent / "services.py").read_text()

        marker = "def bootstrap_trip_stops_for_map(*, trip):"
        start = text.index(marker)
        end = text.index("\ndef driver_operational_trips", start)

        section = text[start:end]

        assert "from parent_portal.models import FamilyStudent" in section
        assert "from .models import TransportAssignment" in section
        assert "TransportFamilyLocation" in section
        assert "TransportTripStop" in section

        assert "trip.stops.exists()" in section
        assert 'trip.status not in ("planned", "active")' in section

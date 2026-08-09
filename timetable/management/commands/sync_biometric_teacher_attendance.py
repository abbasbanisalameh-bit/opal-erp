from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import School
from timetable.biometric_services import rebuild_daily_summaries


class Command(BaseCommand):
    help = "Rebuild teacher biometric daily summaries without auto-changing official attendance."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="day", default="")
        parser.add_argument("--school-id", type=int, default=None)
        parser.add_argument("--late-grace", type=int, default=10)
        parser.add_argument("--early-grace", type=int, default=10)

    def handle(self, *args, **options):
        raw = (options["day"] or timezone.localdate().isoformat()).strip()
        try:
            selected = date.fromisoformat(raw)
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD") from exc
        school = None
        if options["school_id"]:
            school = School.objects.filter(pk=options["school_id"]).first()
            if school is None:
                raise CommandError("School not found")
        rows = rebuild_daily_summaries(
            selected,
            school=school,
            late_grace_minutes=max(options["late_grace"], 0),
            early_grace_minutes=max(options["early_grace"], 0),
        )
        self.stdout.write(self.style.SUCCESS(f"Biometric summaries rebuilt: {len(rows)} for {selected}"))

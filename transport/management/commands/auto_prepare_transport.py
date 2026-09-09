from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import School
from transport.services import synchronize_transport_operations


class Command(BaseCommand):
    help = "Automatically synchronize transport rounds from stable groups and current subscriptions."

    def add_arguments(self, parser):
        parser.add_argument("--school-id", type=int, dest="school_id")

    def handle(self, *args, **options):
        school_id = options.get("school_id")
        schools = School.objects.filter(is_active=True).order_by("id")
        if school_id:
            schools = schools.filter(pk=school_id)

        total = {"created": 0, "updated": 0, "rebuilt": 0, "missing_locations": 0}
        for school in schools: 
            with transaction.atomic():
                result = synchronize_transport_operations(
                    school=school,
                    reason="تشغيل المواصلات التلقائي",
                )
            for key in total:
                total[key] += int(result.get(key, 0) or 0)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{school.name}: created={result.get('created', 0)} "
                    f"updated={result.get('updated', 0)} "
                    f"rebuilt={result.get('rebuilt', 0)}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"TOTAL: created={total['created']} updated={total['updated']} "
                f"rebuilt={total['rebuilt']} missing_locations={total['missing_locations']}"
            )
        )

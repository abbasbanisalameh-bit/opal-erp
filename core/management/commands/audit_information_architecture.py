from django.core.management.base import BaseCommand, CommandError

from core.information_architecture import GATEWAYS, COMPATIBILITY_ROUTE_GATEWAYS, audit_gateway_definitions


class Command(BaseCommand):
    help = "Read-only audit of OPAL canonical information gateways and compatibility routes."

    def handle(self, *args, **options):
        errors = audit_gateway_definitions()
        self.stdout.write(self.style.MIGRATE_HEADING("OPAL information architecture audit"))
        self.stdout.write(f"Canonical gateways: {len(GATEWAYS)}")
        self.stdout.write(f"Compatibility routes: {len(COMPATIBILITY_ROUTE_GATEWAYS)}")
        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))
            raise CommandError(f"Information architecture audit failed with {len(errors)} error(s).")
        self.stdout.write(self.style.SUCCESS("One canonical gateway per role/domain is structurally valid."))

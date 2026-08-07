from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Compatibility alias for the canonical readiness command.

    `verify_core_readiness` is the only engine that calculates production
    readiness.  This command remains only so historical deployment scripts do
    not break; it forwards every request to the canonical command without
    duplicating any checks or touching school data.
    """

    help = (
        "اسم متوافق تاريخيًا لفحص جاهزية OPAL ERP. "
        "ينفذ محرك verify_core_readiness الرسمي نفسه دون حسابات موازية."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            help="مسار اختياري لحفظ نسخة JSON من التقرير الرسمي.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="اعتبار التحذيرات مانعة للاعتماد.",
        )
        parser.add_argument(
            "--allow-empty",
            action="store_true",
            help="تحويل متطلبات التهيئة الأولية إلى تحذيرات لنسخة جديدة.",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="صيغة عرض التقرير.",
        )

    def handle(self, *args, **options):
        return call_command(
            "verify_core_readiness",
            allow_empty=bool(options.get("allow_empty")),
            strict_warnings=bool(options.get("strict")),
            format=options.get("format") or "text",
            output=options.get("output"),
            stdout=self.stdout,
            stderr=self.stderr,
        )

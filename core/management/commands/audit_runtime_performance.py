from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY, get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, reverse

from core.performance_audit import (
    DEFAULT_PERFORMANCE_ROUTES,
    compare_reports,
    median_number,
    release_version,
    summarize_queries,
)


class Command(BaseCommand):
    help = "قياس زمن الصفحات وعدد استعلامات قاعدة البيانات وإصدار تقرير قبل/بعد دون تعديل البيانات."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="اسم مستخدم إداري فعّال لإجراء الطلبات المقروءة.")
        parser.add_argument(
            "--route",
            dest="routes",
            action="append",
            help="اسم URL في Django مثل dashboard:home. يمكن تكراره.",
        )
        parser.add_argument(
            "--url",
            dest="urls",
            action="append",
            help="مسار داخلي مقروء يبدأ بشرطة مائلة. يمكن تكراره.",
        )
        parser.add_argument("--iterations", type=int, default=3, help="عدد مرات القياس لكل صفحة. الافتراضي 3.")
        parser.add_argument("--warmup", type=int, default=1, help="عدد طلبات التهيئة قبل القياس. الافتراضي 1.")
        parser.add_argument("--compare-to", help="ملف JSON سابق للمقارنة قبل/بعد.")
        parser.add_argument("--output", help="مسار JSON اختياري. يحفظ بجانبه تقرير Markdown.")
        parser.add_argument("--no-save", action="store_true", help="طباعة التقرير فقط دون حفظه.")
        parser.add_argument("--format", choices=["text", "json"], default="text")
        parser.add_argument("--fail-on-budget", action="store_true", help="إرجاع خطأ إذا تجاوزت صفحة ميزانية الاستعلامات أو أخفقت.")
        parser.add_argument("--list-routes", action="store_true", help="عرض الصفحات الافتراضية ثم الخروج.")

    def handle(self, *args, **options):
        if options["list_routes"]:
            for item in DEFAULT_PERFORMANCE_ROUTES:
                self.stdout.write(f"{item['route']}: {item['label']}")
            return

        iterations = options["iterations"]
        warmup = options["warmup"]
        if iterations < 1 or iterations > 20:
            raise CommandError("يجب أن يكون عدد مرات القياس بين 1 و20.")
        if warmup < 0 or warmup > 10:
            raise CommandError("يجب أن يكون عدد مرات التهيئة بين 0 و10.")

        user = self._resolve_user(options.get("username"))
        targets = self._build_targets(options.get("routes"), options.get("urls"))
        if not targets:
            raise CommandError("لم يتم تحديد أي صفحة للقياس.")

        report = {
            "schema": 1,
            "product": "OPAL ERP",
            "release": release_version(Path(settings.BASE_DIR)),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "database_vendor": connection.vendor,
            "username": user.get_username(),
            "iterations": iterations,
            "warmup": warmup,
            "read_only": True,
            "results": [],
        }

        allowed_hosts = list(getattr(settings, "ALLOWED_HOSTS", []) or [])
        if "testserver" not in allowed_hosts:
            allowed_hosts.append("testserver")
        with override_settings(
            ALLOWED_HOSTS=allowed_hosts,
            SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
        ):
            client = Client()
            self._authenticate_client_without_database_write(client, user)
            for target in targets:
                report["results"].append(
                    self._measure_target(client, target, iterations=iterations, warmup=warmup)
                )

        baseline_path = options.get("compare_to")
        if baseline_path:
            report["comparison"] = compare_reports(report, self._load_json(Path(baseline_path)))

        saved_paths = []
        if not options["no_save"]:
            json_path = Path(options["output"]).expanduser() if options.get("output") else self._default_output_path()
            saved_paths = self._save_report(report, json_path)

        if options["format"] == "json":
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self._print_text_report(report)
            for path in saved_paths:
                self.stdout.write(self.style.SUCCESS(f"تم حفظ التقرير: {path}"))

        failures = [row for row in report["results"] if row.get("status") in {"error", "over_budget"}]
        if failures and options["fail_on_budget"]:
            raise CommandError(f"فشل فحص الأداء في {len(failures)} صفحة. راجع التقرير المحفوظ.")

    def _resolve_user(self, username):
        user_model = get_user_model()
        queryset = user_model.objects.filter(is_active=True)
        if username:
            try:
                user = queryset.get(**{user_model.USERNAME_FIELD: username})
            except user_model.DoesNotExist as exc:
                raise CommandError("اسم المستخدم المحدد غير موجود أو غير فعّال.") from exc
        else:
            user = queryset.filter(is_superuser=True).order_by("pk").first()
            user = user or queryset.filter(is_staff=True).order_by("pk").first()
        if not user:
            raise CommandError("لا يوجد مستخدم إداري فعّال لإجراء الفحص.")
        if not (user.is_superuser or user.is_staff):
            raise CommandError("فحص الصفحات الإدارية يتطلب حسابًا إداريًا.")
        return user

    @staticmethod
    def _authenticate_client_without_database_write(client, user):
        """Attach a signed-cookie auth session without updating last_login."""
        session = client.session
        session[SESSION_KEY] = user._meta.pk.value_to_string(user)
        session[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
        session[HASH_SESSION_KEY] = user.get_session_auth_hash()
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def _build_targets(self, route_names, urls):
        catalog = {str(item["route"]): dict(item) for item in DEFAULT_PERFORMANCE_ROUTES}
        targets = []
        requested_routes = route_names or list(catalog)
        for route_name in requested_routes:
            item = dict(catalog.get(route_name, {
                "key": route_name.replace(":", "_"),
                "route": route_name,
                "label": route_name,
                "query_budget": 100,
                "response_budget_ms": 4000,
            }))
            try:
                item["url"] = reverse(route_name)
            except NoReverseMatch as exc:
                item["resolution_error"] = str(exc)
            targets.append(item)
        for index, url in enumerate(urls or [], start=1):
            if not str(url).startswith("/"):
                raise CommandError("المسار المخصص يجب أن يبدأ بشرطة مائلة (/).")
            targets.append({
                "key": f"custom_url_{index}",
                "route": "",
                "url": str(url),
                "label": str(url),
                "query_budget": 100,
                "response_budget_ms": 4000,
            })
        return targets

    def _measure_target(self, client, target, *, iterations, warmup):
        if target.get("resolution_error"):
            return {
                **target,
                "status": "error",
                "error": f"تعذر حل اسم المسار: {target['resolution_error']}",
                "samples": [],
            }
        url = target["url"]
        try:
            for _ in range(warmup):
                client.get(url, follow=False)
        except Exception as exc:  # pragma: no cover - reported safely in live environments
            return {**target, "status": "error", "error": f"فشل طلب التهيئة: {exc}", "samples": []}

        samples = []
        for _ in range(iterations):
            try:
                started = perf_counter()
                with CaptureQueriesContext(connection) as captured:
                    response = client.get(url, follow=False)
                    if not getattr(response, "streaming", False):
                        _ = response.content
                elapsed_ms = (perf_counter() - started) * 1000
                query_summary = summarize_queries(captured.captured_queries)
                content_size = 0
                if not getattr(response, "streaming", False):
                    content_size = len(response.content)
                samples.append({
                    "status_code": response.status_code,
                    "response_ms": round(elapsed_ms, 3),
                    "response_bytes": content_size,
                    **query_summary,
                })
            except Exception as exc:  # pragma: no cover - surfaced in report
                samples.append({"error": str(exc)})

        valid = [sample for sample in samples if "error" not in sample]
        if not valid:
            return {**target, "status": "error", "error": samples[-1].get("error", "فشل غير معروف"), "samples": samples}

        representative = min(valid, key=lambda sample: abs(sample["response_ms"] - median([row["response_ms"] for row in valid])))
        status_codes = sorted({sample["status_code"] for sample in valid})
        median_queries = median_number([sample["query_count"] for sample in valid])
        median_response = median_number([sample["response_ms"] for sample in valid])
        median_db = median_number([sample["db_time_ms"] for sample in valid])
        query_over = median_queries > float(target["query_budget"])
        response_over = median_response > float(target["response_budget_ms"])
        http_error = any(code < 200 or code >= 300 for code in status_codes)
        status = "error" if http_error else ("over_budget" if query_over or response_over else "ok")
        return {
            **target,
            "status": status,
            "status_codes": status_codes,
            "median_response_ms": median_response,
            "min_response_ms": round(min(sample["response_ms"] for sample in valid), 3),
            "max_response_ms": round(max(sample["response_ms"] for sample in valid), 3),
            "median_db_time_ms": median_db,
            "median_query_count": median_queries,
            "median_response_bytes": median_number([sample["response_bytes"] for sample in valid]),
            "query_budget_exceeded": query_over,
            "response_budget_exceeded": response_over,
            "duplicate_query_count": representative["duplicate_query_count"],
            "duplicate_groups": representative["duplicate_groups"],
            "slow_queries": representative["slow_queries"],
            "n_plus_one_suspected": representative["n_plus_one_suspected"],
            "samples": samples,
        }

    def _default_output_path(self):
        try:
            from core.update_engine_runtime import private_storage_root

            directory = private_storage_root() / "performance_audits"
        except Exception:
            directory = Path(settings.BASE_DIR).parent / "opal_private_backups" / "performance_audits"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return directory / f"opal_performance_{stamp}.json"

    def _save_report(self, report, json_path):
        json_path = json_path.resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path = json_path.with_suffix(".md")
        markdown_path.write_text(self._markdown_report(report), encoding="utf-8")
        try:
            json_path.chmod(0o600)
            markdown_path.chmod(0o600)
        except OSError:
            pass
        return [json_path, markdown_path]

    @staticmethod
    def _load_json(path):
        try:
            return json.loads(path.expanduser().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"تعذر قراءة تقرير المقارنة: {path}") from exc

    def _print_text_report(self, report):
        self.stdout.write(self.style.MIGRATE_HEADING(f"OPAL Performance Audit — الإصدار {report['release']}"))
        for row in report["results"]:
            if row["status"] == "error":
                self.stdout.write(self.style.ERROR(f"✗ {row['label']}: {row.get('error', row.get('status_codes'))}"))
                continue
            style = self.style.SUCCESS if row["status"] == "ok" else self.style.WARNING
            self.stdout.write(style(
                f"• {row['label']}: {row['median_response_ms']} ms | "
                f"{row['median_query_count']} استعلام | DB {row['median_db_time_ms']} ms | "
                f"الحالة {row['status']}"
            ))
        if report.get("comparison"):
            self.stdout.write(self.style.MIGRATE_LABEL("المقارنة قبل/بعد:"))
            for row in report["comparison"]:
                self.stdout.write(
                    f"  {row['label']}: الزمن {row['response_ms_delta']:+.1f} ms، "
                    f"الاستعلامات {row['queries_delta']:+.0f}"
                )

    @staticmethod
    def _markdown_report(report):
        lines = [
            f"# تقرير أداء OPAL ERP — الإصدار {report['release']}",
            "",
            f"- تاريخ القياس: `{report['generated_at']}`",
            f"- قاعدة البيانات: `{report['database_vendor']}`",
            f"- عدد مرات القياس: `{report['iterations']}` بعد `{report['warmup']}` طلب تهيئة",
            "- الفحص للقراءة فقط ولا يعدّل بيانات المدرسة.",
            "",
            "| الصفحة | الحالة | الزمن الوسيط ms | الاستعلامات | زمن DB ms | التكرار |",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for row in report["results"]:
            if row["status"] == "error":
                lines.append(f"| {row['label']} | خطأ | - | - | - | - |")
            else:
                lines.append(
                    f"| {row['label']} | {row['status']} | {row['median_response_ms']} | "
                    f"{row['median_query_count']} | {row['median_db_time_ms']} | {row['duplicate_query_count']} |"
                )
        if report.get("comparison"):
            lines.extend([
                "",
                "## المقارنة قبل/بعد",
                "",
                "| الصفحة | فرق الزمن ms | فرق الاستعلامات |",
                "|---|---:|---:|",
            ])
            for row in report["comparison"]:
                lines.append(f"| {row['label']} | {row['response_ms_delta']:+.1f} | {row['queries_delta']:+.0f} |")
        return "\n".join(lines) + "\n"

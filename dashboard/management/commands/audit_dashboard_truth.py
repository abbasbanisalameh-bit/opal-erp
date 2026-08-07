from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from academics.models import Enrollment, Section
from accounting.models import StudentInvoice, StudentPayment
from announcements.models import Announcement
from attendance_v2.analytics import VALID_REGISTER_Q, build_school_attendance_period_snapshot
from attendance_v2.models import Attendance, AttendanceRegister
from core.models import AcademicYear, School
from enterprise_ops.models import BroadcastMessage, FeedbackTicket, MonthlyServiceEvaluation
from enterprise_ops.services import feedback_satisfaction_snapshot
from exams.analytics import top_students_by_grade
from exams.models import StudentMark
from parent_portal.evaluation_services import monthly_teacher_evaluation_snapshot
from parent_portal.models import TeacherMonthlyEvaluation
from teachers.models import Teacher
from timetable.live_services import management_live_status
from timetable.models import TeacherAbsence

from dashboard.workflow import OFFICIAL_EXAM_STATUSES, build_dashboard_context


MONEY_QUANTUM = Decimal("0.01")


def _money(value):
    return (value or Decimal("0.00")).quantize(MONEY_QUANTUM)


def _teacher_ranking_signature(snapshot):
    return [
        (
            row["teacher"].pk,
            round(float(row["adjusted_average"]), 2),
            int(row["responses"]),
        )
        for row in snapshot.get("top_teacher_evaluations", [])
    ]


def _live_matrix_signature(live):
    return [
        (
            column["grade"].pk,
            tuple(
                (
                    item["section"].pk,
                    item["label"],
                    item.get("meta", ""),
                    item.get("state_code", ""),
                    item.get("subject_color", ""),
                )
                for item in column.get("sections", [])
            ),
        )
        for column in live.get("grade_columns", [])
    ]


class Command(BaseCommand):
    help = (
        "يدقق أن كل قيمة ظاهرة في لوحة المدير مشتقة من سجلات المدرسة والعام "
        "الحالي، وأن حالة عدم توفر البيانات لا تتحول إلى رقم مصطنع."
    )

    def add_arguments(self, parser):
        parser.add_argument("--school-id", type=int, help="معرف المدرسة؛ الافتراضي أول مدرسة نشطة.")
        parser.add_argument("--json", action="store_true", help="إخراج التقرير بصيغة JSON.")

    def handle(self, *args, **options):
        school = (
            School.objects.filter(pk=options.get("school_id")).first()
            if options.get("school_id")
            else School.objects.filter(is_active=True).order_by("pk").first()
        )
        if school is None:
            raise CommandError("لا توجد مدرسة نشطة لتدقيق لوحة المدير.")
        year = (
            AcademicYear.objects.filter(school=school, is_current=True)
            .order_by("-start_date", "-pk")
            .first()
        )
        if year is None:
            raise CommandError(f"لا يوجد عام دراسي حالي للمدرسة: {school}.")

        snapshot = build_dashboard_context(school=school, academic_year=year)
        checks = []

        def check(code, expected, actual, source, note=""):
            ok = expected == actual
            checks.append({
                "code": code,
                "ok": ok,
                "expected": str(expected),
                "actual": str(actual),
                "source": source,
                "note": note,
            })

        # 1) بطاقات المؤشرات الأساسية: الطالب/المعلم/الشعبة.
        enrollment_qs = Enrollment.objects.filter(academic_year=year)
        student_stats = enrollment_qs.aggregate(
            total=Count("student_id", distinct=True),
            active=Count(
                "student_id",
                distinct=True,
                filter=Q(status="active", student__is_active=True),
            ),
        )
        check("students_total", student_stats["total"] or 0, snapshot["students_count"], "academics.Enrollment / current year")
        check("students_active", student_stats["active"] or 0, snapshot["active_students"], "Enrollment + Student.is_active")
        check("teachers_active", Teacher.objects.filter(school=school, is_active=True).count(), snapshot["teachers_count"], "teachers.Teacher")
        check("sections_active", Section.objects.filter(academic_year=year, is_active=True).count(), snapshot["sections_count"], "academics.Section")

        # 2) الحضور اليومي وملخص الثلاثين يومًا من السجلات المعتمدة فقط.
        today = timezone.localdate()
        period_start = today - timedelta(days=29)
        attendance = build_school_attendance_period_snapshot(
            period_start,
            today,
            school=school,
            academic_year=year,
        )
        today_attendance = attendance["days"][today]
        for key, dashboard_key in (
            ("has_data", "attendance_data_available"),
            ("present", "present_today"),
            ("absent", "absent_today"),
            ("departed", "departed_today"),
            ("roster_total", "attendance_total_today"),
            ("percent", "attendance_percent"),
            ("submitted_sections", "attendance_submitted_sections"),
            ("pending_sections", "attendance_pending_sections"),
            ("unregistered_exceptions", "attendance_unregistered_exceptions"),
        ):
            check(f"attendance_today_{key}", today_attendance[key], snapshot[dashboard_key], "attendance_v2 canonical analytics")
        check("attendance_period_available", attendance["totals"]["has_data"], snapshot["attendance_period_data_available"], "valid AttendanceRegister rows")
        check("attendance_period_absences", attendance["totals"]["absent"], snapshot["period_absences"], "attendance_v2.Attendance")
        check("attendance_period_departures", attendance["totals"]["departed"], snapshot["period_departures"], "attendance_v2.Attendance")
        register_count = AttendanceRegister.objects.filter(
            academic_year=year,
            date=today,
        ).filter(VALID_REGISTER_Q).count()
        check("attendance_submitted_sections_direct", register_count, snapshot["attendance_submitted_sections"], "submitted/locked/closed AttendanceRegister")
        direct_absent_ids = set(
            Attendance.objects.filter(
                academic_year=year,
                date=today,
                status="absent",
                student_id__in=today_attendance["absent_student_ids"],
            ).values_list("student_id", flat=True)
        )
        shown_absent_ids = {row.student_id for row in snapshot["absent_students_today"]}
        check("absent_students_list", direct_absent_ids, shown_absent_ids, "registered student absence rows")

        # 3) الرسوم والتحصيل: صافي الفواتير والدفعات المرحلة والمتبقي الحقيقي.
        invoices = list(
            StudentInvoice.objects.filter(academic_year=year)
            .exclude(status="cancelled")
            .prefetch_related("payments")
        )
        total_fees = sum((invoice.net_amount for invoice in invoices), Decimal("0.00"))
        paid = sum((invoice.total_paid for invoice in invoices), Decimal("0.00"))
        remaining = sum((invoice.remaining for invoice in invoices), Decimal("0.00"))
        overdue = sum(1 for invoice in invoices if invoice.remaining > 0 and invoice.due_date < today)
        paid_invoices = sum(1 for invoice in invoices if invoice.remaining <= 0)
        unpaid_invoices = sum(1 for invoice in invoices if invoice.remaining > 0)
        collection_rate = round((min(paid, total_fees) / total_fees) * 100, 1) if total_fees > 0 else 0
        for code, expected, actual, source in (
            ("finance_available", bool(invoices), snapshot["finance_data_available"], "current-year non-cancelled invoices"),
            ("finance_total", _money(total_fees), _money(snapshot["total_invoices"]), "StudentInvoice.net_amount"),
            ("finance_paid", _money(paid), _money(snapshot["paid_amount"]), "posted StudentPayment rows"),
            ("finance_remaining", _money(remaining), _money(snapshot["outstanding"]), "StudentInvoice.remaining"),
            ("finance_collection_rate", collection_rate, snapshot["collection_rate"], "paid / net fees"),
            ("finance_overdue", overdue, snapshot["overdue_invoices"], "remaining > 0 and due_date < today"),
            ("finance_paid_invoice_count", paid_invoices, snapshot["paid_invoices"], "fully paid invoices"),
            ("finance_unpaid_invoice_count", unpaid_invoices, snapshot["unpaid_invoices"], "invoices with remaining balance"),
        ):
            check(code, expected, actual, source)

        direct_monthly = list(
            StudentPayment.objects.filter(
                status="posted",
                invoice__academic_year=year,
            )
            .exclude(invoice__status="cancelled")
            .annotate(month=TruncMonth("payment_date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        direct_monthly_labels = [row["month"].strftime("%Y-%m") for row in direct_monthly if row["month"]]
        direct_monthly_values = [_money(row["total"]) for row in direct_monthly if row["month"]]
        shown_monthly_values = [_money(Decimal(str(value))) for value in snapshot["monthly_income_values"]]
        check("monthly_income_labels", direct_monthly_labels, snapshot["monthly_income_labels"], "posted payments grouped by payment month")
        check("monthly_income_values", direct_monthly_values, shown_monthly_values, "posted payments grouped by payment month")

        cutoff = snapshot["recent_payment_cutoff"]
        shown_watch = snapshot["no_recent_payment_students"]
        shown_watch_ids = [row["student"].pk for row in shown_watch]
        candidate_ids = {
            invoice.student_id
            for invoice in invoices
            if invoice.remaining > 0 and invoice.due_date <= cutoff
        }
        recent_payment_ids = set(
            StudentPayment.objects.filter(
                status="posted",
                invoice__academic_year=year,
                invoice__student_id__in=candidate_ids,
                payment_date__gte=cutoff,
            )
            .exclude(invoice__status="cancelled")
            .values_list("invoice__student_id", flat=True)
        )
        active_enrollment_ids = set(
            Enrollment.objects.filter(
                academic_year=year,
                status="active",
                student__is_active=True,
                student_id__in=candidate_ids,
            ).values_list("student_id", flat=True)
        )
        expected_watch_ids = (candidate_ids - recent_payment_ids) & active_enrollment_ids
        shown_watch_valid = set(shown_watch_ids).issubset(expected_watch_ids) and len(shown_watch_ids) == len(set(shown_watch_ids))
        check("no_recent_payment_watch_rows", True, shown_watch_valid, "old outstanding invoices without a recent posted payment")
        check("no_recent_payment_watch_count", len(expected_watch_ids), snapshot["no_recent_payment_total"], "exact qualifying student total")

        # 4) النتائج الأكاديمية الرسمية فقط.
        marks_qs = StudentMark.objects.filter(
            exam__academic_year=year,
            exam__status__in=OFFICIAL_EXAM_STATUSES,
            exam__is_active=True,
        )
        marks = list(marks_qs.values_list("mark", "exam__max_mark", "exam__pass_percentage"))
        percentages = []
        passed = 0
        for mark, max_mark, pass_percentage in marks:
            maximum = Decimal(max_mark or 0)
            percentage = (Decimal(mark or 0) * Decimal("100") / maximum) if maximum else Decimal("0")
            percentages.append(percentage)
            if percentage >= Decimal(pass_percentage or 0):
                passed += 1
        direct_average = (
            (sum(percentages, Decimal("0")) / len(percentages)).quantize(MONEY_QUANTUM)
            if percentages else Decimal("0.00")
        )
        direct_pass_rate = round((passed / len(percentages)) * 100, 1) if percentages else 0
        check("academic_available", bool(marks), snapshot["academic_data_available"], "official active exams")
        check("official_marks", len(marks), snapshot["marks_count"], "exams.StudentMark / official exams")
        check("academic_average", direct_average, snapshot["academic_average"], "normalized official marks")
        check("academic_pass_rate", direct_pass_rate, snapshot["pass_rate"], "official marks meeting exam pass percentage")

        rankings = top_students_by_grade(academic_year=year)
        dashboard_grade_ids = {group["grade"].pk for group in snapshot["top_students_matrix"]}
        expected_leaders = [
            (
                group["grade"].pk,
                tuple((row["student"].pk, row["rank"], str(row["average"])) for row in group["students"] if row["rank"] == 1),
            )
            for group in rankings
            if group["grade"].pk in dashboard_grade_ids
        ]
        shown_leaders = [
            (
                group["grade"].pk,
                tuple((row["student"].pk, row["rank"], str(row["average"])) for row in group["leaders"]),
            )
            for group in snapshot["top_students_matrix"]
            if group["leaders"]
        ]
        expected_leaders = [row for row in expected_leaders if row[1]]
        check("top_students", expected_leaders, shown_leaders, "official normalized exam rankings")

        # 5) رضا المستخدمين: المشاركة مرة واحدة والتوزيعات من حقول التقييم الفعلية.
        satisfaction = feedback_satisfaction_snapshot(today=today, school=school)
        satisfaction_keys = (
            "feedback_data_available",
            "teaching_data_available",
            "electronic_data_available",
            "feedback_total",
            "feedback_rating_observations",
            "feedback_recent_total",
            "teaching_rating_average",
            "electronic_rating_average",
            "overall_rating_average",
            "teaching_satisfaction_percent",
            "electronic_satisfaction_percent",
            "overall_satisfaction_percent",
            "teaching_positive_percent",
            "electronic_positive_percent",
            "both_positive_percent",
            "both_positive_total",
            "paired_feedback_total",
            "teaching_rating_distribution",
            "electronic_rating_distribution",
            "feedback_teacher_responses",
            "feedback_parent_responses",
            "feedback_recent_overall_average",
            "feedback_trend_available",
            "feedback_trend_delta",
            "feedback_trend_abs",
        )
        for key in satisfaction_keys:
            check(f"satisfaction_{key}", satisfaction[key], snapshot[key], "MonthlyServiceEvaluation canonical aggregate")
        eval_scope = MonthlyServiceEvaluation.objects.filter(
            Q(school=school)
            | Q(school__isnull=True, user__profile__school=school)
            | Q(school__isnull=True, user__teacher_profile__school=school)
            | Q(school__isnull=True, user__family_account__school=school)
        ).filter(
            Q(teaching_quality_rating__isnull=False)
            | Q(electronic_services_rating__isnull=False)
        ).distinct()
        check("satisfaction_participations_direct", eval_scope.count(), snapshot["feedback_total"], "one MonthlyServiceEvaluation row = one participation")

        # 6) تقييم المعلمين: الشهر الحالي والمدرسة الحالية فقط.
        teacher_evaluations = monthly_teacher_evaluation_snapshot(today=today, school=school)
        for key in (
            "teacher_evaluation_period",
            "teacher_evaluation_total",
            "teacher_evaluation_average",
            "teacher_evaluation_chart_labels",
            "teacher_evaluation_chart_values",
        ):
            check(f"teacher_{key}", teacher_evaluations[key], snapshot[key], "TeacherMonthlyEvaluation canonical aggregate")
        check("teacher_top_ranking", _teacher_ranking_signature(teacher_evaluations), _teacher_ranking_signature(snapshot), "Bayesian-adjusted teacher ranking")
        direct_teacher_eval_count = TeacherMonthlyEvaluation.objects.filter(
            period=today.replace(day=1),
            teacher__school=school,
            teacher__is_active=True,
        ).count()
        check("teacher_evaluation_rows_direct", direct_teacher_eval_count, snapshot["teacher_evaluation_total"], "current-month teacher evaluation rows")

        # 7) الشكاوى والتعاميم والإعلانات.
        feedback_scope = FeedbackTicket.objects.filter(
            Q(school=school)
            | Q(school__isnull=True, sender__profile__school=school)
            | Q(school__isnull=True, sender__teacher_profile__school=school)
            | Q(school__isnull=True, sender__family_account__school=school)
        ).distinct()
        check("feedback_new", feedback_scope.filter(status="new").count(), snapshot["new_feedback_count"], "FeedbackTicket / school scope")
        check("feedback_review", feedback_scope.filter(status="review").count(), snapshot["review_feedback_count"], "FeedbackTicket / school scope")
        check("broadcasts_active", BroadcastMessage.objects.filter(is_active=True).count(), snapshot["active_broadcasts"], "system-wide BroadcastMessage")
        check("announcements_active", Announcement.objects.filter(is_active=True).count(), snapshot["active_announcements"], "system-wide Announcement")

        # 8) غياب المعلمين وقوائم الحصص الجارية والمتفرغين والأحداث الصفية.
        direct_teacher_absence_ids = set(
            TeacherAbsence.objects.filter(
                date=today,
                attendance_status="absent",
                teacher__school=school,
                teacher__is_active=True,
            ).values_list("teacher_id", flat=True)
        )
        shown_teacher_absence_ids = {row.teacher_id for row in snapshot["absent_teachers_today"]}
        check("teacher_absences", direct_teacher_absence_ids, shown_teacher_absence_ids, "timetable.TeacherAbsence")

        live = management_live_status(school)
        shown_live = snapshot["opal_live_schedule"]
        for key in ("teacher_state_active", "busy_teachers", "free_teachers_count"):
            check(f"live_{key}", live[key], shown_live[key], "current timetable + teacher exceptions")
        check("live_busy_teacher_ids", set(live.get("busy_teacher_ids", set())), {row["teacher"].pk for row in shown_live.get("busy_rows", [])}, "effective current teachers")
        check("live_free_teacher_ids", {teacher.pk for teacher in live.get("free_teachers", [])}, {teacher.pk for teacher in shown_live.get("free_teachers", [])}, "active teachers minus busy/unavailable")
        check("live_grade_event_matrix", _live_matrix_signature(live), _live_matrix_signature(shown_live), "current grade/section timetable events")

        # 9) آخر عشرة طلاب: قبول فعلي نشط في العام الحالي، لا أسماء تجريبية ثابتة.
        direct_latest = list(
            Enrollment.objects.filter(
                academic_year=year,
                status="active",
                student__is_active=True,
            )
            .select_related("student", "grade", "section")
            .order_by("-joined_at", "-pk")[:10]
        )
        direct_latest_signature = [
            (row.student_id, row.grade_id, row.section_id, str(row.joined_at))
            for row in direct_latest
        ]
        shown_latest_signature = [
            (row["student"].pk, row["grade"].pk, row["section"].pk if row["section"] else None, str(row["joined_at"]))
            for row in snapshot["latest_students"]
        ]
        check("latest_students", direct_latest_signature, shown_latest_signature, "latest active current-year Enrollment rows")

        report = {
            "school": str(school),
            "school_id": school.pk,
            "academic_year": str(year),
            "academic_year_id": year.pk,
            "checked_at": timezone.localtime().isoformat(),
            "ok": all(item["ok"] for item in checks),
            "checks_total": len(checks),
            "checks_passed": sum(1 for item in checks if item["ok"]),
            "checks_failed": sum(1 for item in checks if not item["ok"]),
            "checks": checks,
            "notes": [
                "الحضور يعرض عدم توفر البيانات بدل صفر إذا لم توجد سجلات شعب معتمدة.",
                "الرضا يحسب كل مشاركة مرة واحدة، بينما التوزيع يحسب مشاهدات كل حقل تقييم.",
                "قائمة عدم السداد تشترط متبقيًا مستحقًا منذ 30 يومًا وعدم وجود دفعة مرحلة حديثة.",
                "التعاميم والإعلانات موصوفة بأنها على مستوى النظام لأن النموذجين الحاليين لا يحتويان حقل مدرسة.",
                "الأمر لا يغيّر أي سجل؛ هو تدقيق قراءة فقط ويخرج بفشل عند أول اختلاف منطقي في اللوحة.",
            ],
        }
        if options.get("json"):
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING(f"تدقيق حقيقة لوحة المدير: {school} — {year}"))
            for item in checks:
                marker = self.style.SUCCESS("PASS") if item["ok"] else self.style.ERROR("FAIL")
                self.stdout.write(f"[{marker}] {item['code']}: {item['actual']} — {item['source']}")

        if not report["ok"]:
            raise CommandError(
                f"فشل {report['checks_failed']} من {report['checks_total']} تدقيقًا في لوحة المدير."
            )
        if not options.get("json"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"نجحت جميع تدقيقات لوحة المدير ({report['checks_passed']}/{report['checks_total']})."
                )
            )

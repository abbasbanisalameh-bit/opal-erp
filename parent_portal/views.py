from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponse
import csv

from .models import Family, FamilyStudent, TeacherMonthlyEvaluation
from .services import ensure_family_account, reset_family_password
from .services import update_family_identity
from .receipt_services import build_guardian_receipt_history
from .financial_services import build_guardian_annual_statement, guardian_financial_years
from .forms import FamilyIdentityForm, ParentFamilyPersonalForm, ParentPhotoForm, ParentStudentPersonalForm
from .permissions import parent_required
from accounting.models import StudentInvoice
from attendance_v2.models import Attendance
from announcements.models import Announcement
from exams.models import StudentMark
from exams.services import student_marks_matrix
from accounts.models import UserProfile
from .academic_services import current_enrollment, homework_for_student, homework_rows_for_students, student_class_rank
from .parent360 import build_parent360_context
from .workflow import (
    build_dashboard_context,
    build_family_finance_context,
    build_fees_context,
    build_student_card,
    build_student_detail_context,
    family_for_user,
    student_for_user_or_403,
    students_for_user,
)
from admissions.models import FeePaymentAllocation, FeePayment
from enterprise_ops.permissions import management_required
from enterprise_ops.services import audit
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.exceptions import ValidationError
from .duplicate_services import guardian_duplicate_groups, merge_guardian_group
from timetable.live_services import student_live_status
from .financial_access import guardian_feature_allowed
from .evaluation_services import teachers_for_family_students

try:
    from documents.models import StudentIssuedDocument
except Exception:  # keeps portal safe if documents app changes later
    StudentIssuedDocument = None


def _students_for_user(user):
    return students_for_user(user)


def _normalized_students_for_user(user):
    return students_for_user(user)


def _family_for_user(user):
    return family_for_user(user)


def _student_or_403(user, student_id):
    return student_for_user_or_403(user, student_id)


def _student_card(student):
    return build_student_card(student)


@parent_required
def dashboard(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")

    return render(request, "parent_portal/dashboard.html", build_dashboard_context(request.user))


@parent_required
def parent_360(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    family = _family_for_user(request.user)
    if family is None:
        return render(request, "parent_portal/no_profile.html")
    context = build_parent360_context(family, students)
    return render(request, "parent_portal/parent_360.html", context)


@parent_required
def children(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    marks_allowed = guardian_feature_allowed(_family_for_user(request.user), "marks")
    return render(request, "parent_portal/children.html", {"cards": [build_student_card(s, marks_allowed=marks_allowed) for s in students]})


@parent_required
def student_detail(request, student_id):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    student = _student_or_403(request.user, student_id)
    context = build_student_detail_context(student)
    family = _family_for_user(request.user)
    if not guardian_feature_allowed(family, "marks"):
        context["marks"] = []
        context["financial_restriction"] = "النتائج محجوبة وفق السياسة المالية المحددة لهذا الحساب."
    if not guardian_feature_allowed(family, "documents"):
        context["documents"] = []
    return render(request, "parent_portal/student_detail.html", context)


@parent_required
def fees(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    return render(request, "parent_portal/fees.html", build_fees_context(request.user, request.GET.get("year")))


@parent_required
def attendance(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    student_id = request.GET.get("student", "")
    date = request.GET.get("date", "")
    selected_student = _student_or_403(request.user, student_id) if student_id else None
    records = Attendance.objects.filter(student=selected_student) if selected_student else Attendance.objects.filter(student__in=students)
    if date:
        records = records.filter(date=date)
    records = records.select_related("student").order_by("-date")[:120]
    return render(request, "parent_portal/attendance.html", {
        "records": records, "students": students, "selected_student": selected_student,
        "student_id": student_id, "date": date,
    })


@parent_required
def marks(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    if not guardian_feature_allowed(_family_for_user(request.user), "marks"):
        return render(request, "parent_portal/financial_restriction.html", {"feature": "النتائج والشهادات"})
    student_id = request.GET.get("student", "")
    subject_id = request.GET.get("subject", "")
    exam_key = request.GET.get("exam", "")
    selected_student = _student_or_403(request.user, student_id) if student_id else None
    matrix = student_marks_matrix(selected_student) if selected_student else None
    selected_subject = None
    subject_rows = []
    selected_exam = None
    exam_rows = []
    if matrix:
        if subject_id:
            selected_subject = next((row["subject"] for row in matrix["by_subject"] if str(row["subject"].pk) == subject_id), None)
            subject_rows = [row for row in matrix["by_subject"] if selected_subject and row["subject"].pk == selected_subject.pk]
        if exam_key:
            try:
                semester_id, exam_type = exam_key.split(":", 1)
            except ValueError:
                semester_id = exam_type = ""
            selected_exam = next((row for row in matrix["by_exam"] if str(row["semester"].pk) == semester_id and row["exam_type"]["key"] == exam_type), None)
            exam_rows = selected_exam["rows"] if selected_exam else []
    return render(request, "parent_portal/marks.html", {
        "students": students, "selected_student": selected_student, "student_id": student_id,
        "matrix": matrix, "subject_id": subject_id, "exam_key": exam_key,
        "selected_subject": selected_subject, "subject_rows": subject_rows,
        "selected_exam": selected_exam, "exam_rows": exam_rows,
    })


@parent_required
def homework(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    if not guardian_feature_allowed(_family_for_user(request.user), "homework"):
        return render(request, "parent_portal/financial_restriction.html", {"feature": "الخدمات غير الأساسية"})
    student_id = request.GET.get("student", "")
    subject_id = request.GET.get("subject", "")
    selected_student = _student_or_403(request.user, student_id) if student_id else None
    items = []
    subjects = []
    if selected_student:
        enrollment = current_enrollment(selected_student)
        if enrollment and enrollment.section_id:
            from academics.models import Subject
            subjects = Subject.objects.filter(
                teacherassignment__academic_year=enrollment.academic_year,
                teacherassignment__section=enrollment.section,
                teacherassignment__is_active=True,
            ).distinct().order_by("name")
        items = homework_for_student(selected_student)
        if subject_id:
            items = items.filter(assignment__subject_id=subject_id)
    return render(request, "parent_portal/homework.html", {
        "students": students, "selected_student": selected_student, "student_id": student_id,
        "subject_id": subject_id, "subjects": subjects, "items": items,
    })


@parent_required
def teacher_evaluations(request):
    students = _normalized_students_for_user(request.user)
    family = _family_for_user(request.user)
    if not students or family is None:
        return render(request, "parent_portal/no_profile.html")
    today = timezone.localdate()
    period = today.replace(day=1)
    rows = teachers_for_family_students(students)
    evaluations = {
        item.teacher_id: item
        for item in TeacherMonthlyEvaluation.objects.filter(
            family=family, period=period, teacher_id__in=[row["teacher"].pk for row in rows]
        )
    }
    for row in rows:
        row["evaluation"] = evaluations.get(row["teacher"].pk)
    return render(request, "parent_portal/teacher_evaluations.html", {
        "rows": rows,
        "period": period,
    })


@require_POST
@parent_required
def submit_monthly_teacher_evaluations(request):
    """Compatibility URL routed into the single central monthly workflow."""
    from enterprise_ops.views import submit_monthly_evaluations

    return submit_monthly_evaluations(request)


@parent_required
def student_personal_update(request, student_id):
    student = _student_or_403(request.user, student_id)
    form = ParentStudentPersonalForm(request.POST or None, request.FILES or None, instance=student)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "تم تحديث الصورة والمعلومات الشخصية المسموح بها للطالب.")
        return redirect("parent_portal:student_detail", student_id=student.pk)
    return render(request, "parent_portal/student_personal_form.html", {"student": student, "form": form})


@parent_required
def timetable(request):
    if not guardian_feature_allowed(_family_for_user(request.user), "timetable"):
        return render(request, "parent_portal/financial_restriction.html", {"feature": "الخدمات غير الأساسية"})
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    from academics.models import Enrollment, Subject
    from timetable.models import TimetableEntry

    student_id = request.GET.get("student", "")
    day = request.GET.get("day", "")
    subject_id = request.GET.get("subject", "")
    selected_students = students
    if student_id:
        selected_students = [student for student in students if str(student.pk) == student_id]

    enrollments = Enrollment.objects.filter(
        student__in=selected_students, status="active"
    ).select_related("student", "section", "section__grade", "academic_year")
    rows = []
    all_matrix_entries = []
    all_enrollments = Enrollment.objects.filter(student__in=students, status="active")
    all_entry_scope = TimetableEntry.objects.filter(
        section_id__in=all_enrollments.values_list("section_id", flat=True),
        academic_year_id__in=all_enrollments.values_list("academic_year_id", flat=True),
        is_active=True,
    ).distinct()
    for enrollment in enrollments:
        entries = TimetableEntry.objects.filter(
            section=enrollment.section,
            academic_year=enrollment.academic_year,
            is_active=True,
        ).select_related("subject", "teacher", "time_slot", "section__grade")
        if day:
            entries = entries.filter(day=day)
        if subject_id:
            entries = entries.filter(subject_id=subject_id)
        entry_list = list(entries)
        all_matrix_entries.extend(entry_list)
        rows.append({"student": enrollment.student, "enrollment": enrollment, "entries": entry_list})

    from timetable.workflow import build_horizontal_schedule_matrix
    matrix_school = enrollments.first().academic_year.school if enrollments.exists() else None
    shared_matrix = build_horizontal_schedule_matrix(all_matrix_entries, selected_day=day, school=matrix_school)
    for row in rows:
        row["schedule_matrix"] = build_horizontal_schedule_matrix(
            row["entries"], selected_day=day, periods=shared_matrix["periods"], school=row["enrollment"].academic_year.school
        )

    subjects = Subject.objects.filter(timetableentry__in=all_entry_scope).select_related("grade").distinct().order_by("grade__order", "name")
    audit(request, "view", "parent_portal.Timetable", description="عرض جدول الأبناء")
    return render(request, "parent_portal/timetable.html", {
        "rows": rows,
        "students": students,
        "subjects": subjects,
        "days": TimetableEntry.DAYS,
        "filters": {"student": student_id, "day": day, "subject": subject_id},
    })

@parent_required
def documents(request):
    students = _normalized_students_for_user(request.user)
    if not students:
        return render(request, "parent_portal/no_profile.html")
    if not guardian_feature_allowed(_family_for_user(request.user), "documents"):
        return render(request, "parent_portal/financial_restriction.html", {"feature": "الوثائق والشهادات"})
    records = []
    if StudentIssuedDocument:
        records = StudentIssuedDocument.objects.filter(student__in=students).select_related("student", "issued_document")[:100]
    return render(request, "parent_portal/documents.html", {"records": records})


@parent_required
def announcements(request):
    records = Announcement.objects.filter(is_active=True).order_by("-created_at")[:100]
    return render(request, "parent_portal/announcements.html", {"records": records})


@parent_required
def account(request):
    family = _family_for_user(request.user)
    if family is None:
        return render(request, "parent_portal/no_profile.html")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    action = request.POST.get("action", "") if request.method == "POST" else ""
    family_form = ParentFamilyPersonalForm(
        request.POST if action == "personal" else None, instance=family, prefix="family"
    )
    photo_form = ParentPhotoForm(
        request.POST if action == "photo" else None,
        request.FILES if action == "photo" else None,
        instance=profile,
        prefix="photo",
    )
    password_form = PasswordChangeForm(
        request.user, request.POST if action == "password" else None, prefix="password"
    )
    for field in password_form.fields.values():
        field.widget.attrs.setdefault("class", "form-control")

    if request.method == "POST" and action == "personal" and family_form.is_valid():
        family_form.save()
        messages.success(request, "تم تحديث معلومات ولي الأمر الشخصية.")
        return redirect("parent_portal:account")
    if request.method == "POST" and action == "photo" and photo_form.is_valid():
        photo_form.save()
        messages.success(request, "تم تحديث الصورة الشخصية.")
        return redirect("parent_portal:account")
    if request.method == "POST" and action == "password" and password_form.is_valid():
        user = password_form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "تم تغيير كلمة المرور بنجاح.")
        return redirect("parent_portal:account")

    return render(request, "parent_portal/account.html", {
        "family": family,
        "profile": profile,
        "family_form": family_form,
        "photo_form": photo_form,
        "password_form": password_form,
        "form": password_form,
    })

@management_required
def family_management(request):
    families = (
        Family.objects.filter(is_active=True, merged_into__isnull=True).select_related("user", "school")
        .prefetch_related("children__student")
        .order_by("guardian_name", "phone", "id")
    )
    return render(request, "parent_portal/family_management.html", {"families": families})


@management_required
def guardian_duplicates(request):
    return render(request, "parent_portal/guardian_duplicates.html", {"groups": guardian_duplicate_groups()})


@management_required
@require_POST
def guardian_duplicate_merge(request):
    ids = [value for value in request.POST.get("family_ids", "").split(",") if value.strip().isdigit()]
    try:
        canonical, count = merge_guardian_group(
            family_ids=ids,
            canonical_id=int(request.POST.get("canonical_id", "0")),
            user=request.user,
        )
    except (ValidationError, ValueError) as exc:
        messages.error(request, getattr(exc, "messages", [str(exc)])[0])
    else:
        audit(request, "update", "parent_portal.Family", canonical.pk, f"دمج {count} ملفات مكررة في ملف ولي الأمر {canonical.pk}")
        messages.success(request, f"تم دمج {count} ملفات في الملف الأساسي مع نقل روابط الأبناء وإيقاف الحسابات المكررة.")
    return redirect("parent_portal:guardian_duplicates")


def _family_finance_context(family):
    return build_family_finance_context(family)


@management_required
def family_detail(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    context = _family_finance_context(family)
    context.update({"can_print_receipts": True, "receipt_family_pk": family.pk})
    return render(request, "parent_portal/family_detail.html", context)


@management_required
def family_receipt_print(request, pk, source_type, receipt_pk):
    family = get_object_or_404(Family.objects.select_related("school"), pk=pk)
    if source_type not in {"fee", "accounting"}:
        raise Http404("نوع الإيصال غير معروف.")
    history = build_guardian_receipt_history(
        [link.student for link in FamilyStudent.objects.filter(family=family, is_active=True).select_related("student")]
    )
    receipt = next(
        (item for item in history if item.get("source_type") == source_type and item.get("source_id") == receipt_pk),
        None,
    )
    if receipt is None:
        raise Http404("الإيصال لا يتبع ملف ولي الأمر المحدد.")
    return render(request, "parent_portal/guardian_receipt_print.html", {"family": family, "receipt": receipt})


@management_required
def family_update(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    form = FamilyIdentityForm(request.POST or None, instance=family)
    if request.method == "POST" and form.is_valid():
        try:
            update_family_identity(
                family,
                guardian_name=form.cleaned_data["guardian_name"],
                phone=form.cleaned_data["phone"],
                identity_type=form.cleaned_data.get("identity_type", "national"),
                identity_number=form.cleaned_data.get("identity_number", ""),
                relation=form.cleaned_data.get("relation", "ولي أمر"),
            )
        except Exception as exc:
            message = getattr(exc, "messages", None)
            form.add_error(None, message[0] if message else str(exc))
        else:
            if family.financial_policy != form.cleaned_data["financial_policy"]:
                family.financial_policy = form.cleaned_data["financial_policy"]
                family.save(update_fields=["financial_policy", "updated_at"])
            messages.success(request, "تم تحديث المصدر الرسمي لبيانات ولي الأمر ومزامنة الأبناء.")
            return redirect("parent_portal:family_detail", pk=family.pk)
    return render(request, "parent_portal/family_form.html", {"family": family, "form": form})


@management_required
def family_statement_print(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    return render(request, "parent_portal/family_statement_print.html", _family_finance_context(family))


@management_required
def family_account_create(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    if request.method != "POST":
        return redirect("parent_portal:family_detail", pk=family.pk)
    user, password, created = ensure_family_account(family)
    if not created:
        messages.info(request, "ملف ولي الأمر مرتبط بحساب مستخدم بالفعل.")
        return redirect("parent_portal:family_detail", pk=family.pk)
    return render(request, "parent_portal/family_credentials.html", {"family": family, "username": user.username, "password": password, "created": True})


@management_required
def family_account_reset(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    if request.method != "POST":
        return redirect("parent_portal:family_detail", pk=family.pk)
    user, password = reset_family_password(family)
    return render(request, "parent_portal/family_credentials.html", {"family": family, "username": user.username, "password": password, "created": False})


@management_required
def family_statement_csv(request, pk):
    family = get_object_or_404(Family.objects.select_related("user", "school"), pk=pk)
    context = _family_finance_context(family)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="guardian-{family.pk}-statement.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["ولي الأمر", family.guardian_name, "الهاتف", family.phone, "رقم ملف ولي الأمر", family.family_code])
    writer.writerow([])
    writer.writerow([
        "الطالب",
        "الصف",
        "رسوم السنة الحالية",
        "مدفوع السنة الحالية",
        "متبقي السنة الحالية",
        "متبقيات السنوات السابقة",
        "الإجمالي المطلوب",
        "حالة السنة الحالية",
    ])
    for card in context["cards"]:
        writer.writerow([
            card["student"].full_name,
            f'{card["student"].grade} {card["student"].section}',
            card["total"],
            card["paid"],
            card["remaining"],
            card["previous_debt"]["total"],
            card["combined_remaining"],
            card["status_label"],
        ])
    writer.writerow([])
    writer.writerow(["الإيصال", "التاريخ", "النوع", "المبلغ", "المتبقي بعد العملية"])
    for payment in context["payments"]:
        writer.writerow([
            payment.receipt_number,
            payment.created_at.strftime("%Y-%m-%d %H:%M"),
            f"{payment.payment_period_label} — {payment.get_scope_display()}",
            payment.total_amount,
            payment.total_due_after,
        ])
    return response

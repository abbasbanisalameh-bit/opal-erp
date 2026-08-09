from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone


DEFAULT_ACCOUNT_PASSWORD = "Opal@12345"

DEMO_STUDENT_COUNT = 500
DEMO_GUARDIAN_COUNT = 200
DEMO_TEACHER_COUNT = 30
DEMO_TEACHER_WEEKLY_LOAD = 30
DEMO_TEACHER_DAILY_TARGET = 6


def _subject_plan_for_grade(grade_order):
    """Thirty weekly lessons per section; Arabic, math and science occur daily."""
    return [
        ("اللغة العربية", 5),
        ("الرياضيات", 5),
        ("العلوم", 5),
        ("اللغة الإنجليزية", 5),
        ("التربية الإسلامية", 2),
        ("التربية المهنية", 2),
        ("التربية الرياضية", 2),
        ("الحاسوب", 1),
        ("التربية الفنية", 1),
        ("الاجتماعيات", 1),
        ("الثقافة المالية", 1),
    ]


def _teacher_specialization_label(subject_loads):
    ordered = sorted(subject_loads.items(), key=lambda item: (-item[1], item[0]))
    names = [name for name, _ in ordered[:3]]
    return " / ".join(names) if names else "متعدد المواد"


def _delete_all(model):
    count = model.objects.count()
    model.objects.all().delete()
    return count


@transaction.atomic
def reset_all_operational_data(*, keep_user=None):
    """Delete operational records while preserving the current superuser and permission structure."""
    if keep_user is None or not keep_user.pk or not keep_user.is_superuser:
        raise ValueError("يجب تحديد حساب المدير الأعلى الحالي قبل تنفيذ التصفير الشامل.")
    from academics.models import Enrollment, Grade, Section, StudentDocument, StudentLifecycleEvent, Subject
    from accounting.models import (
        CanteenTransaction, DiscountRequest, ExpenseEntry, FeeCategory,
        FinancialCarryForward, FinancialYearClosure, Installment,
        MonthlyFinancialStatement, MonthlyFinancialTarget, Receipt,
        StudentInvoice, StudentPayment,
    )
    from admissions.models import (
        FeePayment, FeePaymentAllocation, GradeFee, RegistrationSettings,
        StudentRegistration, TransportRoute,
    )
    from announcements.models import Announcement
    from attendance_v2.models import Attendance, AttendanceRegister
    from core.models import (
        AcademicYear, AuditLog, Branch, DataIntegrityIssue, DataIntegrityRun, School,
        SemesterStructureSnapshot, Sequence,
    )
    from development_center.models import (
        ActivityLog, Bug, Decision, Idea, Milestone, Module,
        Notification as DevelopmentNotification, Release, Sprint,
        SprintDailySnapshot, Task,
    )
    from documents.models import DocumentSettings, DocumentTemplate, IssuedDocument, StudentIssuedDocument
    from enterprise_ops.models import (
        ApprovalAction, BroadcastMessage, FeedbackTicket, MonthlyServiceEvaluation, Notification,
        ReportPreset, WorkflowRequest,
    )
    from exams.models import (
        AnnualStudentResult, AnnualSubjectResult, Exam, ExamCycle,
        SemesterSubjectResult, StudentMark,
    )
    from openemis_integration.models import OpenEMISSyncLog
    from parent_portal.models import Family, FamilyStudent, TeacherMonthlyEvaluation
    from students.models import Student
    from teachers.models import (
        Homework, Teacher, TeacherAdvance, TeacherAssignment,
        TeacherDocument, TeacherPayroll, TeacherPerformanceSnapshot,
    )
    from timetable.models import (
        BiometricDailySummary, ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TeacherAbsence,
        TeacherBiometricIdentity, TeacherBiometricPunch, TimeSlot, TimetableEntry,
    )

    counts = {
        "students": Student.objects.count(), "teachers": Teacher.objects.count(),
        "families": Family.objects.count(), "documents": IssuedDocument.objects.count(),
        "receipts": Receipt.objects.count() + FeePayment.objects.count(),
    }

    # Remove learning-platform operational data before school/student/teacher rows.
    # The safe production-reset ordering is reused so PROTECT relations cannot
    # leave a partially-reset demo database.
    from django.apps import apps
    from core.production_reset import DELETE_MODEL_LABELS
    for label in DELETE_MODEL_LABELS:
        if label.startswith("learning_platform."):
            app_label, model_name = label.split(".", 1)
            _delete_all(apps.get_model(app_label, model_name))

    # Protected and transactional financial chains are removed from leaf to root.
    _delete_all(MonthlyFinancialStatement)
    _delete_all(CanteenTransaction)
    _delete_all(FinancialCarryForward)
    _delete_all(FinancialYearClosure)
    _delete_all(Receipt)
    _delete_all(FeePaymentAllocation)
    _delete_all(FeePayment)
    _delete_all(DiscountRequest)
    _delete_all(Installment)
    _delete_all(StudentPayment)
    _delete_all(StudentRegistration)
    _delete_all(StudentInvoice)
    _delete_all(FeeCategory)
    _delete_all(ExpenseEntry)
    _delete_all(MonthlyFinancialTarget)

    _delete_all(StudentIssuedDocument)
    _delete_all(IssuedDocument)
    _delete_all(DocumentSettings)
    _delete_all(DocumentTemplate)

    _delete_all(AnnualStudentResult)
    _delete_all(AnnualSubjectResult)
    _delete_all(SemesterSubjectResult)
    _delete_all(StudentMark)
    _delete_all(Exam)
    _delete_all(ExamCycle)
    _delete_all(AttendanceRegister)
    _delete_all(Attendance)
    _delete_all(BiometricDailySummary)
    _delete_all(TeacherBiometricPunch)
    _delete_all(TeacherBiometricIdentity)
    _delete_all(ClassCoverage)
    _delete_all(TeacherAbsence)
    _delete_all(TimetableEntry)
    _delete_all(SchoolDayEvent)
    _delete_all(SchoolScheduleSettings)
    _delete_all(TimeSlot)

    _delete_all(Homework)
    _delete_all(TeacherPerformanceSnapshot)
    _delete_all(TeacherPayroll)
    _delete_all(TeacherAdvance)
    _delete_all(TeacherMonthlyEvaluation)
    _delete_all(TeacherAssignment)
    _delete_all(TeacherDocument)
    _delete_all(Teacher)
    _delete_all(FamilyStudent)
    _delete_all(Family)

    _delete_all(StudentLifecycleEvent)
    _delete_all(StudentDocument)
    _delete_all(Enrollment)
    _delete_all(Student)

    _delete_all(GradeFee)
    _delete_all(TransportRoute)
    _delete_all(RegistrationSettings)
    _delete_all(Section)
    _delete_all(Subject)
    _delete_all(Grade)
    _delete_all(SemesterStructureSnapshot)

    # A prepared academic year may protect its source year through a nullable
    # self-reference. Detach that operational link before deleting all years.
    AcademicYear.objects.exclude(preparation_source=None).update(preparation_source=None)
    _delete_all(AcademicYear)
    _delete_all(Branch)
    _delete_all(School)

    _delete_all(ApprovalAction)
    _delete_all(MonthlyServiceEvaluation)
    _delete_all(FeedbackTicket)
    _delete_all(BroadcastMessage)
    _delete_all(WorkflowRequest)
    _delete_all(Notification)
    _delete_all(ReportPreset)
    # RolePermissionRule is part of the permission structure and must survive reset.
    _delete_all(Announcement)
    _delete_all(OpenEMISSyncLog)
    _delete_all(SprintDailySnapshot)
    _delete_all(ActivityLog)
    _delete_all(DevelopmentNotification)
    _delete_all(Task)
    _delete_all(Milestone)
    _delete_all(Release)
    _delete_all(Sprint)
    _delete_all(Module)
    _delete_all(Idea)
    _delete_all(Decision)
    _delete_all(Bug)
    _delete_all(DataIntegrityIssue)
    _delete_all(DataIntegrityRun)
    _delete_all(AuditLog)
    _delete_all(Sequence)

    # Preserve only the manager account that explicitly launched the reset.
    # All other users, including other superusers, are operational data here.
    removable_users = User.objects.exclude(pk=keep_user.pk)
    counts["users"] = removable_users.count()
    removable_users.delete()
    return counts


def _guardian_index(student_index):
    """Exact 500-student/200-family distribution: 50 families each with 1, 2, 3 and 4 children."""
    if student_index <= 50:
        return student_index, 0
    if student_index <= 150:
        relative = student_index - 51
        return 51 + (relative // 2), relative % 2
    if student_index <= 300:
        relative = student_index - 151
        return 101 + (relative // 3), relative % 3
    relative = student_index - 301
    return 151 + (relative // 4), relative % 4


def _relation_for(guardian_index, child_position):
    return "والد"


def _month_28(base_date, offset):
    value = (base_date.year * 12 + base_date.month - 1) + offset
    return date(value // 12, value % 12 + 1, 28)


def _structure(school):
    from academics.models import Grade, Section, Subject
    from academics.subject_identity import default_subject_colour, normalize_subject_key
    from admissions.models import GradeFee, RegistrationSettings, TransportRoute
    from core.models import AcademicYear, Branch
    from documents.models import DocumentSettings
    from timetable.models import SchoolDayEvent, SchoolScheduleSettings, TimeSlot

    branch = Branch.objects.create(
        school=school, name="الفرع الرئيسي", phone="027555555",
        address="إربد", is_main=True, is_active=True,
    )
    start_year = timezone.localdate().year
    year = AcademicYear.objects.create(
        school=school, name=f"{start_year}/{start_year + 1}",
        start_date=date(start_year, 9, 1), midyear_break_start=date(start_year + 1, 1, 16),
        midyear_break_end=date(start_year + 1, 1, 31), end_date=date(start_year + 1, 6, 30),
        is_current=True,
    )
    first_semester = year.semesters.get(code="first")
    first_semester.is_current = True
    first_semester.save(update_fields=["is_current"])

    grade_names = [
        "الصف الأول", "الصف الثاني", "الصف الثالث", "الصف الرابع",
        "الصف الخامس", "الصف السادس", "الصف السابع", "الصف الثامن",
        "الصف التاسع", "الصف العاشر", "الصف الحادي عشر", "الصف الثاني عشر",
    ]
    grades = [Grade(school=school, name=name, order=index) for index, name in enumerate(grade_names, 1)]
    Grade.objects.bulk_create(grades)
    grades = list(Grade.objects.filter(school=school).order_by("order"))
    GradeFee.objects.bulk_create([
        GradeFee(school=school, academic_year=year, grade=grade, tuition_fee=Decimal("900") + grade.order * Decimal("75"))
        for grade in grades
    ])

    sections = []
    subject_rows = []
    all_subject_names = []
    for grade in grades:
        section_names = ("أ", "ب", "ج") if grade.order <= 6 else ("أ", "ب")
        for section_name in section_names:
            sections.append(Section(
                academic_year=year, branch=branch, grade=grade,
                name=f"شعبة {section_name}", capacity=30, is_active=True,
            ))
        for subject_name, _ in _subject_plan_for_grade(grade.order):
            if subject_name not in all_subject_names:
                all_subject_names.append(subject_name)

    colour_by_key = {}
    for subject_name in all_subject_names:
        canonical_key = normalize_subject_key(subject_name)
        colour_by_key[canonical_key] = default_subject_colour(canonical_key, colour_by_key.values())

    for grade in grades:
        for index, (subject_name, weekly_periods) in enumerate(_subject_plan_for_grade(grade.order), 1):
            canonical_key = normalize_subject_key(subject_name)
            subject_rows.append(Subject(
                academic_year=year, grade=grade, name=subject_name,
                code=f"G{grade.order:02d}-S{index:02d}",
                weekly_periods=weekly_periods,
                is_required=True, canonical_key=canonical_key,
                color=colour_by_key[canonical_key], is_active=True,
            ))

    Section.objects.bulk_create(sections)
    Subject.objects.bulk_create(subject_rows)
    sections = list(
        Section.objects.filter(academic_year=year)
        .select_related("grade")
        .order_by("grade__order", "name")
    )
    subjects_by_grade = {
        grade.pk: list(Subject.objects.filter(academic_year=year, grade=grade).order_by("code"))
        for grade in grades
    }

    # Eight periods remain available so the manager can add future assignments
    # and so the three staggered break groups keep valid non-overlapping windows.
    slots = []
    cursor = datetime.combine(date.today(), time(8, 0))
    for index in range(1, 9):
        start = cursor.time()
        end_dt = cursor + timedelta(minutes=40)
        slots.append(TimeSlot(
            name=f"الحصة {index}", start_time=start, end_time=end_dt.time(),
            order=index, is_active=True,
        ))
        cursor = end_dt + timedelta(minutes=10)
    TimeSlot.objects.bulk_create(slots)
    SchoolScheduleSettings.objects.create(
        school=school,
        weekend_days="friday,saturday",
        alert_minutes_before_end=5,
    )

    SchoolDayEvent.objects.bulk_create([
        SchoolDayEvent(
            school=school, name="الطابور الصباحي", event_type="assembly",
            start_time=time(7, 40), end_time=time(7, 55),
            days="sunday,monday,tuesday,wednesday,thursday", order=1,
        ),
        SchoolDayEvent(
            school=school, name="نهاية الدوام", event_type="dismissal",
            start_time=time(14, 45), end_time=time(14, 55),
            days="sunday,monday,tuesday,wednesday,thursday", order=8,
        ),
        SchoolDayEvent(
            school=school, name="النشاط المدرسي الأسبوعي", event_type="other",
            start_time=time(15, 0), end_time=time(15, 40),
            days="thursday", order=9,
        ),
    ])

    break_definitions = (
        ("استراحة الصفوف الأساسية الدنيا", range(1, 5), 2),
        ("استراحة الصفوف الأساسية العليا", range(5, 9), 3),
        ("استراحة الصفوف الثانوية", range(9, 13), 4),
    )
    for name, grade_orders, order in break_definitions:
        event = SchoolDayEvent.objects.create(
            school=school,
            name=name,
            event_type="break",
            duration_minutes=20,
            placement_mode="smart",
            days="sunday,monday,tuesday,wednesday,thursday",
            order=order,
            is_active=True,
        )
        event.sections.set([section for section in sections if section.grade.order in grade_orders])

    RegistrationSettings.objects.create(school=school, first_payment_percent=20)
    TransportRoute.objects.bulk_create([
        TransportRoute(school=school, name=name, full_fee=amount, is_active=True)
        for name, amount in (("مسار إربد المدينة", 300), ("مسار الحصن", 325), ("مسار الرمثا", 350), ("مسار بني عبيد", 300))
    ])
    DocumentSettings.objects.create(
        school=school, manager_name="مدير مدرسة أوبال", manager_title="المدير العام", stamp_label="ختم المدرسة",
    )
    return branch, year, grades, sections, subjects_by_grade


def _validate_integrated_academic_demo(*, school, year, sections):
    """Fail atomically unless the latest plan/workload/break/timetable chain is coherent."""
    from academics.models import Subject
    from teachers.models import TeacherAssignment
    from timetable.models import SchoolDayEvent, TimeSlot, TimetableEntry

    canonical_days = {"sunday", "monday", "tuesday", "wednesday", "thursday"}
    subject_plans = list(
        Subject.objects.filter(academic_year=year, is_active=True)
        .select_related("grade")
    )
    assignments = list(
        TeacherAssignment.objects.filter(academic_year=year, is_active=True)
        .select_related("teacher", "section__grade", "subject")
    )
    entries = list(
        TimetableEntry.objects.filter(academic_year=year, is_active=True)
        .select_related("section", "subject", "teacher", "time_slot")
    )
    breaks = list(
        SchoolDayEvent.objects.filter(school=school, event_type="break", is_active=True)
        .prefetch_related("sections")
        .order_by("start_time", "order", "pk")
    )
    base_slots = list(
        TimeSlot.objects.filter(is_active=True, generated_for_smart_schedule=False)
        .order_by("order", "pk")
    )

    if len(base_slots) != 8:
        raise ValueError("بيانات الاختبار المترابطة تحتاج ثمانية أوقات حصص أساسية.")
    if len(sections) != 30:
        raise ValueError("يجب أن تتضمن بيانات R29 ثلاثين شعبة مترابطة.")
    if len(breaks) != 3:
        raise ValueError("يجب أن تتضمن بيانات الاختبار ثلاث مجموعات استراحة مترابطة.")
    if any(item.effective_duration_minutes != 20 for item in breaks):
        raise ValueError("مدة كل استراحة في بيانات R29 يجب أن تكون عشرين دقيقة.")
    if any(item.placement_mode != "smart" or not item.start_time or not item.end_time for item in breaks):
        raise ValueError("لم يثبت محرك الجدول أوقات جميع الاستراحات الذكية.")

    section_ids = {section.pk for section in sections}
    break_membership = Counter()
    for event in breaks:
        for section_id in event.sections.values_list("pk", flat=True):
            if section_id in section_ids:
                break_membership[section_id] += 1
    if set(break_membership) != section_ids or any(value != 1 for value in break_membership.values()):
        raise ValueError("يجب أن ترتبط كل شعبة باستراحة واحدة فقط في بيانات القبول التجريبية.")

    ordered_breaks = sorted(breaks, key=lambda item: (item.start_time, item.end_time))
    for previous, current in zip(ordered_breaks, ordered_breaks[1:]):
        if previous.end_time > current.start_time:
            raise ValueError("الاستراحات التجريبية متداخلة رغم اعتماد ساحة واحدة.")

    plan_map = {(item.grade_id, item.pk): item.weekly_periods for item in subject_plans}
    assignment_map = {}
    assigned_by_teacher = Counter()
    for assignment in assignments:
        key = (assignment.section_id, assignment.subject_id)
        if key in assignment_map:
            raise ValueError("يوجد تكليف تجريبي مكرر للمادة والشعبة نفسها.")
        assignment_map[key] = assignment
        required = plan_map.get((assignment.section.grade_id, assignment.subject_id))
        if required is None:
            raise ValueError("يوجد تكليف تجريبي لا يقابله بند في الخطة الدراسية.")
        assigned_by_teacher[assignment.teacher_id] += required

    expected_total = 0
    entry_counts = Counter((item.section_id, item.subject_id) for item in entries)
    for section in sections:
        for subject in subject_plans:
            if subject.grade_id != section.grade_id:
                continue
            key = (section.pk, subject.pk)
            assignment = assignment_map.get(key)
            if assignment is None:
                raise ValueError("خطة المواد التجريبية تحتوي مادة بلا تكليف فعّال.")
            expected_total += subject.weekly_periods
            if entry_counts[key] != subject.weekly_periods:
                raise ValueError("الجدول التجريبي لا يغطي جميع حصص الخطة بدقة.")

    if len(entries) != expected_total:
        raise ValueError("إجمالي حصص الجدول التجريبي لا يطابق إجمالي الخطة.")
    if any(item.day not in canonical_days for item in entries):
        raise ValueError("الجدول التجريبي يجب أن يعمل من الأحد إلى الخميس فقط.")
    for entry in entries:
        assignment = assignment_map.get((entry.section_id, entry.subject_id))
        if assignment is None or assignment.teacher_id != entry.teacher_id:
            raise ValueError("توجد حصة في الجدول لا تطابق التكليف الرسمي.")

    daily_subjects = {"اللغة العربية", "الرياضيات", "العلوم"}
    daily_subject_count = Counter((entry.section_id, entry.subject.name, entry.day) for entry in entries)
    for section in sections:
        for subject_name in daily_subjects:
            for day in canonical_days:
                if daily_subject_count[(section.pk, subject_name, day)] != 1:
                    raise ValueError(f"يجب أن تكون مادة {subject_name} موجودة مرة واحدة يوميًا في كل شعبة.")

    homeroom_ids = [section.homeroom_teacher_id for section in sections]
    if any(value is None for value in homeroom_ids) or len(set(homeroom_ids)) != len(sections):
        raise ValueError("يجب أن يكون لكل شعبة مربي صف واحد مختلف في بيانات R29.")

    configured_teachers = 0
    daily_by_teacher = Counter((entry.teacher_id, entry.day) for entry in entries if entry.teacher_id)
    for teacher_id, assigned in assigned_by_teacher.items():
        teacher = next(item.teacher for item in assignments if item.teacher_id == teacher_id)
        if teacher.weekly_teaching_load != DEMO_TEACHER_WEEKLY_LOAD or assigned != DEMO_TEACHER_WEEKLY_LOAD:
            raise ValueError("يجب أن يكون نصاب كل معلم تجريبي 30 حصة فعلية بالضبط.")
        if teacher.free_period_policy != "daily" or teacher.daily_free_periods < 1:
            raise ValueError("يجب أن يبقى لكل معلم حصة فراغ يومية واحدة على الأقل.")
        for day in canonical_days:
            if daily_by_teacher[(teacher_id, day)] != DEMO_TEACHER_DAILY_TARGET:
                raise ValueError("لم يوزع الجدول نصاب المعلم على ست حصص يوميًا.")
        configured_teachers += 1

    for event in breaks:
        break_sections = set(event.sections.values_list("pk", flat=True))
        for entry in entries:
            if entry.section_id not in break_sections or entry.day not in event.day_codes:
                continue
            if entry.time_slot.start_time < event.end_time and entry.time_slot.end_time > event.start_time:
                raise ValueError("توجد حصة تجريبية تتداخل مع استراحة الشعبة.")

    return {
        "subject_plans": len(subject_plans),
        "assignments": len(assignments),
        "base_slots": len(base_slots),
        "breaks": len(breaks),
        "day_events": SchoolDayEvent.objects.filter(school=school, is_active=True).count(),
        "configured_teachers": configured_teachers,
        "teacher_weekly_load": DEMO_TEACHER_WEEKLY_LOAD,
        "teacher_daily_target": DEMO_TEACHER_DAILY_TARGET,
        "timetable_entries": len(entries),
        "schedule_verified": True,
    }


@transaction.atomic
def seed_system_data(*, student_count=DEMO_STUDENT_COUNT, teacher_count=DEMO_TEACHER_COUNT, guardian_count=DEMO_GUARDIAN_COUNT, user=None):
    from accounts.models import Role, UserProfile
    from academics.models import Enrollment, StudentDocument
    from accounting.models import (
        ExpenseEntry, FeeCategory, MonthlyFinancialTarget, Receipt,
        StudentInvoice, StudentPayment,
    )
    from admissions.models import FeePayment, FeePaymentAllocation, StudentRegistration
    from announcements.models import Announcement
    from attendance_v2.models import Attendance, AttendanceRegister
    from core.models import School
    from documents.defaults import DEFAULT_DOCUMENT_TEMPLATES
    from documents.models import DocumentTemplate, IssuedDocument, StudentIssuedDocument
    from enterprise_ops.models import (
        BroadcastMessage, FeedbackTicket, MonthlyServiceEvaluation, Notification,
        ReportPreset, WorkflowRequest,
    )
    from exams.models import (
        AnnualStudentResult, AnnualSubjectResult, Exam, ExamCycle,
        SemesterSubjectResult, StudentMark,
    )
    from parent_portal.models import Family, FamilyStudent, TeacherMonthlyEvaluation
    from students.models import Student
    from teachers.models import (
        Homework, Teacher, TeacherAdvance, TeacherAssignment,
        TeacherDocument, TeacherPayroll,
    )
    from timetable.models import TeacherAbsence, TimetableEntry
    from timetable.services import build_smart_timetable

    # The button intentionally produces one stable, complete acceptance dataset.
    if user is None or not user.pk or not user.is_superuser:
        raise ValueError("يجب تحديد حساب المدير الأعلى الحالي قبل إدخال البيانات التجريبية.")
    student_count, teacher_count, guardian_count = DEMO_STUDENT_COUNT, DEMO_TEACHER_COUNT, DEMO_GUARDIAN_COUNT
    School.objects.select_for_update().filter(is_active=True).first()
    reset_all_operational_data(keep_user=user)
    school = School.objects.filter(is_active=True).first()
    if school is None:
        school = School.objects.create(
            name="مدرسة أوبال الدولية", official_name="مدرسة أوبال الدولية",
            phone="027555555", email="info@opal-school.edu", address="إربد", is_active=True,
        )
    branch, year, grades, sections, subjects_by_grade = _structure(school)

    parent_role, _ = Role.objects.get_or_create(code="parent", defaults={"name": "ولي أمر", "description": "حساب ولي أمر"})
    teacher_role, _ = Role.objects.get_or_create(code="teacher", defaults={"name": "معلم", "description": "حساب معلم"})
    password_hash = make_password(DEFAULT_ACCOUNT_PASSWORD)
    male_names = ["أحمد", "محمد", "عمر", "يوسف", "خالد", "محمود", "إبراهيم", "حمزة", "ياسر", "معاذ"]
    female_names = ["مريم", "سارة", "ليان", "نور", "تالا", "رنا", "هدى", "دانا", "آية", "لينا"]
    family_names = ["الحداد", "الخطيب", "النجار", "العلي", "العبادي", "العمري", "الزعبي", "المصري", "الرفاعي", "الشامي", "الحسن", "النعيمي"]

    def generated_name(index, *, female=False):
        """Return a natural-looking, unique four-part Arabic name for this data set."""
        value = index - 1
        first_pool = female_names if female else male_names
        first = first_pool[value % len(first_pool)]
        father = male_names[(value // 10) % len(male_names)]
        grandfather = male_names[(value // 100) % len(male_names)]
        family_name = family_names[(value * 7 + value // 10) % len(family_names)]
        return first, father, grandfather, family_name, f"{first} {father} {grandfather} {family_name}"

    def family_identity(index):
        value = index - 1
        father = male_names[value % len(male_names)]
        grandfather = male_names[(value // 10 + 3) % len(male_names)]
        great_grandfather = male_names[(value // 20 + 6) % len(male_names)]
        surname = family_names[(value * 5 + value // 10) % len(family_names)]
        return {
            "father": father, "grandfather": grandfather, "great_grandfather": great_grandfather,
            "surname": surname,
            "guardian_name": f"{father} {grandfather} {great_grandfather} {surname}",
        }

    account_rows = []
    for index in range(1, teacher_count + 1):
        *_, name = generated_name(index, female=index % 2 == 0)
        account_rows.append(User(username=f"teacher_{index:03d}", password=password_hash, first_name=name, email=f"teacher{index:03d}@opal-school.edu", is_active=True))
    for index in range(1, guardian_count + 1):
        identity = family_identity(index)
        account_rows.append(User(username=f"guardian_{index:03d}", password=password_hash, first_name=identity["guardian_name"], is_active=True))
    User.objects.bulk_create(account_rows)
    teacher_users = {row.username: row for row in User.objects.filter(username__startswith="teacher_")}
    guardian_users = {row.username: row for row in User.objects.filter(username__startswith="guardian_")}

    teacher_rows = []
    for index in range(1, teacher_count + 1):
        *_, full_name = generated_name(index, female=index % 2 == 0)
        teacher_rows.append(Teacher(
            user=teacher_users[f"teacher_{index:03d}"], employee_number=f"T-{index:04d}",
            source="manual", ministry_teacher_id=f"MIN-T-{index:05d}", full_name=full_name,
            national_id=f"2000{index:06d}", gender="male" if index % 2 else "female",
            birth_date=date(1980 + index % 20, (index % 12) + 1, (index % 27) + 1),
            phone=f"078{index:07d}", email=f"teacher{index:03d}@opal-school.edu",
            address=f"إربد - الحي {index % 10 + 1}", specialization="متعدد المواد",
            qualification="بكالوريوس تربية", hire_date=date(2020 + index % 5, 9, 1),
            school=school, branch=branch, monthly_salary=Decimal("550") + index * Decimal("8"),
            weekly_teaching_load=DEMO_TEACHER_WEEKLY_LOAD, free_period_policy="daily",
            daily_free_periods=1, weekly_free_periods=0,
            is_active=True, is_demo=False,
        ))
    Teacher.objects.bulk_create(teacher_rows)
    teachers = list(Teacher.objects.filter(school=school).select_related("user").order_by("employee_number"))
    TeacherDocument.objects.bulk_create([
        TeacherDocument(
            teacher=teacher, document_type=doc_type, title=title,
            document_number=f"{prefix}-{teacher.employee_number}", issue_date=teacher.hire_date,
        )
        for teacher in teachers
        for doc_type, title, prefix in (("contract", "عقد عمل", "CON"), ("qualification", "شهادة جامعية", "QUAL"))
    ])

    family_rows = []
    family_identity_by_index = {}
    for index in range(1, guardian_count + 1):
        identity = family_identity(index)
        family_identity_by_index[index] = identity
        family_rows.append(Family(
            school=school, user=guardian_users[f"guardian_{index:03d}"], source="manual",
            guardian_name=identity["guardian_name"], relation="والد", identity_type="national",
            identity_number=f"3000{index:06d}", phone=f"079{index:07d}",
            secondary_phone=f"077{index:07d}", email=f"guardian{index:03d}@mail.com",
            job_title="موظف", address=f"إربد - منطقة {index % 15 + 1}",
            family_code=f"G-{index:05d}", is_active=True,
        ))
    Family.objects.bulk_create(family_rows)
    families = list(Family.objects.filter(school=school).select_related("user").order_by("family_code"))
    family_by_index = {index: family for index, family in enumerate(families, 1)}

    UserProfile.objects.bulk_create([
        UserProfile(user=teacher.user, school=school, branch=branch, role=teacher_role, full_name=teacher.full_name, phone=teacher.phone, is_school_user=True)
        for teacher in teachers
    ] + [
        UserProfile(user=family.user, school=school, role=parent_role, full_name=family.guardian_name, phone=family.phone, is_school_user=False)
        for family in families
    ])
    teacher_group, _ = Group.objects.get_or_create(name="Teachers")
    through = Group.user_set.through
    through.objects.bulk_create([through(user_id=teacher.user_id, group_id=teacher_group.pk) for teacher in teachers], ignore_conflicts=True)

    # Build one exact and auditable chain: each of the 30 sections has one
    # unique homeroom teacher, and that teacher owns the section's complete
    # 30-period demo plan.  This deliberately favours relational correctness
    # over realism in synthetic data: 30 sections × 30 periods = 900, exactly
    # 30 teachers × 30 periods (6 per day across five days), with no hidden
    # cross-section teacher conflict introduced by the seed itself.
    teacher_loads = {teacher.pk: 0 for teacher in teachers}
    subject_loads_by_teacher = {teacher.pk: Counter() for teacher in teachers}
    assignment_rows = []
    for section_index, section in enumerate(sections):
        teacher = teachers[section_index]
        section.homeroom_teacher = teacher
        section.save(update_fields=["homeroom_teacher"])
        for subject in subjects_by_grade[section.grade_id]:
            periods = subject.weekly_periods
            teacher_loads[teacher.pk] += periods
            subject_loads_by_teacher[teacher.pk][subject.name] += periods
            assignment_rows.append(TeacherAssignment(
                teacher=teacher, academic_year=year, section=section, subject=subject,
                is_primary=True, is_active=True,
            ))

    if set(teacher_loads.values()) != {DEMO_TEACHER_WEEKLY_LOAD}:
        raise ValueError("لم يصل جميع المعلمين إلى النصاب التجريبي المطلوب وهو 30 حصة أسبوعيًا.")

    TeacherAssignment.objects.bulk_create(assignment_rows)
    for teacher in teachers:
        teacher.specialization = _teacher_specialization_label(subject_loads_by_teacher[teacher.pk])
        teacher.weekly_teaching_load = DEMO_TEACHER_WEEKLY_LOAD
        teacher.free_period_policy = "daily"
        teacher.daily_free_periods = 1
        teacher.weekly_free_periods = 0
    Teacher.objects.bulk_update(
        teachers,
        ["specialization", "weekly_teaching_load", "free_period_policy", "daily_free_periods", "weekly_free_periods"],
        batch_size=100,
    )

    assignments = list(
        TeacherAssignment.objects.filter(academic_year=year)
        .select_related("teacher", "section__grade", "subject")
        .order_by("teacher_id", "section_id", "subject_id")
    )
    schedule_result = build_smart_timetable(
        academic_year=year,
        apply=True,
        replace_generated=True,
        variant="balanced",
        enforce_daily_teaching_target=True,
    )
    if not schedule_result["can_apply"] or schedule_result["unresolved"]:
        first_issue = (
            schedule_result["blockers"][0]["message"]
            if schedule_result["blockers"]
            else schedule_result["unresolved"][0]["reason"]
        )
        raise ValueError(f"تعذر إنشاء بيانات الجدول المترابطة: {first_issue}")
    Homework.objects.bulk_create([
        Homework(
            assignment=assignment, title=f"واجب {assignment.subject.name}",
            description=f"حل التدريبات المقررة للشعبة {assignment.section}",
            assigned_date=timezone.localdate(), due_date=timezone.localdate() + timedelta(days=7),
            is_active=True, created_by=user,
        ) for assignment in assignments
    ])

    student_rows = []
    student_meta = {}
    for index in range(1, student_count + 1):
        guardian_index, position = _guardian_index(index)
        family = family_by_index[guardian_index]
        section = sections[(index - 1) % len(sections)]
        identity = family_identity_by_index[guardian_index]
        first_name = (female_names if index % 2 == 0 else male_names)[(index + position) % 10]
        father_name = identity["father"]
        grandfather_name = identity["grandfather"]
        family_name = identity["surname"]
        full_name = f"{first_name} {father_name} {grandfather_name} {family_name}"
        number = f"STU-{index:05d}"
        student_rows.append(Student(
            student_number=number, source="manual", national_id=f"1000{index:06d}",
            ministry_student_id=f"MIN-S-{index:06d}", full_name=full_name,
            guardian_name=family.guardian_name, father_name=f"{father_name} {grandfather_name} {family_name}",
            mother_name=f"{female_names[(guardian_index + 2) % len(female_names)]} {grandfather_name} {family_name}",
            gender="male" if index % 2 else "female", blood_type=("A+", "B+", "O+", "AB+")[index % 4],
            grade=section.grade.name, section=section.name, phone=family.phone,
            address=family.address, status="active", enrollment_date=year.start_date,
            is_active=True, is_demo=False,
        ))
        student_meta[number] = {
            "index": index, "family": family, "section": section, "position": position,
            "first": first_name, "father": father_name, "grandfather": grandfather_name,
            "family_name": family_name,
        }
    Student.objects.bulk_create(student_rows)
    students = list(Student.objects.filter(student_number__startswith="STU-").order_by("student_number"))
    enrollment_rows, link_rows = [], []
    for student in students:
        meta = student_meta[student.student_number]
        section = meta["section"]
        enrollment_rows.append(Enrollment(
            student=student, academic_year=year, grade=section.grade, section=section,
            status="active", joined_at=year.start_date,
        ))
        link_rows.append(FamilyStudent(
            family=meta["family"], student=student,
            relation="والد", is_active=True,
        ))
    Enrollment.objects.bulk_create(enrollment_rows)
    FamilyStudent.objects.bulk_create(link_rows)

    category = FeeCategory.objects.create(name="الرسوم المدرسية", description="رسوم العام الدراسي الحالي", amount=Decimal("1200"), active=True)
    invoice_rows, payment_amounts = [], {}
    methods = ("cash", "card", "bank_transfer", "electronic", "cheque")
    for student in students:
        meta = student_meta[student.student_number]
        total = Decimal("900") + meta["section"].grade.order * Decimal("75")
        ratios = (Decimal("0"), Decimal("0.20"), Decimal("0.50"), Decimal("0.80"), Decimal("1.00"))
        if meta["position"] == 0:
            guardian_no = int(meta["family"].family_code.split("-")[1])
            ratio = (Decimal("0.20"), Decimal("0.50"), Decimal("0.80"), Decimal("1.00"))[(guardian_no - 1) % 4]
        else:
            ratio = ratios[(meta["index"] - 1) % len(ratios)]
        paid = (total * ratio).quantize(Decimal("0.01"))
        status = "open" if paid == 0 else ("paid" if paid >= total else "partial")
        invoice_rows.append(StudentInvoice(
            student=student, academic_year=year, fee_category=category, amount=total,
            due_date=year.start_date + timedelta(days=30), issue_date=year.start_date,
            status=status, paid=status == "paid", created_by=user,
        ))
        payment_amounts[student.pk] = (paid, total, methods[(meta["index"] - 1) % len(methods)])
    StudentInvoice.objects.bulk_create(invoice_rows)
    invoices = list(StudentInvoice.objects.filter(academic_year=year).select_related("student"))
    invoice_by_student = {row.student_id: row for row in invoices}
    StudentPayment.objects.bulk_create([
        StudentPayment(
            invoice=invoice, amount=payment_amounts[invoice.student_id][0],
            payment_date=year.start_date, reference=f"PAY-{invoice.student.student_number}",
            payment_method=payment_amounts[invoice.student_id][2], status="posted", created_by=user,
            notes="دفعة رسوم مدرسية",
        ) for invoice in invoices if payment_amounts[invoice.student_id][0] > 0
    ])
    payments = list(StudentPayment.objects.filter(invoice__academic_year=year).select_related("invoice__student"))
    payment_by_student = {row.invoice.student_id: row for row in payments}
    Receipt.objects.bulk_create([
        Receipt(payment=payment, receipt_number=f"REC-{payment.invoice.student.student_number}") for payment in payments
    ])
    receipts = {row.payment_id: row for row in Receipt.objects.filter(payment__in=payments)}

    registration_rows = []
    for student in students:
        meta = student_meta[student.student_number]
        invoice = invoice_by_student[student.pk]
        paid, total, method = payment_amounts[student.pk]
        payment = payment_by_student.get(student.pk)
        registration_rows.append(StudentRegistration(
            school=school, branch=branch, academic_year=year,
            registration_number=f"REG-{student.student_number}", student=student,
            grade=meta["section"].grade, section=meta["section"],
            first_name=meta["first"], father_name=meta["father"], grandfather_name=meta["grandfather"],
            family_name=meta["family_name"], full_name=student.full_name,
            national_id=student.national_id, gender=student.gender,
            birth_date=date(max(2005, year.start_date.year - (5 + meta["section"].grade.order)), (meta["index"] % 12) + 1, (meta["index"] % 27) + 1),
            address=student.address, phone=student.phone, guardian_name=student.guardian_name,
            guardian_identity_type="national", guardian_identity_number=meta["family"].identity_number,
            mother_name=student.mother_name, transport_type="none", discount_type="none",
            tuition_fee=total, transport_fee=0, discount_value=0, net_total=total,
            first_payment=paid, remaining_amount=total - paid, payment_method=method,
            invoice=invoice, payment=payment, receipt=receipts.get(payment.pk) if payment else None,
            created_by=user, notes="سجل طالب مكتمل",
        ))
    StudentRegistration.objects.bulk_create(registration_rows)

    # One canonical family receipt per guardian, allocated automatically to
    # every child who has a positive payment.  The first child always has a
    # payment, so all 200 guardians own at least one real receipt.
    family_fee_rows = []
    for family in families:
        family_students = [student for student in students if student_meta[student.student_number]["family"].pk == family.pk]
        family_payments = [payment_by_student.get(student.pk) for student in family_students]
        family_payments = [payment for payment in family_payments if payment is not None]
        if not family_payments:
            raise ValueError(f"ملف ولي الأمر {family.family_code} لا يحتوي دفعة، وهذا يخالف عقد R29.")
        due_before = sum((invoice_by_student[student.pk].amount for student in family_students), Decimal("0"))
        total_amount = sum((payment.amount for payment in family_payments), Decimal("0"))
        family_fee_rows.append(FeePayment(
            school=school, receipt_number=f"FAMILY-{family.family_code}",
            scope="all_siblings", main_student=family_students[0],
            guardian_name=family.guardian_name, phone=family.phone,
            total_amount=total_amount, total_due_before=due_before,
            total_due_after=due_before - total_amount,
            payment_method=family_payments[0].payment_method, created_by=user,
            notes="دفعة مترابطة عن جميع الإخوة — بيانات R29 التجريبية",
        ))
    FeePayment.objects.bulk_create(family_fee_rows)
    fee_payment_by_family = {row.receipt_number.replace("FAMILY-G-", ""): row for row in FeePayment.objects.filter(school=school, receipt_number__startswith="FAMILY-G-")}
    allocation_rows = []
    for student in students:
        payment = payment_by_student.get(student.pk)
        if payment is None:
            continue
        meta = student_meta[student.student_number]
        family_no = meta["family"].family_code.split("-")[1]
        family_payment = fee_payment_by_family[family_no]
        invoice = invoice_by_student[student.pk]
        allocation_rows.append(FeePaymentAllocation(
            fee_payment=family_payment, student=student, invoice=invoice, accounting_payment=payment,
            amount=payment.amount, total_fees=invoice.amount, paid_before=0,
            remaining_before=invoice.amount, remaining_after=invoice.amount - payment.amount,
        ))
    FeePaymentAllocation.objects.bulk_create(allocation_rows, batch_size=1000)


    # Ten recent school days using the current exception-only attendance policy.
    # A submitted register proves the homeroom teacher completed the daily task;
    # only absent/departed pupils are stored as Attendance rows.
    today = timezone.localdate()
    attendance_dates = []
    cursor = today
    while len(attendance_dates) < 10:
        if cursor.weekday() not in {4, 5}:  # Friday and Saturday are the Jordan weekend.
            attendance_dates.append(cursor)
        cursor -= timedelta(days=1)

    def aware_at(day, hour, minute):
        return timezone.make_aware(
            datetime.combine(day, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    register_rows = []
    for section in sections:
        teacher_user = section.homeroom_teacher.user if section.homeroom_teacher_id else user
        for attendance_date in attendance_dates:
            submitted_at = aware_at(attendance_date, 8, 20)
            register_rows.append(AttendanceRegister(
                academic_year=year, grade=section.grade, section=section, date=attendance_date,
                is_teacher_locked=True, teacher_locked_at=submitted_at,
                submitted_by=teacher_user, submitted_at=submitted_at,
                created_by=teacher_user,
            ))
    AttendanceRegister.objects.bulk_create(register_rows, batch_size=500)

    attendance_rows = []
    enrollment_by_student = {
        row.student_id: row
        for row in Enrollment.objects.filter(academic_year=year).select_related("grade", "section", "section__homeroom_teacher__user")
    }
    for student in students:
        enrollment = enrollment_by_student[student.pk]
        for day_index, attendance_date in enumerate(attendance_dates):
            marker = (student.pk + day_index) % 20
            status = "absent" if marker in {0, 1} else ("departed" if marker == 2 else None)
            if status is None:
                continue
            attendance_rows.append(Attendance(
                student=student, academic_year=year, grade=enrollment.grade, section=enrollment.section,
                date=attendance_date, status=status,
                departure_time=time(12, 30) if status == "departed" else None,
                recorded_by=enrollment.section.homeroom_teacher.user if enrollment.section.homeroom_teacher_id else user,
                updated_by=enrollment.section.homeroom_teacher.user if enrollment.section.homeroom_teacher_id else user,
            ))
    Attendance.objects.bulk_create(attendance_rows, batch_size=1000)

    # Official teacher work-attendance rows support the TPI engine without a parallel model.
    work_rows = []
    for teacher_index, teacher in enumerate(teachers, 1):
        for day_index, attendance_date in enumerate(attendance_dates):
            marker = (teacher_index + day_index) % 25
            if marker == 0:
                status, arrival, departure = "absent", None, None
            elif marker in {1, 2}:
                status, arrival, departure = "late", time(8, 15), time(14, 0)
            elif marker == 3:
                status, arrival, departure = "early_departure", time(8, 0), time(12, 30)
            elif marker == 4:
                status, arrival, departure = "approved_excuse", None, None
            elif marker == 5:
                status, arrival, departure = "official_mission", None, None
            else:
                continue  # No row means present under the official exception-only policy.
            approved_exception = status in {"approved_excuse", "official_mission"}
            work_rows.append(TeacherAbsence(
                teacher=teacher, date=attendance_date, attendance_status=status,
                arrival_time=arrival, departure_time=departure,
                reason=("عذر معتمد" if status == "approved_excuse" else "مهمة رسمية" if status == "official_mission" else ""),
                absence_type="unexcused" if status == "absent" else "excused",
                is_approved=approved_exception, approved_by=user if approved_exception else None,
                payroll_approved=False, recorded_by=user,
            ))
    TeacherAbsence.objects.bulk_create(work_rows, batch_size=1000)

    # Current evaluation architecture: per-teacher guardian evaluation plus one
    # separate monthly school-services evaluation per user.
    period = today.replace(day=1)
    teachers_by_id = {teacher.pk: teacher for teacher in teachers}
    teachers_by_section = {}
    for assignment in assignments:
        teachers_by_section.setdefault(assignment.section_id, set()).add(assignment.teacher_id)
    family_sections = {}
    for meta in student_meta.values():
        family_sections.setdefault(meta["family"].pk, set()).add(meta["section"].pk)

    teacher_evaluation_rows = []
    for family in families:
        teacher_ids = sorted({
            teacher_id
            for section_id in family_sections.get(family.pk, set())
            for teacher_id in teachers_by_section.get(section_id, set())
        })[:3]
        for teacher_id in teacher_ids:
            teacher_evaluation_rows.append(TeacherMonthlyEvaluation(
                family=family, teacher=teachers_by_id[teacher_id], period=period,
                teaching_quality_rating=3 + ((family.pk + teacher_id) % 3),
            ))
    TeacherMonthlyEvaluation.objects.bulk_create(teacher_evaluation_rows, batch_size=1000)

    evaluated_at = timezone.now()
    MonthlyServiceEvaluation.objects.bulk_create([
        MonthlyServiceEvaluation(
            user=family.user, school=school, branch=branch, period=period,
            teaching_quality_rating=3 + (index % 3),
            electronic_services_rating=3 + ((index + 1) % 3),
            teaching_quality_submitted_at=evaluated_at,
            electronic_services_submitted_at=evaluated_at,
        )
        for index, family in enumerate(families)
    ] + [
        MonthlyServiceEvaluation(
            user=teacher.user, school=school, branch=branch, period=period,
            electronic_services_rating=3 + (index % 3),
            electronic_services_submitted_at=evaluated_at,
        )
        for index, teacher in enumerate(teachers)
    ], batch_size=1000)

    # Four assessments per teaching assignment in both semesters. Linking every
    # exam to its canonical assignment makes the seeded marks usable by TPI.
    current_published_at = timezone.now()
    exam_rows = []
    for assignment in assignments:
        for semester in year.semesters.all():
            published_at = (
                current_published_at
                if semester.code == "second"
                else current_published_at - timedelta(days=35)
            )
            exam_date = timezone.localtime(published_at).date()
            for exam_type, maximum in Exam.MAX_MARKS.items():
                exam_rows.append(Exam(
                    name=f"{dict(Exam.EXAM_TYPES)[exam_type]} - {assignment.subject.name} - {assignment.section}",
                    exam_type=exam_type, academic_year=year, semester=semester,
                    grade=assignment.section.grade, section=assignment.section,
                    subject=assignment.subject, teacher_assignment=assignment,
                    max_mark=maximum, weight=maximum, pass_percentage=60,
                    exam_date=exam_date, marks_due_date=exam_date, status="published",
                    submitted_by=assignment.teacher.user, submitted_at=published_at - timedelta(hours=2),
                    approved_by=user, approved_at=published_at - timedelta(hours=1),
                    published_at=published_at, is_locked=True, is_active=True,
                ))
    Exam.objects.bulk_create(exam_rows, batch_size=1000)
    exams = list(
        Exam.objects.filter(academic_year=year)
        .select_related("grade", "section", "subject", "semester", "teacher_assignment")
    )
    students_by_section = {}
    for enrollment in Enrollment.objects.filter(academic_year=year).select_related("student"):
        students_by_section.setdefault(enrollment.section_id, []).append(enrollment.student)
    mark_rows = []
    for exam in exams:
        maximum = int(exam.max_mark)
        for student in students_by_section.get(exam.section_id, []):
            deduction = (student.pk + exam.subject_id + (1 if exam.semester.code == "first" else 3)) % max(2, maximum // 2)
            mark_rows.append(StudentMark(
                exam=exam, student=student, mark=Decimal(maximum - deduction),
                entered_by=exam.teacher_assignment.teacher.user if exam.teacher_assignment_id else user,
            ))
    StudentMark.objects.bulk_create(mark_rows, batch_size=2000)

    # Default editable templates plus physical and issued documents.
    for definition in DEFAULT_DOCUMENT_TEMPLATES:
        DocumentTemplate.objects.update_or_create(code=definition["code"], defaults={**definition, "is_active": True})
    student_template = DocumentTemplate.objects.get(code="student-proof")
    teacher_template = DocumentTemplate.objects.get(code="teacher-experience")
    guardian_template = DocumentTemplate.objects.get(code="guardian-statement")
    StudentDocument.objects.bulk_create([
        StudentDocument(student=student, document_type="birth_certificate", title="شهادة ميلاد") for student in students
    ])
    issued_rows = [
        IssuedDocument(
            template=student_template, student=student, applicant_name=student.full_name,
            document_number=f"DOC-{student.student_number}", title="إثبات طالب",
            content=f"تشير سجلات {school.official_name or school.name} إلى أن الطالب {student.full_name} مسجل في {student.grade}.",
            manager_name_snapshot="مدير مدرسة أوبال", issued_by=user,
        ) for student in students
    ] + [
        IssuedDocument(
            template=teacher_template, teacher=teacher, applicant_name=teacher.full_name,
            document_number=f"EXP-{teacher.employee_number}", title="شهادة خبرة",
            content=f"تشهد المدرسة بأن {teacher.full_name} يعمل لديها منذ {teacher.hire_date}.",
            manager_name_snapshot="مدير مدرسة أوبال", issued_by=user,
        ) for teacher in teachers
    ] + [
        IssuedDocument(
            template=guardian_template, guardian=family, applicant_name=family.guardian_name,
            document_number=f"STM-{family.family_code}", title="كشف حساب ولي الأمر",
            content=f"كشف حساب ولي الأمر {family.guardian_name} للعام الدراسي {year.name}.",
            manager_name_snapshot="مدير مدرسة أوبال", issued_by=user,
        ) for family in families
    ]
    IssuedDocument.objects.bulk_create(issued_rows, batch_size=1000)
    issued_students = {row.student_id: row for row in IssuedDocument.objects.exclude(student_id=None)}
    StudentIssuedDocument.objects.bulk_create([
        StudentIssuedDocument(student=student, issued_document=issued_students[student.pk]) for student in students
    ])

    ExpenseEntry.objects.bulk_create([
        ExpenseEntry(
            school=school, expense_number=f"EXPENSE-{index:04d}",
            expense_date=today - timedelta(days=index % 60), title=("صيانة" if index % 2 else "قرطاسية"),
            beneficiary=f"مورد {index:02d}", amount=Decimal("50") + index * Decimal("7"),
            payment_method=methods[index % len(methods)], created_by=user,
        ) for index in range(1, 37)
    ])
    MonthlyFinancialTarget.objects.bulk_create([
        MonthlyFinancialTarget(
            school=school, period_end=_month_28(today, offset),
            expected_amount=Decimal("45000") + offset * Decimal("1000"), updated_by=user,
        ) for offset in range(-6, 6)
    ])
    Announcement.objects.bulk_create([
        Announcement(title=title, message=message, announcement_type=kind, is_active=True)
        for title, message, kind in (
            ("بدء العام الدراسي", "نرحب بالطلبة وأولياء الأمور في العام الدراسي الجديد.", "success"),
            ("اجتماع أولياء الأمور", "يعقد الاجتماع يوم السبت في مبنى المدرسة.", "info"),
            ("متابعة الواجبات", "يرجى متابعة الواجبات من حساب ولي الأمر.", "warning"),
            ("الأنشطة المدرسية", "تم فتح التسجيل في الأنشطة الرياضية والثقافية.", "info"),
        )
    ])
    Notification.objects.bulk_create([
        Notification(
            recipient=family.user, title="تحديث حساب الطالب",
            message="تم تسجيل دفعة أو تحديث أكاديمي لأحد الطلبة المرتبطين بالحساب.",
            level="info", event_key=f"seed-family-{family.pk}",
        ) for family in families
    ])
    FeedbackTicket.objects.bulk_create([
        FeedbackTicket(
            sender=(families[index % len(families)].user if index % 2 else teachers[index % len(teachers)].user),
            school=school, branch=branch,
            kind="complaint" if index % 3 == 0 else "suggestion",
            title=f"رسالة مدرسية رقم {index}",
            message="رسالة حول جودة التدريس والخدمات الإلكترونية ومتابعة تجربة المستخدم.",
            teaching_quality_rating=(index % 5) + 1,
            electronic_services_rating=((index + 2) % 5) + 1,
            status=("new", "review", "resolved")[index % 3],
            response="تمت المتابعة من الإدارة." if index % 3 == 2 else "",
        ) for index in range(1, 13)
    ])
    BroadcastMessage.objects.bulk_create([
        BroadcastMessage(
            message_type="circular", audience=audience, title=title, message=message,
            created_by=user, recipients_count=count, is_active=True,
        ) for audience, title, message, count in (
            ("teachers", "تعميم للمعلمين", "يرجى متابعة الجدول والتكليفات اليومية.", len(teachers)),
            ("parents", "تعميم لأولياء الأمور", "يرجى متابعة الحضور والنتائج من البوابة.", len(families)),
            ("all", "تعميم عام", "نرحب بجميع مستخدمي نظام أوبال.", len(teachers) + len(families) + 1),
        )
    ])
    WorkflowRequest.objects.bulk_create([
        WorkflowRequest(
            request_type=("document" if index % 2 else "student"),
            title=f"طلب متابعة رقم {index}", description="طلب مدرسي قيد المتابعة",
            requester=user, school=school, branch=branch,
            status=("new", "review", "approved")[index % 3], priority=("normal", "high")[index % 2],
        ) for index in range(1, 21)
    ])
    ReportPreset.objects.bulk_create([
        ReportPreset(name="تقرير الطلاب", category="students", code="students-overview", is_active=True, created_by=user),
        ReportPreset(name="تقرير التحصيل", category="finance", code="finance-overview", is_active=True, created_by=user),
        ReportPreset(name="تقرير الحضور", category="attendance", code="attendance-overview", is_active=True, created_by=user),
    ])

    # School-linked learning-platform demo identities/content.  Parents and
    # teachers enter by ERP SSO; each child keeps a distinct learner identity.
    from learning_platform.models import (
        LearningAccessSettings, LearningCourse, LearningLesson, LearningSubscriptionCard, LearningSubscriptionPlan,
    )
    from learning_platform.card_codes import generate_unique_card_codes
    from learning_platform.school_bridge import (
        ensure_student_learning_account, ensure_teacher_learning_account, ensure_learning_subject_for_academic_subject,
    )

    LearningAccessSettings.objects.update_or_create(
        school=school, defaults={"parent_default_enabled": True, "teacher_sso_enabled": True}
    )
    learning_teacher_by_id = {teacher.pk: ensure_teacher_learning_account(teacher) for teacher in teachers}
    learning_student_by_id = {student.pk: ensure_student_learning_account(student) for student in students}
    learning_subject_by_academic_id = {}
    for subject in [item for items in subjects_by_grade.values() for item in items]:
        learning_subject_by_academic_id[subject.pk] = ensure_learning_subject_for_academic_subject(subject)

    course_rows = []
    for assignment in assignments:
        course_rows.append(LearningCourse(
            subject=learning_subject_by_academic_id[assignment.subject_id],
            teacher=learning_teacher_by_id[assignment.teacher_id],
            title=f"{assignment.subject.name} — {assignment.section}",
            slug=f"school-course-{assignment.pk}",
            summary=f"محتوى تجريبي مترابط لمادة {assignment.subject.name} حسب التكليف الرسمي للمعلم والشعبة.",
            grade_label=assignment.section.grade.name,
            academic_subject=assignment.subject, academic_section=assignment.section,
            status=LearningCourse.Status.PUBLISHED, published_at=timezone.now(),
        ))
    LearningCourse.objects.bulk_create(course_rows, batch_size=500)
    school_courses = list(LearningCourse.objects.filter(slug__startswith="school-course-").select_related("academic_subject", "academic_section"))
    LearningLesson.objects.bulk_create([
        LearningLesson(
            course=course, title=f"الدرس {lesson_no}: {course.academic_subject.name}",
            slug=f"lesson-{lesson_no}",
            content=f"محتوى تجريبي مترابط للدرس {lesson_no} في {course.academic_subject.name} للشعبة {course.academic_section}.",
            duration_minutes=20 + lesson_no * 5, order=lesson_no, is_published=True,
        )
        for course in school_courses for lesson_no in (1, 2)
    ], batch_size=1000)
    LearningSubscriptionPlan.objects.create(
        name="الخطة المدرسية السنوية", slug="school-yearly-demo",
        duration=LearningSubscriptionCard.Duration.YEARLY, price=Decimal("10.000"),
        currency="JOD", grants_all_subjects=True, is_active=True, display_order=1,
    )
    now_learning = timezone.now()
    demo_card_codes = generate_unique_card_codes(len(students), prefix="DEMO")
    LearningSubscriptionCard.objects.bulk_create([
        LearningSubscriptionCard(
            code=demo_card_codes[index - 1], duration=LearningSubscriptionCard.Duration.YEARLY,
            grants_all_subjects=True,
            status=(LearningSubscriptionCard.Status.REDEEMED if index <= 250 else LearningSubscriptionCard.Status.AVAILABLE),
            redeemed_by=(learning_student_by_id[student.pk] if index <= 250 else None),
            activated_at=(now_learning if index <= 250 else None),
            expires_at=(now_learning + timedelta(days=365) if index <= 250 else None),
        )
        for index, student in enumerate(students, 1)
    ], batch_size=1000)

    family_size_counts = Counter(
        FamilyStudent.objects.filter(family__school=school, is_active=True)
        .values_list("family_id", flat=True)
    )
    distribution = Counter(family_size_counts.values())
    if distribution != Counter({1: 50, 2: 50, 3: 50, 4: 50}):
        raise ValueError(f"توزيع الإخوة غير مطابق لعقد R29: {dict(distribution)}")
    if FeePayment.objects.filter(school=school, scope="all_siblings", is_deleted=False).count() != 200:
        raise ValueError("يجب أن يمتلك كل ولي أمر إيصال دفعة عائلية واحدًا على الأقل.")
    if len(school_courses) != len(assignments) or LearningLesson.objects.filter(course__in=school_courses).count() != len(school_courses) * 2:
        raise ValueError("محتوى منصة التعلم التجريبي غير مترابط مع جميع تكليفات المعلمين.")

    academic_demo = _validate_integrated_academic_demo(
        school=school,
        year=year,
        sections=sections,
    )
    return {
        "students": Student.objects.count(), "teachers": Teacher.objects.count(),
        "families": Family.objects.count(), "sections": len(sections),
        "years": school.academic_years.count(), "semesters": year.semesters.count(),
        "marks": StudentMark.objects.count(), "documents": IssuedDocument.objects.count(),
        "receipts": Receipt.objects.count() + FeePayment.objects.count(),
        "learning_accounts": len(learning_teacher_by_id) + len(learning_student_by_id),
        "learning_courses": len(school_courses),
        "learning_lessons": len(school_courses) * 2,
        "password": DEFAULT_ACCOUNT_PASSWORD,
        **academic_demo,
    }

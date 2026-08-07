"""Read-only operational integration audit for the OPAL management centre."""

from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Q


def _issue(code, label, count, description, route, *, severity="warning"):
    return {
        "code": code,
        "label": label,
        "count": int(count or 0),
        "description": description,
        "route": route,
        "severity": "success" if not count else severity,
    }


def build_operation_audit():
    from academics.models import Enrollment, Subject
    from accounting.models import StudentInvoice
    from admissions.models import StudentRegistration
    from core.models import AcademicYear, School
    from attendance_v2.models import Attendance
    from exams.models import Exam, StudentMark
    from parent_portal.models import Family
    from students.models import Student
    from teachers.models import Teacher, TeacherAssignment
    from timetable.models import TimetableEntry

    active_students = Student.objects.filter(is_active=True)
    active_teachers = Teacher.objects.filter(is_active=True)
    active_assignments = TeacherAssignment.objects.filter(is_active=True)
    active_entries = TimetableEntry.objects.filter(is_active=True)
    active_subject_plans = Subject.objects.filter(is_active=True)

    students_without_enrollment = active_students.exclude(
        enrollments__status="active"
    ).distinct().count()
    students_without_family = active_students.exclude(
        family_links__is_active=True
    ).distinct().count()
    families_without_children = Family.objects.filter(
        is_active=True
    ).annotate(active_children=Count("children", filter=Q(children__is_active=True))).filter(active_children=0).count()
    registrations_without_student = StudentRegistration.objects.filter(student__isnull=True).count()
    registrations_without_invoice = StudentRegistration.objects.filter(invoice__isnull=True).count()
    active_teachers_without_assignment = active_teachers.exclude(assignments__is_active=True).distinct().count()
    active_teachers_without_account = active_teachers.filter(user__isnull=True).count()
    active_families_without_account = Family.objects.filter(
        is_active=True, user__isnull=True, children__is_active=True
    ).distinct().count()
    active_enrollments_without_section = Enrollment.objects.filter(status="active", section__isnull=True).count()
    schools_without_current_year = School.objects.filter(is_active=True).exclude(
        academic_years__is_current=True
    ).distinct().count()
    current_years_without_current_semester = AcademicYear.objects.filter(
        is_current=True
    ).exclude(semesters__is_current=True).distinct().count()

    matching_entries = TimetableEntry.objects.filter(
        teacher_id=OuterRef("teacher_id"),
        academic_year_id=OuterRef("academic_year_id"),
        section_id=OuterRef("section_id"),
        subject_id=OuterRef("subject_id"),
        is_active=True,
    )
    assignments_without_timetable = active_assignments.annotate(
        has_timetable=Exists(matching_entries)
    ).filter(has_timetable=False).count()

    matching_assignments = TeacherAssignment.objects.filter(
        teacher_id=OuterRef("teacher_id"),
        academic_year_id=OuterRef("academic_year_id"),
        section_id=OuterRef("section_id"),
        subject_id=OuterRef("subject_id"),
        is_active=True,
    )
    timetable_without_assignment = active_entries.filter(teacher__isnull=False).annotate(
        has_assignment=Exists(matching_assignments)
    ).filter(has_assignment=False).count()

    subject_plan_assignment = TeacherAssignment.objects.filter(
        academic_year_id=OuterRef("academic_year_id"),
        subject_id=OuterRef("pk"),
        section__grade_id=OuterRef("grade_id"),
        is_active=True,
    )
    subject_plan_without_assignment = active_subject_plans.annotate(
        has_assignment=Exists(subject_plan_assignment)
    ).filter(has_assignment=False).count()

    subject_plan_timetable = TimetableEntry.objects.filter(
        academic_year_id=OuterRef("academic_year_id"),
        subject_id=OuterRef("pk"),
        section__grade_id=OuterRef("grade_id"),
        is_active=True,
    )
    subject_plan_without_timetable = active_subject_plans.annotate(
        has_timetable=Exists(subject_plan_timetable)
    ).filter(has_timetable=False).count()

    attendance_without_academic_context = Attendance.objects.filter(
        Q(academic_year__isnull=True) | Q(grade__isnull=True) | Q(section__isnull=True)
    ).count()
    invoices_without_year = StudentInvoice.objects.filter(academic_year__isnull=True).count()

    published_exams = Exam.objects.filter(status="published", is_active=True)
    published_exams_without_marks = published_exams.annotate(mark_count=Count("marks")).filter(mark_count=0).count()
    marks_without_enterer = StudentMark.objects.filter(entered_by__isnull=True).count()

    issues = [
        _issue("CURRENT_YEAR", "مدارس دون عام دراسي حالي", schools_without_current_year, "يجب تحديد عام حالي لكل مدرسة نشطة قبل التسجيل والجدول والحضور والعلامات.", "academics:academic_year_list", severity="danger"),
        _issue("CURRENT_SEMESTER", "أعوام حالية دون فصل حالي", current_years_without_current_semester, "حدد الفصل الجاري حتى تتوحد التقارير والعمليات اليومية.", "academics:semester_list"),
        _issue("STUDENT_ENROLLMENT", "طلاب دون قيد أكاديمي نشط", students_without_enrollment, "كل طالب نشط يجب أن يرتبط بقيد واحد في العام الحالي.", "academics:lifecycle_list", severity="danger"),
        _issue("STUDENT_FAMILY", "طلاب دون ملف ولي أمر", students_without_family, "بطاقة الطالب والبوابة والإشعارات تعتمد على رابط الأسرة الرسمي.", "parent_portal:family_management", severity="danger"),
        _issue("EMPTY_FAMILY", "ملفات أولياء أمور دون أبناء", families_without_children, "راجع الملفات الفارغة أو اربطها بالطالب الصحيح.", "parent_portal:family_management"),
        _issue("REGISTRATION_STUDENT", "تسجيلات غير مرتبطة بطالب", registrations_without_student, "عملية التسجيل يجب أن تنتهي بإنشاء students.Student الرسمي.", "admissions:admission_list", severity="danger"),
        _issue("REGISTRATION_INVOICE", "تسجيلات دون رسوم مرتبطة", registrations_without_invoice, "التسجيل الفعلي يجب أن ينشئ الرسم المدرسي المرتبط.", "admissions:admission_list", severity="danger"),
        _issue("ENROLLMENT_SECTION", "قيود نشطة دون شعبة", active_enrollments_without_section, "القيد النشط يحتاج شعبة حتى يعمل الجدول والحضور وقائمة المعلم بصورة صحيحة.", "academics:lifecycle_list", severity="danger"),
        _issue("TEACHER_ACCOUNT", "معلمون نشطون دون حساب دخول", active_teachers_without_account, "حساب المعلم مطلوب للوصول إلى الجدول والحضور والعلامات والواجبات.", "teachers:dashboard"),
        _issue("FAMILY_ACCOUNT", "أسر لها أبناء دون حساب ولي أمر", active_families_without_account, "أنشئ حسابًا موحدًا للأسرة ليصل ولي الأمر إلى جميع أبنائه.", "parent_portal:family_management"),
        _issue("TEACHER_ASSIGNMENT", "معلمون نشطون دون تكليف", active_teachers_without_assignment, "التكليف هو المصدر الذي يربط المعلم بالمادة والشعبة والجدول والعلامات.", "teachers:dashboard"),
        _issue("ASSIGNMENT_TIMETABLE", "تكليفات غير ممثلة في الجدول", assignments_without_timetable, "شغّل منشئ الجدول أو أضف الحصص حتى يطابق الجدول التكليفات.", "timetable:dashboard"),
        _issue("TIMETABLE_ASSIGNMENT", "حصص دون تكليف مطابق", timetable_without_assignment, "لا ينبغي أن توجد حصة لمعلم خارج تكليفه الأكاديمي.", "timetable:dashboard", severity="danger"),
        _issue("SUBJECT_PLAN_ASSIGNMENT", "مواد خطة دون تكليف معلم", subject_plan_without_assignment, "كل مادة فعالة في خطة العام تحتاج تكليفًا في شعب الصف قبل إنشاء الجدول.", "academics:subject_list"),
        _issue("SUBJECT_PLAN_TIMETABLE", "مواد خطة غير ممثلة في الجدول", subject_plan_without_timetable, "راجع المواد والتكليفات ثم افتح قسم إنشاء أو تحديث الجدول.", "timetable:dashboard"),
        _issue("ATTENDANCE_CONTEXT", "حضور ناقص السياق الأكاديمي", attendance_without_academic_context, "سجل الحضور يجب أن يحمل العام والصف والشعبة لسلامة التقارير.", "attendance_v2:report"),
        _issue("INVOICE_YEAR", "رسوم دون عام دراسي", invoices_without_year, "ربط الرسم بالعام ضروري للإغلاق والترحيل والتقارير.", "accounting:dashboard"),
        _issue("PUBLISHED_EXAM_MARKS", "امتحانات منشورة بلا علامات", published_exams_without_marks, "لا تنشر الامتحان قبل اكتمال العلامات ومراجعتها.", "exams:exam_list"),
        _issue("MARK_ENTERER", "علامات دون مسجل معروف", marks_without_enterer, "وجود المستخدم المسجل ضروري للمساءلة وسجل العمليات.", "exams:exam_list"),
    ]

    total_checks = len(issues)
    passed_checks = sum(1 for item in issues if item["count"] == 0)
    health_percent = round((passed_checks / total_checks) * 100) if total_checks else 100
    if health_percent >= 90:
        health_label, health_class = "تكامل قوي", "success"
    elif health_percent >= 70:
        health_label, health_class = "تكامل جيد مع ملاحظات", "warning"
    else:
        health_label, health_class = "يحتاج معالجة", "danger"

    return {
        "integration_issues": issues,
        "integration_total_checks": total_checks,
        "integration_passed_checks": passed_checks,
        "integration_health_percent": health_percent,
        "integration_health_label": health_label,
        "integration_health_class": health_class,
        "integration_open_issues": sum(item["count"] for item in issues),
        "integration_counts": {
            "students": active_students.count(),
            "teachers": active_teachers.count(),
            "enrollments": Enrollment.objects.filter(status="active").count(),
            "assignments": active_assignments.count(),
            "timetable_entries": active_entries.count(),
            "subject_plan_items": active_subject_plans.count(),
        },
    }

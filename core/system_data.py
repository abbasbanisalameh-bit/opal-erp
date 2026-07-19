from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.utils import timezone


DEFAULT_ACCOUNT_PASSWORD = "Opal@12345"


def _delete_all(model):
    count = model.objects.count()
    model.objects.all().delete()
    return count


@transaction.atomic
def reset_all_operational_data(*, keep_user=None):
    """Delete all school-operational records while preserving system access/config."""
    from academics.models import Enrollment, Grade, Section, StudentDocument, StudentLifecycleEvent, Subject
    from accounting.models import (
        DiscountRequest, ExpenseEntry, FeeCategory, FinancialCarryForward,
        FinancialYearClosure, Installment, MonthlyFinancialTarget, Receipt,
        StudentInvoice, StudentPayment,
    )
    from admissions.models import (
        AdmissionApplication, FeePayment, FeePaymentAllocation, GradeFee,
        RegistrationSettings, StudentRegistration, TransportRoute,
    )
    from announcements.models import Announcement
    from attendance_v2.models import Attendance
    from core.models import AcademicYear, AuditLog, Branch, DataIntegrityRun, Sequence
    from curriculum.models import Curriculum
    from development_center.models import ActivityLog, Bug, Decision, Idea, Module, Notification as DevelopmentNotification, Release, Sprint
    from documents.models import DocumentSettings, DocumentTemplate, IssuedDocument, StudentIssuedDocument
    from enterprise_ops.models import ApprovalAction, Notification, ReportPreset, WorkflowRequest
    from exams.models import Exam, StudentMark
    from openemis_integration.models import OpenEMISSyncLog
    from parent_portal.models import Family, FamilyStudent
    from students.models import Student
    from teachers.models import Homework, Teacher, TeacherAssignment, TeacherDocument
    from timetable.models import (
        ClassCoverage, SchoolDayEvent, SchoolScheduleSettings, TeacherAbsence,
        TimeSlot, TimetableEntry,
    )

    counts = {
        "students": Student.objects.count(), "teachers": Teacher.objects.count(),
        "families": Family.objects.count(), "documents": IssuedDocument.objects.count(),
        "receipts": Receipt.objects.count() + FeePayment.objects.count(),
    }

    # Protected and transactional financial chains are removed from leaf to root.
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

    _delete_all(StudentMark)
    _delete_all(Exam)
    _delete_all(Attendance)
    _delete_all(ClassCoverage)
    _delete_all(TeacherAbsence)
    _delete_all(TimetableEntry)
    _delete_all(SchoolDayEvent)
    _delete_all(SchoolScheduleSettings)
    _delete_all(TimeSlot)

    _delete_all(Homework)
    _delete_all(TeacherAssignment)
    _delete_all(TeacherDocument)
    _delete_all(Teacher)
    _delete_all(FamilyStudent)
    _delete_all(Family)

    _delete_all(StudentLifecycleEvent)
    _delete_all(StudentDocument)
    _delete_all(Enrollment)
    _delete_all(Student)
    _delete_all(Curriculum)

    _delete_all(AdmissionApplication)
    _delete_all(GradeFee)
    _delete_all(TransportRoute)
    _delete_all(RegistrationSettings)
    _delete_all(Section)
    _delete_all(Subject)
    _delete_all(Grade)
    _delete_all(AcademicYear)
    _delete_all(Branch)

    _delete_all(ApprovalAction)
    _delete_all(WorkflowRequest)
    _delete_all(Notification)
    _delete_all(ReportPreset)
    _delete_all(Announcement)
    _delete_all(OpenEMISSyncLog)
    _delete_all(Module)
    _delete_all(Sprint)
    _delete_all(Release)
    _delete_all(Idea)
    _delete_all(Decision)
    _delete_all(Bug)
    _delete_all(ActivityLog)
    _delete_all(DevelopmentNotification)
    _delete_all(DataIntegrityRun)
    _delete_all(AuditLog)
    _delete_all(Sequence)

    # Preserve every superuser so the installation never locks its owner out.
    removable_users = User.objects.filter(is_superuser=False)
    if keep_user and keep_user.pk:
        removable_users = removable_users.exclude(pk=keep_user.pk)
    counts["users"] = removable_users.count()
    removable_users.delete()
    return counts


def _guardian_index(student_index):
    # A varied but exact 500-student/300-guardian distribution:
    # 150 guardians with one student, 100 with two, and 50 with three.
    if student_index <= 150:
        return student_index, 0
    if student_index <= 350:
        relative = student_index - 151
        return 151 + (relative // 2), relative % 2
    relative = student_index - 351
    return 251 + (relative // 3), relative % 3


def _relation_for(guardian_index, child_position):
    category = (guardian_index - 1) % 6
    if category == 0:
        return "والد"
    if category == 1:
        return "والدة"
    if category == 2:
        return "عم ووصي"
    if category == 3:
        return "الأخ الأكبر"
    if category == 4:
        return "والد" if child_position == 0 else "عم ووصي"
    return "جد وولي"


def _month_28(base_date, offset):
    value = (base_date.year * 12 + base_date.month - 1) + offset
    return date(value // 12, value % 12 + 1, 28)


def _structure(school):
    from academics.models import Grade, Section, Subject
    from admissions.models import GradeFee, RegistrationSettings, TransportRoute
    from core.models import AcademicYear, Branch
    from documents.models import DocumentSettings
    from timetable.models import SchoolDayEvent, SchoolScheduleSettings, TimeSlot

    branch = Branch.objects.create(
        school=school, name="الفرع الرئيسي", phone="065555555",
        address="عمّان", is_main=True, is_active=True,
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
    subjects = [
        "اللغة العربية", "الرياضيات", "العلوم", "اللغة الإنجليزية",
        "التربية الإسلامية", "الحاسوب",
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
    for grade in grades:
        for section_name in ("أ", "ب"):
            sections.append(Section(
                academic_year=year, branch=branch, grade=grade,
                name=section_name, capacity=30, is_active=True,
            ))
        for index, subject_name in enumerate(subjects, 1):
            subject_rows.append(Subject(
                grade=grade, name=subject_name,
                code=f"G{grade.order:02d}-S{index:02d}", is_active=True,
            ))
    Section.objects.bulk_create(sections)
    Subject.objects.bulk_create(subject_rows)
    sections = list(Section.objects.filter(academic_year=year).select_related("grade").order_by("grade__order", "name"))
    subjects_by_grade = {
        grade.pk: list(Subject.objects.filter(grade=grade).order_by("name")) for grade in grades
    }

    slots = []
    for index, (hour, minute) in enumerate(((8, 0), (8, 50), (9, 40), (10, 40), (11, 30), (12, 20), (13, 10)), 1):
        start = time(hour, minute)
        end = (timezone.datetime.combine(date.today(), start) + timedelta(minutes=45)).time()
        slots.append(TimeSlot(name=f"الحصة {index}", start_time=start, end_time=end, order=index, is_active=True))
    TimeSlot.objects.bulk_create(slots)
    SchoolScheduleSettings.objects.create(school=school, weekend_days="thursday,friday", alert_minutes_before_end=5)
    SchoolDayEvent.objects.bulk_create([
        SchoolDayEvent(school=school, name="الطابور الصباحي", event_type="assembly", start_time=time(7, 40), end_time=time(7, 55), order=1),
        SchoolDayEvent(school=school, name="الاستراحة", event_type="break", start_time=time(10, 25), end_time=time(10, 40), order=2),
        SchoolDayEvent(school=school, name="نهاية الدوام", event_type="dismissal", start_time=time(13, 55), end_time=time(14, 5), order=3),
    ])
    RegistrationSettings.objects.create(school=school, first_payment_percent=20)
    TransportRoute.objects.bulk_create([
        TransportRoute(school=school, name=name, full_fee=amount, is_active=True)
        for name, amount in (("مسار عمّان الشرقية", 350), ("مسار عمّان الغربية", 400), ("مسار الجبيهة", 300), ("مسار شفا بدران", 325))
    ])
    DocumentSettings.objects.create(
        school=school, manager_name="مدير مدرسة أوبال", manager_title="المدير العام", stamp_label="ختم المدرسة",
    )
    return branch, year, grades, sections, subjects_by_grade


@transaction.atomic
def seed_system_data(*, student_count=500, teacher_count=50, guardian_count=300, user=None):
    from accounts.models import Role, UserProfile
    from academics.models import Enrollment, StudentDocument
    from accounting.models import (
        ExpenseEntry, FeeCategory, MonthlyFinancialTarget, Receipt,
        StudentInvoice, StudentPayment,
    )
    from admissions.models import AdmissionApplication, FeePayment, FeePaymentAllocation, StudentRegistration
    from announcements.models import Announcement
    from attendance_v2.models import Attendance
    from core.models import School
    from curriculum.models import Curriculum
    from documents.defaults import DEFAULT_DOCUMENT_TEMPLATES
    from documents.models import DocumentTemplate, IssuedDocument, StudentIssuedDocument
    from enterprise_ops.models import Notification, ReportPreset, WorkflowRequest
    from exams.models import Exam, StudentMark
    from parent_portal.models import Family, FamilyStudent
    from students.models import Student
    from teachers.models import Homework, Teacher, TeacherAssignment, TeacherDocument
    from timetable.models import TimetableEntry
    from timetable.services import build_smart_timetable

    # The button intentionally produces one stable, complete acceptance dataset.
    student_count, teacher_count, guardian_count = 500, 50, 300
    School.objects.select_for_update().filter(is_active=True).first()
    reset_all_operational_data(keep_user=user)
    school = School.objects.filter(is_active=True).first()
    if school is None:
        school = School.objects.create(
            name="مدرسة أوبال الدولية", official_name="مدرسة أوبال الدولية",
            phone="065555555", email="info@opal-school.edu", address="عمّان", is_active=True,
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

    account_rows = []
    for index in range(1, teacher_count + 1):
        *_, name = generated_name(index, female=index % 2 == 0)
        account_rows.append(User(username=f"teacher_{index:03d}", password=password_hash, first_name=name, email=f"teacher{index:03d}@opal-school.edu", is_active=True))
    for index in range(1, guardian_count + 1):
        category = (index - 1) % 6
        *_, name = generated_name(index, female=category == 1)
        account_rows.append(User(username=f"guardian_{index:03d}", password=password_hash, first_name=name, is_active=True))
    User.objects.bulk_create(account_rows)
    teacher_users = {row.username: row for row in User.objects.filter(username__startswith="teacher_")}
    guardian_users = {row.username: row for row in User.objects.filter(username__startswith="guardian_")}

    specializations = ["لغة عربية", "رياضيات", "علوم", "لغة إنجليزية", "تربية إسلامية", "حاسوب"]
    teacher_rows = []
    for index in range(1, teacher_count + 1):
        *_, full_name = generated_name(index, female=index % 2 == 0)
        teacher_rows.append(Teacher(
            user=teacher_users[f"teacher_{index:03d}"], employee_number=f"T-{index:04d}",
            source="manual", ministry_teacher_id=f"MIN-T-{index:05d}", full_name=full_name,
            national_id=f"2000{index:06d}", gender="male" if index % 2 else "female",
            birth_date=date(1980 + index % 20, (index % 12) + 1, (index % 27) + 1),
            phone=f"078{index:07d}", email=f"teacher{index:03d}@opal-school.edu",
            address=f"عمّان - الحي {index % 10 + 1}", specialization=specializations[(index - 1) % len(specializations)],
            qualification="بكالوريوس تربية", hire_date=date(2020 + index % 5, 9, 1),
            school=school, branch=branch, monthly_salary=Decimal("550") + index * Decimal("8"),
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

    relation_labels = ["والد", "والدة", "عم ووصي", "الأخ الأكبر", "وصي على أبناء وأبناء أخ", "جد وولي"]
    family_rows = []
    for index in range(1, guardian_count + 1):
        category = (index - 1) % 6
        *_, name = generated_name(index, female=category == 1)
        family_rows.append(Family(
            school=school, user=guardian_users[f"guardian_{index:03d}"], source="manual",
            guardian_name=name, relation=relation_labels[category], identity_type="national",
            identity_number=f"3000{index:06d}", phone=f"079{index:07d}",
            secondary_phone=f"077{index:07d}", email=f"guardian{index:03d}@mail.com",
            job_title=("مهندسة" if category == 1 else "موظف"), address=f"عمّان - منطقة {index % 15 + 1}",
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

    # Assign teachers, homerooms, curricula, and generate a conflict-free timetable.
    assignment_rows, curriculum_rows = [], []
    for section_index, section in enumerate(sections):
        section.homeroom_teacher = teachers[section_index % len(teachers)]
        section.save(update_fields=["homeroom_teacher"])
        for subject_index, subject in enumerate(subjects_by_grade[section.grade_id]):
            weekly = (3, 3, 2, 2, 2, 2)[subject_index]
            teacher = teachers[(section_index * 7 + subject_index) % len(teachers)]
            assignment_rows.append(TeacherAssignment(
                teacher=teacher, academic_year=year, section=section, subject=subject,
                weekly_periods=weekly, is_primary=True, is_active=True,
            ))
    for grade in grades:
        for subject_index, subject in enumerate(subjects_by_grade[grade.pk]):
            curriculum_rows.append(Curriculum(
                academic_year=year, grade=grade, subject=subject,
                weekly_periods=(3, 3, 2, 2, 2, 2)[subject_index], is_required=True, is_active=True,
            ))
    TeacherAssignment.objects.bulk_create(assignment_rows)
    Curriculum.objects.bulk_create(curriculum_rows)
    plan = build_smart_timetable(academic_year=year, apply=False, replace_generated=True)
    TimetableEntry.objects.bulk_create([
        TimetableEntry(
            academic_year=year, section=row["assignment"].section, subject=row["assignment"].subject,
            teacher=row["assignment"].teacher, day=row["day"], time_slot=row["time_slot"],
            room=f"R-{row['assignment'].section_id:03d}", is_active=True, generated_automatically=True,
        ) for row in plan["plan"]
    ])
    assignments = list(TeacherAssignment.objects.select_related("teacher", "section", "subject").filter(academic_year=year))
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
        first_name, father_name, grandfather_name, family_name, full_name = generated_name(index, female=index % 2 == 0)
        number = f"STU-{index:05d}"
        student_rows.append(Student(
            student_number=number, source="manual", national_id=f"1000{index:06d}",
            ministry_student_id=f"MIN-S-{index:06d}", full_name=full_name,
            guardian_name=family.guardian_name, father_name=f"{father_name} {grandfather_name} {family_name}",
            mother_name=f"{female_names[(index + 2) % len(female_names)]} {family_name}",
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
            relation=_relation_for(int(meta["family"].family_code.split("-")[1]), meta["position"]), is_active=True,
        ))
    Enrollment.objects.bulk_create(enrollment_rows)
    FamilyStudent.objects.bulk_create(link_rows)

    category = FeeCategory.objects.create(name="الرسوم المدرسية", description="رسوم العام الدراسي الحالي", amount=Decimal("1200"), active=True)
    invoice_rows, payment_amounts = [], {}
    methods = ("cash", "card", "bank_transfer", "electronic", "cheque")
    for student in students:
        meta = student_meta[student.student_number]
        total = Decimal("900") + meta["section"].grade.order * Decimal("75")
        ratio = (Decimal("0"), Decimal("0.20"), Decimal("0.50"), Decimal("0.80"), Decimal("1.00"))[(meta["index"] - 1) % 5]
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

    FeePayment.objects.bulk_create([
        FeePayment(
            school=school, receipt_number=f"FEE-{payment.invoice.student.student_number}",
            scope="single", main_student=payment.invoice.student,
            guardian_name=payment.invoice.student.guardian_name, phone=payment.invoice.student.phone,
            total_amount=payment.amount, total_due_before=payment.invoice.amount,
            total_due_after=payment.invoice.amount - payment.amount,
            payment_method=payment.payment_method, created_by=user,
        ) for payment in payments
    ])
    fee_payments = {row.main_student_id: row for row in FeePayment.objects.filter(school=school)}
    FeePaymentAllocation.objects.bulk_create([
        FeePaymentAllocation(
            fee_payment=fee_payments[payment.invoice.student_id], student=payment.invoice.student,
            invoice=payment.invoice, accounting_payment=payment, amount=payment.amount,
            total_fees=payment.invoice.amount, paid_before=0,
            remaining_before=payment.invoice.amount, remaining_after=payment.invoice.amount - payment.amount,
        ) for payment in payments
    ])

    # Ten days of attendance with present/absent/late/departed variety.
    attendance_rows = []
    today = timezone.localdate()
    enrollment_by_student = {row.student_id: row for row in Enrollment.objects.filter(academic_year=year).select_related("grade", "section")}
    for student in students:
        enrollment = enrollment_by_student[student.pk]
        for offset in range(10):
            marker = (student.pk + offset) % 20
            status = "absent" if marker == 0 else ("late" if marker in (1, 2) else ("departed" if marker == 3 else "present"))
            attendance_rows.append(Attendance(
                student=student, academic_year=year, grade=enrollment.grade, section=enrollment.section,
                date=today - timedelta(days=offset), status=status,
                arrival_time=time(8, 10) if status == "late" else None,
                departure_time=time(12, 30) if status == "departed" else None,
                recorded_by=user, updated_by=user,
            ))
    Attendance.objects.bulk_create(attendance_rows, batch_size=1000)

    # Four assessments per subject in both semesters, with marks for every student.
    exam_rows = []
    for grade in grades:
        for subject in subjects_by_grade[grade.pk]:
            for semester in year.semesters.all():
                for exam_type, maximum in Exam.MAX_MARKS.items():
                    exam_rows.append(Exam(
                        name=f"{dict(Exam.EXAM_TYPES)[exam_type]} - {subject.name}",
                        exam_type=exam_type, academic_year=year, semester=semester,
                        grade=grade, subject=subject, max_mark=maximum, weight=maximum,
                        pass_percentage=60, exam_date=today, status="published", is_locked=True, is_active=True,
                    ))
    Exam.objects.bulk_create(exam_rows)
    exams = list(Exam.objects.filter(academic_year=year).select_related("grade", "subject", "semester"))
    students_by_grade = {}
    for enrollment in Enrollment.objects.filter(academic_year=year).select_related("student"):
        students_by_grade.setdefault(enrollment.grade_id, []).append(enrollment.student)
    mark_rows = []
    for exam in exams:
        maximum = int(exam.max_mark)
        for student in students_by_grade.get(exam.grade_id, []):
            deduction = (student.pk + exam.subject_id + (1 if exam.semester.code == "first" else 3)) % max(2, maximum // 2)
            mark_rows.append(StudentMark(exam=exam, student=student, mark=Decimal(maximum - deduction), entered_by=user))
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

    candidate_rows = []
    for index in range(1, 31):
        family = families[(index - 1) % len(families)]
        grade = grades[(index - 1) % len(grades)]
        candidate_rows.append(AdmissionApplication(
            school=school, branch=branch, academic_year=year,
            application_number=f"ADM-{index:05d}", student_full_name=f"مرشح {male_names[index % len(male_names)]} {family_names[index % len(family_names)]}",
            gender="male" if index % 2 else "female", guardian_name=family.guardian_name,
            guardian_phone=family.phone, grade=grade, status="candidate", notes="بانتظار استكمال التسجيل",
        ))
    AdmissionApplication.objects.bulk_create(candidate_rows)

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

    return {
        "students": Student.objects.count(), "teachers": Teacher.objects.count(),
        "families": Family.objects.count(), "sections": len(sections),
        "years": school.academic_years.count(), "semesters": year.semesters.count(),
        "marks": StudentMark.objects.count(), "documents": IssuedDocument.objects.count(),
        "receipts": Receipt.objects.count() + FeePayment.objects.count(),
        "timetable_entries": TimetableEntry.objects.count(),
        "password": DEFAULT_ACCOUNT_PASSWORD,
    }

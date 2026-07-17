from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone


DEMO_PREFIX = "[تجريبي]"


def _structure():
    from academics.models import Grade, Section, Subject
    from admissions.models import GradeFee
    from core.models import AcademicYear, Branch, School, Semester
    from timetable.models import TimeSlot

    school = School.objects.filter(is_active=True).first() or School.objects.create(name="OPAL School")
    branch = school.branches.filter(is_active=True, is_main=True).first()
    if branch is None:
        branch = school.branches.filter(is_active=True).first()
    if branch is None:
        branch = Branch.objects.create(school=school, name="الفرع الرئيسي", is_main=True)

    year = school.academic_years.filter(is_current=True, is_closed=False).first() or school.academic_years.filter(
        is_closed=False
    ).order_by("-start_date").first()
    if year is None:
        start_year = date.today().year
        while school.academic_years.filter(name=f"{start_year}/{start_year + 1}").exists():
            start_year += 1
        year = AcademicYear.objects.create(
            school=school,
            name=f"{start_year}/{start_year + 1}",
            start_date=date(start_year, 9, 1),
            midyear_break_start=date(start_year + 1, 1, 16),
            midyear_break_end=date(start_year + 1, 1, 31),
            end_date=date(start_year + 1, 6, 30),
            is_current=True,
        )
    year.ensure_semesters()

    grade_names = ["الصف الأول", "الصف الثاني", "الصف الثالث", "الصف الرابع", "الصف الخامس"]
    subject_names = ["اللغة العربية", "الرياضيات", "العلوم", "اللغة الإنجليزية", "التربية الإسلامية"]
    grades, sections, subjects_by_grade = [], [], {}
    for order, grade_name in enumerate(grade_names, 1):
        grade, _ = Grade.objects.get_or_create(school=school, name=grade_name, defaults={"order": order, "is_active": True})
        grades.append(grade)
        GradeFee.objects.get_or_create(
            school=school, academic_year=year, grade=grade,
            defaults={"tuition_fee": Decimal("900") + Decimal(order * 100), "is_active": True},
        )
        grade_sections = []
        for section_name in ("أ", "ب"):
            section, _ = Section.objects.get_or_create(
                academic_year=year, branch=branch, grade=grade, name=section_name,
                defaults={"capacity": 30, "is_active": True},
            )
            grade_sections.append(section)
            sections.append(section)
        subjects_by_grade[grade.pk] = []
        for index, subject_name in enumerate(subject_names, 1):
            subject, _ = Subject.objects.get_or_create(
                grade=grade, name=subject_name,
                defaults={"code": f"DEMO-G{order}-S{index}", "is_active": True},
            )
            subjects_by_grade[grade.pk].append(subject)

    slots = []
    starts = [(8, 0), (8, 50), (9, 40), (10, 40), (11, 30)]
    for index, (hour, minute) in enumerate(starts, 1):
        start = time(hour, minute)
        end_dt = timezone.datetime.combine(date.today(), start) + timedelta(minutes=45)
        slot, _ = TimeSlot.objects.get_or_create(
            name=f"الحصة {index}", defaults={"start_time": start, "end_time": end_dt.time(), "order": index, "is_active": True}
        )
        slots.append(slot)
    return school, branch, year, grades, sections, subjects_by_grade, slots


@transaction.atomic
def seed_demo_school(*, student_count=100, teacher_count=20, user=None):
    from academics.models import Enrollment, StudentDocument
    from admissions.services import create_student_registration
    from attendance_v2.models import Attendance
    from documents.models import DocumentTemplate, IssuedDocument, StudentIssuedDocument
    from exams.models import Exam, StudentMark
    from students.models import Student
    from teachers.account_services import create_teacher_account
    from teachers.models import Teacher, TeacherAssignment, TeacherDocument
    from timetable.models import TimetableEntry

    student_count = max(1, min(int(student_count), 500))
    teacher_count = max(1, min(int(teacher_count), 100))
    school, branch, year, grades, sections, subjects_by_grade, slots = _structure()

    first_names = ["أحمد", "محمد", "عمر", "يوسف", "سارة", "مريم", "ليان", "نور", "خالد", "تالا"]
    family_names = ["الحداد", "الخطيب", "النجار", "العلي", "العبادي", "العمري", "الزعبي", "المصري", "الرفاعي", "الشامي"]
    specializations = ["لغة عربية", "رياضيات", "علوم", "لغة إنجليزية", "تربية إسلامية"]

    teachers = []
    for index in range(1, teacher_count + 1):
        teacher, created = Teacher.objects.get_or_create(
            employee_number=f"DEMO-T-{index:03d}",
            defaults={
                "full_name": f"المعلم التجريبي {first_names[index % len(first_names)]} {family_names[index % len(family_names)]}",
                "national_id": f"DEMO-T-NID-{index:04d}", "gender": "male" if index % 2 else "female",
                "phone": f"0787{index:06d}", "email": f"demo.teacher{index}@opal.test",
                "specialization": specializations[(index - 1) % len(specializations)], "qualification": "بكالوريوس تربية",
                "hire_date": date(2024, 9, 1), "school": school, "branch": branch,
                "monthly_salary": Decimal("550") + Decimal(index * 12), "is_active": True, "is_demo": True,
            },
        )
        if not teacher.is_demo:
            continue
        if created or not teacher.user_id:
            try:
                create_teacher_account(teacher, f"demo_teacher_{index:03d}")
            except ValueError:
                pass
        TeacherDocument.objects.get_or_create(
            teacher=teacher, document_type="contract", title="عقد عمل تجريبي",
            defaults={"document_number": f"DEMO-CONTRACT-{index:03d}", "issue_date": date(2024, 9, 1)},
        )
        TeacherDocument.objects.get_or_create(
            teacher=teacher, document_type="qualification", title="شهادة البكالوريوس",
            defaults={"document_number": f"DEMO-QUAL-{index:03d}", "issue_date": date(2023, 6, 15)},
        )
        teachers.append(teacher)

    if teachers:
        for section_index, section in enumerate(sections):
            subject_rows = subjects_by_grade[section.grade_id]
            for subject_index, subject in enumerate(subject_rows):
                teacher = teachers[(section_index * 2 + subject_index) % len(teachers)]
                TeacherAssignment.objects.get_or_create(
                    teacher=teacher, academic_year=year, section=section, subject=subject,
                    defaults={"is_primary": True, "is_active": True},
                )
            if not section.homeroom_teacher_id:
                section.homeroom_teacher = teachers[section_index % len(teachers)]
                section.save(update_fields=["homeroom_teacher"])

        if len(teachers) >= 10:
            days = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
            for section_index, section in enumerate(sections):
                subject_rows = subjects_by_grade[section.grade_id]
                for day_index, day_name in enumerate(days):
                    for slot_index, slot in enumerate(slots):
                        subject_index = (day_index + slot_index + section_index) % len(subject_rows)
                        subject = subject_rows[subject_index]
                        teacher = teachers[(section_index * 2 + subject_index) % len(teachers)]
                        TimetableEntry.objects.get_or_create(
                            academic_year=year, section=section, day=day_name, time_slot=slot,
                            defaults={"subject": subject, "teacher": teacher, "room": f"R-{section_index + 1:02d}", "is_active": True},
                        )

    students = []
    for index in range(1, student_count + 1):
        national_id = f"DEMO-STU-NID-{index:05d}"
        existing = Student.objects.filter(national_id=national_id, is_demo=True).first()
        if existing:
            students.append(existing)
            continue
        section = sections[(index - 1) % len(sections)]
        family_index = (index + 1) // 2
        first = first_names[(index - 1) % len(first_names)]
        family_name = family_names[(family_index - 1) % len(family_names)]
        cleaned = {
            "first_name": first, "father_name": "محمود", "grandfather_name": "أحمد", "family_name": family_name,
            "national_id": national_id, "gender": "male" if index % 2 else "female", "birth_date": date(2017, 1, 1),
            "photo": None, "guardian_name": f"محمود {family_name}", "guardian_identity_type": "national", "guardian_identity_number": f"DEMO-P-NID-{family_index:04d}",
            "mother_name": f"أم {first}", "phone": f"0798{family_index:06d}", "address": "عمان - عنوان تجريبي",
            "grade": section.grade, "section": section, "transport_route": None, "transport_type": "none",
            "discount_type": "none", "admin_discount_value": Decimal("0"), "sibling_student": None,
            "first_payment": Decimal("250"), "notes": f"{DEMO_PREFIX} سجل مولد لاختبار النظام",
        }
        registration = create_student_registration(SimpleNamespace(cleaned_data=cleaned), user)
        registration.student.is_demo = True
        registration.student.save(update_fields=["is_demo"])
        students.append(registration.student)

    today = timezone.localdate()
    attendance_rows = []
    for student in students:
        enrollment = Enrollment.objects.filter(student=student, status="active").select_related("grade", "section").first()
        if not enrollment:
            continue
        for offset in range(5):
            day = today - timedelta(days=offset)
            attendance_rows.append(Attendance(
                student=student, academic_year=year, grade=enrollment.grade, section=enrollment.section,
                date=day, status="absent" if (student.pk + offset) % 13 == 0 else ("late" if (student.pk + offset) % 9 == 0 else "present"),
                recorded_by=user, updated_by=user,
            ))
    Attendance.objects.bulk_create(attendance_rows, ignore_conflicts=True)

    for grade in grades:
        grade_students = [s for s in students if s.enrollments.filter(academic_year=year, grade=grade).exists()]
        for subject in subjects_by_grade[grade.pk]:
            for semester in year.semesters.order_by("code"):
                for exam_index, (exam_type, maximum) in enumerate(Exam.MAX_MARKS.items(), 1):
                    exam, _ = Exam.objects.get_or_create(
                        academic_year=year,
                        semester=semester,
                        grade=grade,
                        subject=subject,
                        exam_type=exam_type,
                        defaults={
                            "name": f"{DEMO_PREFIX} {dict(Exam.EXAM_TYPES)[exam_type]} - {subject.name}",
                            "pass_percentage": 60,
                            "exam_date": today,
                            "status": "published",
                            "is_locked": True,
                            "is_active": True,
                        },
                    )
                    marks = []
                    max_int = int(maximum)
                    for student in grade_students:
                        score = Decimal(max(0, max_int - ((student.pk + subject.pk + exam_index) % max(2, max_int // 2))))
                        marks.append(StudentMark(exam=exam, student=student, mark=score, entered_by=user))
                    StudentMark.objects.bulk_create(marks, ignore_conflicts=True)


    template, _ = DocumentTemplate.objects.get_or_create(
        name=f"{DEMO_PREFIX} إثبات طالب", defaults={"document_type": "student_certificate", "title": "إثبات طالب تجريبي", "body": "وثيقة تجريبية", "is_active": True}
    )
    for index, student in enumerate(students, 1):
        StudentDocument.objects.get_or_create(student=student, document_type="birth_certificate", title="شهادة ميلاد - بيانات تجريبية")
        number = f"DEMO-DOC-{student.pk:06d}"
        issued, _ = IssuedDocument.objects.get_or_create(
            document_number=number,
            defaults={"template": template, "student": student, "applicant_name": student.full_name,
                      "title": "إثبات طالب تجريبي", "content": f"الطالب {student.full_name} مسجل في {student.grade}", "issued_by": user},
        )
        StudentIssuedDocument.objects.get_or_create(student=student, issued_document=issued)

    return {"students": len(students), "teachers": len(teachers), "families": len({s.phone for s in students}), "sections": len(sections)}


@transaction.atomic
def reset_demo_school():
    from accounting.models import Receipt, StudentInvoice, StudentPayment
    from admissions.models import StudentRegistration
    from documents.models import IssuedDocument
    from exams.models import Exam
    from parent_portal.models import Family, FamilyStudent
    from students.models import Student
    from teachers.models import Teacher
    from timetable.models import TimetableEntry

    students = Student.objects.filter(is_demo=True)
    student_ids = list(students.values_list("pk", flat=True))
    family_ids = list(FamilyStudent.objects.filter(student_id__in=student_ids).values_list("family_id", flat=True).distinct())
    family_user_ids = list(Family.objects.filter(pk__in=family_ids).exclude(user_id=None).values_list("user_id", flat=True))
    invoices = StudentInvoice.objects.filter(student_id__in=student_ids)
    payments = StudentPayment.objects.filter(invoice__in=invoices)
    Receipt.objects.filter(payment__in=payments).delete()
    payments.delete()
    StudentRegistration.objects.filter(student_id__in=student_ids).delete()
    IssuedDocument.objects.filter(document_number__startswith="DEMO-DOC-").delete()
    invoices.delete()
    deleted_students = students.count()
    students.delete()
    Family.objects.filter(pk__in=family_ids, children__isnull=True).delete()

    teachers = Teacher.objects.filter(is_demo=True)
    teacher_user_ids = list(teachers.exclude(user_id=None).values_list("user_id", flat=True))
    TimetableEntry.objects.filter(teacher__in=teachers).delete()
    deleted_teachers = teachers.count()
    teachers.delete()
    from django.contrib.auth.models import User
    User.objects.filter(pk__in=family_user_ids + teacher_user_ids).delete()
    Exam.objects.filter(name__startswith=DEMO_PREFIX).delete()
    return {"students": deleted_students, "teachers": deleted_teachers, "families": len(family_ids)}

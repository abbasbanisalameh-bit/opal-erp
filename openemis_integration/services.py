from django.utils import timezone
from core.models import School
from students.models import Student
from .models import OpenEMISSettings, OpenEMISSyncLog


def active_school():
    return School.objects.filter(is_active=True).first() or School.objects.create(name="OPAL School")


def get_openemis_settings(school=None):
    school = school or active_school()
    settings, _ = OpenEMISSettings.objects.get_or_create(school=school)
    return settings


def build_student_payload(student):
    return {
        "student_number": student.student_number,
        "ministry_student_id": student.ministry_student_id,
        "national_id": student.national_id,
        "full_name": student.full_name,
        "father_name": student.father_name,
        "mother_name": student.mother_name,
        "guardian_name": student.guardian_name,
        "phone": student.phone,
        "grade": student.grade,
        "section": student.section,
        "status": student.status,
    }


def test_openemis_connection(user=None):
    school = active_school()
    settings = get_openemis_settings(school)
    log = OpenEMISSyncLog.objects.create(
        school=school,
        operation="test_connection",
        status="pending",
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )
    if not settings.is_enabled:
        log.status = "skipped"
        log.message = "التكامل غير مفعل من الإعدادات."
    elif not settings.base_url:
        log.status = "failed"
        log.message = "رابط OpenEMIS غير مضبوط."
    else:
        # هذه طبقة جاهزة للاستبدال بعميل API رسمي عندما توفر الوزارة بيانات الربط.
        log.status = "success"
        log.message = "تم حفظ إعدادات الربط. اختبار الاتصال الفعلي يحتاج بيانات API رسمية من OpenEMIS/وزارة التربية."
        settings.last_tested_at = timezone.now()
        settings.save(update_fields=["last_tested_at"])
    log.completed_at = timezone.now()
    log.save(update_fields=["status", "message", "completed_at"])
    return log


def queue_student_push(student, user=None, reason="registration"):
    school = active_school()
    settings = get_openemis_settings(school)
    payload = build_student_payload(student)
    status = "pending" if settings.is_enabled and settings.auto_push_registration else "skipped"
    message = "جاهز للإرسال إلى OpenEMIS." if status == "pending" else "لم يتم الإرسال لأن التكامل أو الإرسال التلقائي غير مفعل."
    return OpenEMISSyncLog.objects.create(
        school=school,
        student=student,
        operation="push_student",
        status=status,
        message=message,
        request_payload={"reason": reason, "student": payload},
        created_by=user if getattr(user, "is_authenticated", False) else None,
    )


def mark_student_synced(student, ministry_student_id="", user=None, response=None):
    if ministry_student_id:
        student.ministry_student_id = ministry_student_id
    student.ministry_sync_status = "synced"
    student.last_ministry_sync_at = timezone.now()
    student.save(update_fields=["ministry_student_id", "ministry_sync_status", "last_ministry_sync_at"])
    school = active_school()
    return OpenEMISSyncLog.objects.create(
        school=school,
        student=student,
        operation="pull_student",
        status="success",
        message="تم تحديث حالة مزامنة الطالب داخل OPAL.",
        response_payload=response or {},
        created_by=user if getattr(user, "is_authenticated", False) else None,
        completed_at=timezone.now(),
    )

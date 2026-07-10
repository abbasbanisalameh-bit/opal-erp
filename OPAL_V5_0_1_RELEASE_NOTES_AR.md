# OPAL ERP V5.0.1 — Stability Update

## الإصلاحات

- إصلاح صفحة جدول ولي الأمر `/parent/timetable/`.
- معالجة التعارض بين `core.AcademicYear` المستخدم في التسجيل و`academics.AcademicYear` المستخدم في جدول الحصص، بالمطابقة الآمنة حسب اسم العام الدراسي.
- إصلاح تصفية امتحانات بوابة المعلم؛ لأن `Exam` يستخدم `core.AcademicYear` بينما تكليف المعلم يستخدم `academics.AcademicYear`.
- قصر طلاب الحضور والعلامات في بوابة المعلم على العام الدراسي المطابق للتكليف، وليس الشعبة فقط.
- الإبقاء على جميع روابط مركز التطوير الفرعية للمدير.
- لا توجد نماذج جديدة ولا تغييرات على نموذج الطالب الرسمي `students.Student`.

## التحقق المنفذ

- `python manage.py check` — ناجح.
- `python manage.py makemigrations --check --dry-run` — لا توجد تغييرات غير منشأة.
- `python manage.py migrate --noinput` — ناجح على نسخة العمل.
- `python manage.py collectstatic --noinput` — ناجح.
- `python -m compileall parent_portal teachers` — ناجح.
- التحقق من عكس مسارات بوابة ولي الأمر والمعلم — ناجح.

## الملفات البرمجية المعدلة

- `parent_portal/views.py`
- `teachers/views.py`

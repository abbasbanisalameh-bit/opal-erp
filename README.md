# OPAL ERP Update 69 — Cards Consolidation

راجع `OPAL_UPDATE_69_RELEASE_NOTES_AR.md` و`OPAL_UPDATE_MANIFEST.json`.

# OPAL ERP Update 57 — Complete Timetable Workflow Reengineering

راجع `OPAL_TIMETABLE_WORKFLOW_REENGINEERING_57_AR.md` و`OPAL_UPDATE_MANIFEST.json`.

# OPAL ERP

## التزام مداخل البيانات

كل بيانات التشغيل تدخل من شاشة OPAL رسمية واحدة فقط، ولا تستخدم لوحة Django Admin للتشغيل اليومي. الاستثناء الوحيد هو استيراد الطالب من OpenEMIS، حيث تدمج البيانات مع سجل `students.Student` الرسمي ولا تنشئ طالبًا مكررًا. التفاصيل في `docs/OPAL_DATA_ENTRY_COMMITMENT_AR.md`.

نظام إدارة مدرسة مبني على Django. النموذج الرسمي والوحيد للطالب هو
`students.Student`، والمصدر المالي الحي هو الفواتير والدفعات والإيصالات.

## الوحدات الإنتاجية

- الطلاب وملفات أولياء الأمور والتسجيل.
- الأكاديميات والمعلمون والحضور والجدول والامتحانات.
- الرسوم والتسديد الموحد والإيصالات والمصروفات والكشوف المالية الشهرية.
- الوثائق والإعلانات وبوابة ولي الأمر.
- اللوحة والتقارير والصلاحيات والسجل والإشعارات.

## الوحدات التأسيسية القابلة للضبط

- OpenEMIS ظاهر كأساس تكاملي، لكنه لا يصبح ربطًا وزاريًا إنتاجيًا قبل توفير API رسمي وبيانات اعتماد صحيحة.
- مركز التطوير باقٍ ومتاح ولا تُحذف مهامه؛ ويمكن تعطيل أي وحدة تأسيسية فقط بقرار صريح عبر متغيرات البيئة دون حذف كودها.
- دليل العمليات الموحد يعرض المكان الرسمي لكل إجراء، ويمنع إنشاء مداخل تشغيلية مكررة.

## فحص المشروع

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test
python manage.py collectstatic --noinput
python manage.py verify_core_readiness --allow-empty
# بعد إعداد بيانات التشغيل الفعلية:
python manage.py verify_core_readiness
```

تعليمات التركيب الحالية في
`INSTALL_OPAL_OPERATION_FLOW_UNIFICATION_V1_AR.md`، وسجل التغيير في
`OPAL_OPERATION_FLOW_UNIFICATION_V1_RELEASE_NOTES_AR.md`. الوثائق التاريخية
محفوظة داخل المشروع للرجوع إليها.

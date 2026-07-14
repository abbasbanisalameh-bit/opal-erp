# OPAL ERP

## التزام مداخل البيانات

كل بيانات التشغيل تدخل من شاشة OPAL رسمية واحدة فقط، ولا تستخدم لوحة Django Admin للتشغيل اليومي. الاستثناء الوحيد هو استيراد الطالب من OpenEMIS، حيث تدمج البيانات مع سجل `students.Student` الرسمي ولا تنشئ طالبًا مكررًا. التفاصيل في `docs/OPAL_DATA_ENTRY_COMMITMENT_AR.md`.

نظام إدارة مدرسة مبني على Django. النموذج الرسمي والوحيد للطالب هو
`students.Student`، والمصدر المالي الحي هو الفواتير والدفعات والإيصالات.

## الوحدات الإنتاجية

- الطلاب والأسرة والتسجيل.
- الأكاديميات والمعلمون والحضور والجدول والامتحانات.
- الرسوم والدفعات والإيصالات والأقساط والخصومات.
- الوثائق والإعلانات وبوابة ولي الأمر.
- اللوحة والتقارير والصلاحيات والسجل والإشعارات.

## الوحدات الاختيارية المفصولة

- OpenEMIS محفوظ كأساس فقط ومخفي افتراضيًا. تفعيله يحتاج
  `OPAL_ENABLE_OPENEMIS=True` وبيانات API رسمية.
- مركز التطوير غير مثبت ولا مكشوف في موقع المدرسة افتراضيًا. لتشغيله في موقع
  خاص استخدم `config.settings_development` أو `config.wsgi_development`.

## فحص المشروع

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test
python manage.py collectstatic --noinput
python manage.py verify_core_readiness --allow-empty
```

تعليمات التركيب الكاملة في `INSTALL_OPAL_SAFE_CONSOLIDATION_AR.md`، وسجل
التغيير في `OPAL_SAFE_CONSOLIDATION_RELEASE_NOTES_AR.md`. الوثائق التاريخية
محفوظة داخل `docs/archive/`.

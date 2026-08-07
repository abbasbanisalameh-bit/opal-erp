# تقرير تحقق OPAL Update 131.7 R25

## الهوية

- الإصدار: `131.7`
- اسم الإصدار: `OPAL Update 131.7 R25 - Core Test Stability and Legacy Contract Fix`
- خط الأساس: R24
- نوع الحزمة: `code_only`
- مراجعة الحزمة: `28`
- لا توجد هجرة قاعدة بيانات جديدة.

## الإصلاحات

- تحديث عقد R14 المتقادم ليتحقق من عدم وجود نماذج موازية بدل تثبيت عدد هجرات المنصة.
- جعل اختبارات النسخ والاستعادة التي تستخدم مجلدات مؤقتة تتحمل أخطاء تنظيف نظام الملفات غير الوظيفية على PythonAnywhere/Python 3.13.
- منع هجرة R24 التاريخية من خفض هوية R25 أو أي إصدار أحدث أثناء إنشاء قاعدة اختبار.

## التحقق الساكن

- بوابة المصدر: `330/330` ناجحة.
- ملفات Python المحللة: `633`.
- أخطاء تركيب Python: صفر.
- تحذيرات: صفر.

## التحقق المطلوب على PythonAnywhere

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
core.tests_system_updates.DatabaseSafetySnapshotTests \
core.test_update131_7_r14_learning_platform_content_management_contract \
core.test_update131_7_r25_core_test_stability_legacy_contract \
--settings=config.settings_test_low_memory --verbosity 1 --noinput
```

لا يُعتمد التحديث قبل نجاح الاختبارات التشغيلية على الخادم.

# تقرير تحقق OPAL Update 131.7 R27

## نطاق الإصلاح

يعالج R27 اختبار تنزيل وحذف النسخ الاحتياطية الذي كان يغلق استجابة `FileResponse` كاملة، فتُطلق إشارة `request_finished` ويُغلق اتصال قاعدة اختبار Django قبل طلب الحذف التالي.

## التحقق الساكن

- نجح تحليل جميع ملفات Python نحويًا.
- نجحت بوابة المصدر `tools/validate_opal_update_131_source.py`.
- تطابق `OPAL_RELEASE_NAME.txt` مع `OPAL_UPDATE_MANIFEST.json`.
- رقم مراجعة الحزمة: 30.
- لا توجد هجرة قاعدة بيانات جديدة.
- عدد ملفات شجرة المصدر: 1323.

## التحقق المطلوب على PythonAnywhere

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
core.tests_system_updates.BackupFileActionsTests.test_download_and_delete_version_file \
core.test_update131_7_r27_file_response_test_connection_fix_contract \
--settings=config.settings_test_low_memory --verbosity 1 --noinput
```

بعد نجاح الاختبار المستهدف يجب تشغيل تطبيق `core` كاملًا بوضع الذاكرة المنخفضة. لم تُشغّل اختبارات Django داخل بيئة بناء الحزمة.

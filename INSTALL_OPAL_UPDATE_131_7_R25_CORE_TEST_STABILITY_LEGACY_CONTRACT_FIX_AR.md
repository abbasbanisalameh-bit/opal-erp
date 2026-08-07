# تركيب OPAL Update 131.7 R25

## Core Test Stability and Legacy Contract Fix

يُركّب هذا التحديث فوق R24. وهو تحديث اختبارات واستقرار فقط، ولا يغيّر بيانات المستخدمين أو الدورات أو الاشتراكات أو الصلاحيات.

## ما يعالجه

- تحديث عقد R14 المتقادم ليتحقق من عدم إنشاء نماذج مدرس/طالب موازية بدل افتراض بقاء هجرة واحدة فقط.
- منع أخطاء `OSError: Directory not empty` الناتجة عن تنظيف مجلدات اختبار مؤقتة بعد نجاح منطق النسخ والاستعادة.
- منع هجرة R24 التاريخية من تخفيض هوية R25 أو أي إصدار أحدث عند إنشاء قاعدة اختبار جديدة.
- لا توجد هجرة قاعدة بيانات جديدة.

## بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

## الاختبار المستهدف

```bash
python manage.py test \
core.tests_system_updates.DatabaseSafetySnapshotTests \
core.test_update131_7_r14_learning_platform_content_management_contract \
core.test_update131_7_r25_core_test_stability_legacy_contract \
--settings=config.settings_test_low_memory \
--verbosity 1 --noinput
```

بعد ظهور `OK` أعد اختبار `core` بوضع الذاكرة المنخفضة، ثم أكمل بقية التطبيقات.

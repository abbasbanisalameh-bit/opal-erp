# تثبيت OPAL Update 131.7 R35.3

هذا التحديث يصلح خطأ Flutter Analyze في لوحة الإدارة داخل تطبيق Android بعد R35.2.

## سبب الخطأ
في `mobile/opal_learning_app/lib/main.dart` كانت دالة `cards.map(...)` غير مغلقة بقوس واحد قبل `.toList()`، لذلك ظهرت أخطاء متسلسلة في السطور 441–451.

## التثبيت
ركّب ZIP من مركز تحديثات OPAL، ثم نفّذ:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py test core.test_update131_7_r35_3_flutter_manager_dashboard_syntax_hotfix_contract --settings=config.settings_test_low_memory --verbosity 1 --noinput
```

بعد ظهور `OK` ارفع التحديث إلى GitHub. تعديل ملفات الموبايل سيشغل `OPAL Android Build` تلقائيًا.

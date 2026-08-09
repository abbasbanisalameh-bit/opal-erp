# تقرير تحقق R35.2 — Manager Mobile SSO

## نتائج التحقق في بيئة البناء
- تحليل Python: **671 ملفًا**، أخطاء نحوية: **0**.
- فحوص عقد مصدر R35.2: **23/23 PASS**.
- تم التحقق من وجود نموذج رمز الإدارة المنفصل، Hash للرمز، إعادة فحص صلاحية الإدارة في كل طلب، واجهات الإدارة، وإعادة استخدام مولد بطاقات R33 المركزي.
- لا توجد مفاتيح خادم أو أسرار SMTP/Payment/Webhook مضمنة في `main.dart`.
- إصدار Flutter أصبح `1.2.0+37`.
- لا تحتوي الحزمة على `db.sqlite3` أو `.env` أو `media/` أو `staticfiles/` أو `__pycache__`.

## ما يتطلب بيئة PythonAnywhere / GitHub
بيئة البناء الحالية لا تحتوي Django أو Flutter SDK، ولذلك لا يمكن اعتماد اختبارات Django أو `flutter analyze/test/build` محليًا. يجب تشغيل اختبارات R35.2 على PythonAnywhere، ثم سيبني GitHub Actions الـAPK تلقائيًا بعد Push لأن ملفات الموبايل تغيرت.

## اختبارات الاعتماد المطلوبة

```bash
python manage.py test \
  core.test_update131_7_r35_2_manager_mobile_contract \
  learning_platform.test_update131_7_r35_2_manager_mobile \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

المتوقع: **10 tests / OK**.

ثم الاختبار الرجعي للموبايل:

```bash
python manage.py test \
  core.test_update131_7_r35_android_production_app_contract \
  core.test_update131_7_r35_1_flutter_radio_group_hotfix_contract \
  core.test_update131_7_r35_2_manager_mobile_contract \
  learning_platform.test_update131_7_r34_mobile_school_sso \
  learning_platform.test_update131_7_r35_2_manager_mobile \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

المتوقع: **20 tests / OK**.

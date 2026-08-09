# تقرير تحقق OPAL 131.7 R34

## تحقق المصدر المنفذ في بيئة البناء

```text
OPAL Update 131.7 static source gate
checks: 355
passed: 355
failed: 0
warnings: 0
python_files_parsed: 664
```

- `python -m compileall` نجح على Python الخاص بالتحديث.
- اختبارات عقد R34 التي لا تعتمد على Django: **5/5 ناجحة**.
- تمت مراجعة عدم تخزين fingerprint templates في Gateway.
- تمت مراجعة أن الدليل البيومتري لا يغيّر `TeacherAbsence` تلقائيًا.
- تمت مراجعة استخدام رمز مستقل لكل جهاز وتخزين SHA-256 فقط.
- تمت مراجعة أن Mobile School SSO يعتمد `django.contrib.auth.authenticate` ولا ينسخ كلمة مرور ERP إلى حساب التعلم.

## قيود بيئة البناء
- Django غير مثبت في بيئة البناء الحالية؛ لذلك اختبارات Django الثلاثة الخاصة بـR34 يجب تشغيلها على PythonAnywhere بعد التركيب.
- Flutter/Dart غير مثبتين في بيئة البناء؛ لذلك لم يتم تنفيذ `flutter analyze`, `flutter test` أو بناء APK/IPA هنا.
- تكامل جهاز بصمة مادي نهائيًا يعتمد على الشركة/الموديل والبروتوكول الفعلي. R34 يوفر Gateway عامًا وجسر ZKTeco؛ الأجهزة الأخرى قد تحتاج Adapter صغيرًا فقط.

## اختبارات الاعتماد المطلوبة على PythonAnywhere

```bash
python manage.py test \
  core.test_update131_7_r34_mobile_biometric_contract \
  learning_platform.test_update131_7_r34_mobile_school_sso \
  timetable.test_update131_7_r34_biometric_gateway \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

المتوقع: **10 tests** ثم `OK`.

## ملاحظة الجاهزية
R34 لم يمس شرط النسخة الاحتياطية، ولذلك يبقى هو المانع الرسمي الوحيد إذا لم تُنشأ نسخة متحققة حديثة.

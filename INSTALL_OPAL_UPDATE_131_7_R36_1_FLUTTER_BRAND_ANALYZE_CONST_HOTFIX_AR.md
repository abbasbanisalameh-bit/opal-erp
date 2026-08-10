# تثبيت OPAL Update 131.7 R36.1

هذا تحديث إصلاحي صغير بعد R36. يعالج فقط فشل `flutter analyze` الظاهر في GitHub Actions بسبب ست ملاحظات `prefer_const_constructors` داخل `CardThemeData`.

لا يغيّر الشعار أو الألوان أو الحسابات أو الصلاحيات أو قاعدة البيانات.

## بعد رفع ZIP من مركز تحديثات OPAL

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
  core.test_update131_7_r36_learning_mobile_branding_contract \
  core.test_update131_7_r36_1_flutter_brand_analyze_const_hotfix_contract \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

لا توجد Migration جديدة في R36.1. بعد نجاح الاختبارات ارفع الملفات المحددة في ملف `OPAL_UPDATE_131_7_R36_1_CHANGED_FILES.txt` إلى GitHub، وسيبدأ Android Build تلقائيًا.

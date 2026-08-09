# تركيب OPAL Update 131.7 R35.1 — Flutter RadioGroup Analyze Hotfix

هذا الإصلاح يعالج فشل GitHub Actions في خطوة `flutter analyze` بعد أن ألغى Flutter الحديث أسلوب إدارة الحالة عبر `groupValue` و`onChanged` داخل `RadioListTile`.

لا توجد هجرات قاعدة بيانات ولا تغيير على بيانات OPAL.

## بعد تركيب الحزمة

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
  core.test_update131_7_r35_android_production_app_contract \
  core.test_update131_7_r35_1_flutter_radio_group_hotfix_contract \
  learning_platform.test_update131_7_r34_mobile_school_sso \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

بعد نجاح الاختبارات:

```bash
git add -A
git commit -m "OPAL R35.1: Flutter RadioGroup analyze hotfix"
git push origin "$(git branch --show-current)"
```

سيعمل Workflow `OPAL Android Build` تلقائيًا بسبب تعديل ملفات التطبيق. لا تضغط Re-run للبناء القديم؛ استخدم تشغيل الـcommit الجديد.

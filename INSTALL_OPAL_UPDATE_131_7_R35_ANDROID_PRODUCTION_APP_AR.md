# تركيب OPAL R35 — Android Production App

هذا التحديث لا يغير قاعدة البيانات ولا يضيف Migration. يكمّل مشروع Flutter الموجود ويضيف بناء Android آليًا عبر GitHub Actions.

## بعد تركيب ZIP

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
  core.test_update131_7_r35_android_production_app_contract \
  learning_platform.test_update131_7_r34_mobile_school_sso \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

بعد ظهور `OK` ثبّت ملف GitHub Actions داخل المستودع (مركز التحديثات يحمي مجلد `.github` من الاستبدال المباشر):

```bash
python manage.py install_mobile_android_ci
```

ثم:

```bash
git add -A
git commit -m "OPAL R35: Android production app build pipeline"
git push origin "$(git branch --show-current)"
```

ثم افتح GitHub → Actions → OPAL Android Build → Run workflow.

PythonAnywhere لا يحتاج Flutter ولا Dart لبقاء OPAL يعمل؛ بناء APK يتم في GitHub Actions أو على جهاز تطوير Flutter.

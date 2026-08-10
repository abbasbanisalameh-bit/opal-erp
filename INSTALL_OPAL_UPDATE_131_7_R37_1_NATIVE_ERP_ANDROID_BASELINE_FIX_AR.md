# تثبيت OPAL Update 131.7 R37.1

هذا الإصدار يصحح R37 ليكون مبنيًا فوق R36.1، ويحافظ على إصلاح Flutter Analyze الخاص بتطبيق منصة أوبال، ويضيف تطبيق نظام OPAL ERP المستقل وAPI الخاص به.

بعد رفع ZIP من مركز التحديثات وتطبيقه:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test \
  core.test_update131_7_r36_1_flutter_brand_analyze_const_hotfix_contract \
  core.test_update131_7_r37_erp_mobile_app_contract \
  core.test_update131_7_r37_1_native_erp_baseline_fix_contract \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
python manage.py install_erp_mobile_android_ci
```

ثم تحقق من وجود المسارين:

```bash
ls -l .github/workflows/opal-android-build.yml
ls -l .github/workflows/opal-erp-android-build.yml
```

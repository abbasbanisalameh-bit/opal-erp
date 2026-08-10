# تركيب OPAL R37.2

هذا تحديث تصحيحي صغير فوق R37.1. يصلح اتساق اسم فهرس SystemMobileAPIToken بين النموذج والهجرة 0015، حتى لا يقترح Django هجرة RenameIndex جديدة أثناء فحص الجاهزية.

بعد التثبيت نفّذ:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py showmigrations core | tail -8
```

ثم اختبارات R37.2/R37.1/R37:

```bash
python manage.py test \
  core.test_update131_7_r37_erp_mobile_app_contract \
  core.test_update131_7_r37_1_native_erp_baseline_fix_contract \
  core.test_update131_7_r37_2_mobile_index_migration_consistency_contract \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

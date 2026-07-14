# تركيب OPAL ERP V10.3 — شريط الروابط الفرعية الثابت

هذه الحزمة تُركّب فوق V10.2.1 مباشرة، ولا تحتوي على migrations.

```bash
rm -rf /home/Opalschool2016/opal_v103_subnav_temp
mkdir -p /home/Opalschool2016/opal_v103_subnav_temp

unzip -o /home/Opalschool2016/OPAL_ERP_V10_3_STICKY_MODULE_NAV_PATCH_READY.zip \
-d /home/Opalschool2016/opal_v103_subnav_temp

rsync -av \
--exclude='db.sqlite3' --exclude='db.sqlite3-*' \
--exclude='media/' --exclude='staticfiles/' \
--exclude='.git/' --exclude='.env' \
--exclude='venv/' --exclude='.venv/' \
--exclude='__pycache__/' --exclude='*.pyc' \
/home/Opalschool2016/opal_v103_subnav_temp/ \
/home/Opalschool2016/opal_school/opal_school/

cd /home/Opalschool2016/opal_school/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

بعدها اضغط Reload من صفحة Web في PythonAnywhere.

لا تحفظ في GitHub قبل فحص الصفحات الرئيسية والفرعية.

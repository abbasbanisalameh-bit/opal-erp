# تركيب OPAL ERP V5.0.1 على PythonAnywhere

يجب فك الحزمة في مجلد مؤقت ثم نسخها باستخدام `rsync` مع استثناء قاعدة البيانات والوسائط وGit وملف البيئة.

```bash
rm -rf /home/Opalschool2016/opal_v501_temp
mkdir -p /home/Opalschool2016/opal_v501_temp
unzip -o /home/Opalschool2016/OPAL_ERP_V5_0_1_STABILITY_READY.zip -d /home/Opalschool2016/opal_v501_temp

rsync -av \
  --exclude='db.sqlite3' \
  --exclude='media/' \
  --exclude='staticfiles/' \
  --exclude='.git/' \
  --exclude='.env' \
  /home/Opalschool2016/opal_v501_temp/ \
  /home/Opalschool2016/opal_school/opal_school/

cd /home/Opalschool2016/opal_school/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

بعد نجاح الأوامر اضغط Reload من صفحة Web، ثم اختبر جدول ولي الأمر وبوابة المعلم.

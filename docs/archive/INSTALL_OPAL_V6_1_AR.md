# تركيب OPAL ERP V6.1 على PythonAnywhere

## قبل التركيب
احتفظ بنسخة مستقرة من المشروع وقاعدة البيانات.

## فك الضغط
```bash
rm -rf /home/Opalschool2016/opal_v61_temp
mkdir -p /home/Opalschool2016/opal_v61_temp
unzip -o /home/Opalschool2016/OPAL_ERP_V6_1_STUDENT360_FAMILY_FINANCE_READY.zip -d /home/Opalschool2016/opal_v61_temp
```

## النسخ إلى المشروع العامل
```bash
rsync -av \
--exclude='db.sqlite3' \
--exclude='media/' \
--exclude='staticfiles/' \
--exclude='.git/' \
--exclude='.env' \
/home/Opalschool2016/opal_v61_temp/ \
/home/Opalschool2016/opal_school/opal_school/
```

## الفحص
```bash
cd /home/Opalschool2016/opal_school/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

بعدها اضغط Reload من صفحة Web.

## اختبار سريع
1. الإدارة > الطلاب > زر 360°.
2. الإدارة > أولياء الأمور > فتح الملف.
3. جرّب كشف الحساب المطبوع والتصدير CSV.
4. جرّب إنشاء/إعادة تعيين حساب ولي الأمر.
5. تأكد أن بوابة ولي الأمر وبوابة المعلم ما زالتا تعملان.

# تركيب OPAL ERP V10.2 — Navigation Audit

## 1. فك الحزمة
```bash
rm -rf /home/Opalschool2016/opal_v102_navigation_temp
mkdir -p /home/Opalschool2016/opal_v102_navigation_temp
unzip -o /home/Opalschool2016/OPAL_ERP_V10_2_NAVIGATION_AUDIT_PATCH_READY.zip \
  -d /home/Opalschool2016/opal_v102_navigation_temp
```

## 2. نسخ التحديث إلى نسخة التشغيل
```bash
rsync -av \
  --exclude='db.sqlite3' \
  --exclude='media/' \
  --exclude='staticfiles/' \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  /home/Opalschool2016/opal_v102_navigation_temp/ \
  /home/Opalschool2016/opal_school/opal_school/
```

## 3. الفحص
```bash
cd /home/Opalschool2016/opal_school/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

لا توجد Migrations جديدة، لذلك لا يلزم `migrate` لهذا التحديث.

## 4. إعادة التحميل
اضغط **Reload** من صفحة Web في PythonAnywhere.

## 5. اختبار التنقل
- دخول المدير: تأكد من ترتيب الأقسام وعدم ظهور روابط التسجيل والدفع كروابط مستقلة في القائمة.
- افتح التسجيلات: يجب أن يبقى زر «تسجيل طالب جديد» داخل صفحة التسجيلات.
- افتح النظام المالي: يجب أن يبقى تسجيل الدفعة داخل الصفحة المالية.
- افتح بوابة ولي الأمر: يجب ألا يظهر شريط روابط ثانٍ داخل كل صفحة.
- دخول المعلم: يجب أن يظهر رابط واحد لبوابة المعلم، لا رابطان إلى الصفحة نفسها.
- افتح جرس الإشعارات من الشريط العلوي.
- افتح OpenEMIS ثم سجل المزامنة من داخل صفحة التكامل.

## 6. الحفظ في GitHub بعد نجاح الاختبار
انسخ نسخة التشغيل إلى مستودع Git ثم احفظ:
```bash
rsync -av \
  --exclude='.git/' \
  --exclude='db.sqlite3' \
  --exclude='media/' \
  --exclude='staticfiles/' \
  --exclude='.env' \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  /home/Opalschool2016/opal_school/opal_school/ \
  /home/Opalschool2016/rc_test/opal_school/opal_school/

cd /home/Opalschool2016/rc_test/opal_school/opal_school
git add -A
git commit -m "OPAL ERP V10.2 Navigation Audit and Deduplication"
git push origin opal-v7-development
git status
```

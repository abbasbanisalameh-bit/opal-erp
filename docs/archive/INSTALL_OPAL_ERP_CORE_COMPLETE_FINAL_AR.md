# تركيب OPAL ERP — CORE COMPLETE FINAL على PythonAnywhere

## 1. فك الحزمة

```bash
rm -rf /home/Opalschool2016/opal_core_complete_temp
mkdir -p /home/Opalschool2016/opal_core_complete_temp
unzip -o /home/Opalschool2016/OPAL_ERP_CORE_COMPLETE_FINAL_READY.zip \
-d /home/Opalschool2016/opal_core_complete_temp
```

## 2. نسخها إلى نسخة التشغيل

```bash
rsync -av \
--exclude='db.sqlite3' \
--exclude='db.sqlite3-*' \
--exclude='media/' \
--exclude='staticfiles/' \
--exclude='.git/' \
--exclude='.env' \
--exclude='venv/' \
--exclude='.venv/' \
--exclude='__pycache__/' \
--exclude='*.pyc' \
/home/Opalschool2016/opal_core_complete_temp/ \
/home/Opalschool2016/opal_school/opal_school/

# إزالة ملف طرفية قديم لا ينتمي إلى المشروع
rm -f /home/Opalschool2016/opal_school/opal_school/sions
```

## 3. الفحص والترحيل

```bash
cd /home/Opalschool2016/opal_school/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py test
python manage.py verify_core_readiness --allow-empty
```

عند وجود بيانات مدرسة فعلية استخدم فحص الجاهزية النهائي دون `--allow-empty`:

```bash
python manage.py verify_core_readiness
```


## إعدادات الإنتاج الآمنة
اضبط متغيرات البيئة في PythonAnywhere قبل التشغيل الفعلي:

```text
OPAL_SECRET_KEY=<مفتاح طويل وعشوائي>
OPAL_DEBUG=False
OPAL_SECURE_SSL_REDIRECT=True
OPAL_HSTS_SECONDS=3600
```

بعد التأكد من عمل HTTPS بصورة دائمة يمكن رفع `OPAL_HSTS_SECONDS` تدريجيًا.

## 4. إعادة تحميل الموقع
من صفحة **Web** في PythonAnywhere اضغط **Reload**.

## 5. الفحص التشغيلي قبل الحفظ في GitHub
- تسجيل طالب وإنشاء الأسرة والفاتورة والدفعة والإيصال.
- إضافة عام وفصل وصف وشعبة.
- تجربة نقل أو ترفيع طالب.
- إنشاء جدول والتأكد من رفض التعارض.
- تسجيل الحضور ثم إقفاله.
- إنشاء امتحان وإدخال العلامات واعتمادها ونشرها.
- إصدار وثيقة وتجربة رابط التحقق.
- إنشاء طلب خصم واعتماده.

## 6. الحفظ على GitHub بعد نجاح الفحص

```bash
rsync -av \
--exclude='.git/' --exclude='db.sqlite3' --exclude='db.sqlite3-*' \
--exclude='media/' --exclude='staticfiles/' --exclude='.env' \
--exclude='venv/' --exclude='.venv/' --exclude='__pycache__/' --exclude='*.pyc' \
/home/Opalschool2016/opal_school/opal_school/ \
/home/Opalschool2016/rc_test/opal_school/opal_school/

cd /home/Opalschool2016/rc_test/opal_school/opal_school
git add -A
git commit -m "OPAL ERP Core Complete Final"
git push origin opal-v7-development
git status
```

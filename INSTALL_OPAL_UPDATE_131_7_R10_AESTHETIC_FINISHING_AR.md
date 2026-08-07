# تركيب OPAL Update 131.7 R10

هذا تحديث كود تراكمي مبني فوق R9، ويضيف طبقة إنهاء جمالية وإتاحية فقط. لا يحتوي قاعدة بيانات أو وسائط أو أسرار، ولا يضيف هجرات أو نماذج أو مسارات تشغيلية.

## قبل التركيب

1. احفظ نسخة من الكود وقاعدة البيانات و`media/` وملف إعداد البيئة.
2. ثبّت الحزمة كاملة مع إبقاء `db.sqlite3` و`media/` و`.env` والبيئة الافتراضية خارج الاستبدال.
3. لا تنسخ ملفات الحزمة جزئيًا؛ هوية الأصول موحدة لمنع بقاء CSS أو JavaScript قديم في المتصفح.

## التحقق

```bash
cd /home/Opalschool2016/opal_school
source /home/Opalschool2016/.virtualenvs/opal/bin/activate
python tools/validate_opal_update_131_source.py .
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test
python manage.py collectstatic --clear --noinput
```

بعد نجاح الأوامر اضغط **Reload** من تبويب Web في PythonAnywhere، ثم افحص الوضعين الليلي والنهاري على سطح المكتب والهاتف، والتنقل بلوحة المفاتيح، والنماذج والجداول والطباعة.

## الرجوع

لا توجد هجرة بيانات في هذا التحديث. عند الحاجة استعد نسخة الكود السابقة، ثم نفذ `collectstatic --clear --noinput` وأعد تحميل الموقع.

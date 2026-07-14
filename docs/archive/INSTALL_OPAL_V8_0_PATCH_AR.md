# تركيب OPAL ERP V8.0 Patch

1. فك الحزمة في مجلد مؤقت.
2. انسخ الملفات إلى المشروع مع استثناء قاعدة البيانات وmedia وstaticfiles و.git و.env.
3. نفذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

4. أعد تحميل الموقع من صفحة Web في PythonAnywhere.
5. اختبر لوحة الامتحانات، إدخال العلامات، تفاصيل الامتحان، التصدير والسجل الأكاديمي.

# تركيب OPAL ERP V8.1

1. فك الحزمة في مجلد مؤقت.
2. انسخ الملفات إلى المشروع العامل مع استثناء قاعدة البيانات وmedia وstaticfiles و.env و.git.
3. نفذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

4. أعد تحميل الموقع من صفحة Web.
5. اختبر السجل الأكاديمي، كشف العلامات، إصدار الوثيقة، مركز الوثائق، وStudent 360.

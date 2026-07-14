# تركيب OPAL ERP V10.0

1. فك الحزمة في مجلد مؤقت.
2. انسخها إلى المشروع مع استثناء db.sqlite3 وmedia وstaticfiles و.git و.env.
3. نفذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

4. أعد تحميل الموقع من PythonAnywhere.
5. افتح `/enterprise/` بحساب المدير.

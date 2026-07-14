# تركيب OPAL ERP V7.3 Patch

1. فك الحزمة في مجلد مؤقت.
2. انسخ الملفات فوق المشروع مع استثناء db.sqlite3 وmedia وstaticfiles و.env و.git.
3. نفذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

4. أعد تحميل تطبيق الويب واختبر معاينة دفعة جميع الإخوة ثم الإيصال.

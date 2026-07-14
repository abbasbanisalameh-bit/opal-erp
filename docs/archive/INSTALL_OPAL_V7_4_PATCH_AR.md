# تركيب OPAL ERP V7.4

1. فك الحزمة في مجلد مؤقت.
2. انسخ الملفات إلى المشروع العامل باستخدام rsync مع استثناء قاعدة البيانات وmedia و.git.
3. نفذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

4. أعد تحميل الموقع واختبر طالبًا لديه `StudentRegistration.net_total` فعلي.

# تركيب OPAL ERP V5 على PythonAnywhere

1. خذ نسخة احتياطية من المشروع وقاعدة البيانات.
2. فك الملف في مجلد مؤقت.
3. انسخ بواسطة rsync مع استثناء: db.sqlite3 وmedia وstaticfiles و.git و.env.
4. نفذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check
```

5. اضغط Reload من صفحة Web.
6. من إدارة المعلمين، اربط كل معلم بحساب المستخدم المناسب في حقل «حساب المستخدم» ليتمكن من دخول بوابة المعلم.

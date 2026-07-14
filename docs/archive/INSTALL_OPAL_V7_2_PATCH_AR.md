# تركيب OPAL ERP V7.2 Parent 360 Patch

1. فك الملف في مجلد مؤقت.
2. انسخ محتويات الحزمة إلى جذر المشروع باستخدام rsync مع استثناء قاعدة البيانات وmedia وstaticfiles و.git و.env.
3. نفذ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

4. أعد تحميل الموقع من صفحة Web في PythonAnywhere.
5. ادخل بحساب ولي أمر وافتح Parent 360 من شريط بوابة ولي الأمر.

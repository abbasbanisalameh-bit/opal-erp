# تثبيت OPAL Update 131.6 R2 — إصلاح عقد لوحة المدير

## السبب
أوقف مركز التحديث الحزمة R1 لأن بوابة `opal.E136` كانت تبحث عن قواعد لوحة المدير داخل `static/css/opal_erp.css`، بينما القواعد موجودة بصورة صحيحة داخل ملفها المتخصص `static/css/opal_dashboard_executive.css`.

## التركيب
1. ارفع ملف ZIP الخاص بـ R2 فقط من مركز تحديثات النظام.
2. انتظر نجاح الفحص والهجرات التلقائية. لا توجد هجرات جديدة في هذه الحزمة.
3. اضغط «إعادة تحميل الموقع» مرة واحدة.
4. نفّذ في Bash:

```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update131_6_subject_ui_contract
python manage.py collectstatic --clear --noinput
```

## النتيجة المطلوبة

```text
System check identified no issues
No changes detected
OK
```

بعد ذلك افتح لوحة المدير وتحقق من شبكة المؤشرات المصغرة وألوان المواد في الأحداث الجارية والمعلمين المشغولين.

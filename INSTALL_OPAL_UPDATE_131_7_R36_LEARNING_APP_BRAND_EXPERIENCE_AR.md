# تثبيت OPAL Update 131.7 R36

هذا التحديث يطبق الهوية المعتمدة لمنصة أوبال التعليمية على نسخة الويب وتطبيق Android.

## بعد رفع ZIP من مركز تحديثات OPAL

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test core.test_update131_7_r36_learning_mobile_branding_contract --settings=config.settings_test_low_memory --verbosity 1 --noinput
python manage.py collectstatic --clear --noinput
```

لا توجد هجرة قاعدة بيانات جديدة في R36.

بعد نجاح الاختبار، ارفع الملفات إلى GitHub. تعديل `mobile/opal_learning_app/**` سيشغل بناء Android تلقائيًا.

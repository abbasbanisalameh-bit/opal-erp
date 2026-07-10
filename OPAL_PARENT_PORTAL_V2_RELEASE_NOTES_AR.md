# OPAL ERP V4.1 — Parent Portal Access Control

## ما تم تنفيذه
- حصر حساب ولي الأمر داخل `/parent/` فقط.
- إعادة توجيه ولي الأمر تلقائيًا من الصفحة الرئيسية أو أي شاشة إدارية إلى لوحة ولي الأمر.
- حجب `/admin/` والمحاسبة والطلاب والإعدادات ومركز التطوير وبقية وحدات الإدارة عن ولي الأمر.
- السماح فقط بمسارات تسجيل الدخول والخروج والملفات الثابتة والوسائط اللازمة لتشغيل البوابة.
- حماية جميع Views داخل `parent_portal` بديكور `parent_required`.
- اعتماد حساب الأسرة `Family.user` مع دعم `ParentProfile` القديم للتوافق.
- عدم تقييد الموظفين أو المديرين أو المستخدمين الفائقين.
- إضافة اختبارات آلية للصلاحيات الأساسية.

## قاعدة الوصول
حساب ولي الأمر هو مستخدم غير Staff وغير Superuser ومرتبط إما بـ `Family` أو `ParentProfile`.

## التثبيت
بعد استبدال الملفات وتشغيل البيئة:

```bash
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py test parent_portal.tests
```

ثم Reload للموقع من صفحة Web في PythonAnywhere.

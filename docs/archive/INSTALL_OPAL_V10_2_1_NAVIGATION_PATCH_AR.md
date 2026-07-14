# تركيب OPAL ERP V10.2.1 — تنظيم التنقل الهرمي

هذا التحديث يحافظ على جميع الروابط، ويعرض في القائمة الجانبية روابط الوحدات الرئيسية فقط، بينما تظهر الروابط الفرعية داخل الصفحة الرئيسية لكل وحدة.

لا توجد Migrations جديدة. شغّل بعد النسخ:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --noinput
```

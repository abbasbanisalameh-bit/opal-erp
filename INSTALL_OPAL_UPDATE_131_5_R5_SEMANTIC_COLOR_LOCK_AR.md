# تركيب OPAL Update 131.5 R5

1. ارفع ملف ZIP من مركز تحديثات النظام.
2. بعد نجاح التثبيت اضغط «إعادة تحميل الموقع».
3. نفذ:

```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update131_5_dashboard_layout_contract
python manage.py collectstatic --clear --noinput
```

4. افتح لوحة المدير بتحديث كامل للصفحة، ثم تحقق من ألوان بطاقات الشكاوى والتعاميم والإعلانات.

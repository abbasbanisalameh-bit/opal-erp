# تثبيت OPAL Update 131.6 R1 — استكمال لوحة المدير

1. ارفع ملف ZIP من مركز تحديثات النظام.
2. بعد نجاح الفحص والتركيب اضغط إعادة تحميل الموقع.
3. نفذ:

```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update131_6_subject_ui_contract
python manage.py collectstatic --clear --noinput
```

4. اختبر لوحة المدير على الهاتف:
   - المؤشرات الستة تظهر في شبكة من ثلاثة أعمدة دون تمرير أفقي.
   - بطاقات التواصل الثلاث تبقى في صف واحد.
   - لون المادة ظاهر في الأحداث الجارية وقائمة المعلمين المشغولين.

لا توجد هجرات أو تغييرات بيانات.

# تثبيت OPAL Update 131.7 R3

## الهدف
إصلاح تمدد صفحة بطاقة الطالب عرضيًا عند فتح تبويبات الأكاديمي والمالية والحضور والعلامات والوثائق والجدول.

## التثبيت
ارفع ملف ZIP فقط من مركز تحديثات النظام، ثم اضغط إعادة تحميل الموقع. لا توجد هجرات ولا تعديل على البيانات.

## التحقق على PythonAnywhere
```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update131_7_r3_student360_mobile_containment_contract
python manage.py collectstatic --clear --noinput
```

بعد ذلك افتح بطاقة طالب على الهاتف وجرّب جميع التبويبات. يجب أن يبقى عرض الصفحة ثابتًا، وأن يكون التمرير الأفقي داخل الجدول الواسع فقط عند الحاجة.

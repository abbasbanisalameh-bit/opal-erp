# OPAL ERP - نسخة موحدة الواجهة

## ما تم إنجازه

- توحيد الواجهة على قالب رئيسي واحد: `templates/base/base.html`.
- فصل القائمة الجانبية في: `templates/includes/sidebar.html`.
- الإبقاء على الشريط العلوي في: `templates/includes/topbar.html`.
- تحويل لوحة التحكم من صفحة HTML مستقلة إلى قالب Django يورّث من `base/base.html`.
- إضافة لوحة تحكم ديناميكية تعرض:
  - إجمالي الطلاب.
  - عدد المستخدمين الإداريين/المعلمين مؤقتاً.
  - الشعب الدراسية.
  - نسبة الحضور اليوم.
  - الرسوم المحصلة والمستحقات.
  - رسم الإيرادات الشهرية باستخدام Chart.js.
  - رسم حضور اليوم.
  - آخر الطلاب.
  - آخر الإعلانات والامتحانات.
- إصلاح صفحة قائمة الطلاب الأكاديمية وإزالة كسر جدول المالية.
- توحيد القوالب التي كانت تعتمد على `dashboard_base.html` لتستخدم `base/base.html`.
- إضافة مسار تقرير الحضور `/attendance/report/` لأنه كان مستخدماً في القوالب ولم يكن موجوداً في URLs.
- إصلاح فلترة تقرير الحضور لاستخدام العلاقة الصحيحة `student__enrollments`.
- إنشاء ملف متطلبات `requirements.txt`.

## خطوات التشغيل على PythonAnywhere

```bash
cd ~/opal_school/opal_school
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
touch /var/www/Opalschool2016_pythonanywhere_com_wsgi.py
```

## ملاحظة

لم يتم تشغيل `python manage.py check` داخل بيئة ChatGPT لأن Django غير مثبت في الحاوية، لكن تم فحص ملفات Python نحوياً باستخدام `compileall`.

# تركيب OPAL Update 131.7 R4.1

هذه الحزمة تصحح رفض R4 من بوابات `opal.E125` و`opal.E126` دون تغيير وظيفة متبقيات الرسوم السابقة.

## ما تم إصلاحه

- استخدام المصطلحات المدرسية: الرسوم، المدفوع، المتبقي، ومتبيقيات الرسوم السابقة.
- إزالة رابط الرسوم الموازي من صفحة الابن مع إبقاء التنبيه، والعودة إلى المدخل الوحيد في رئيسية ولي الأمر.
- إضافة فحص تجهيز مسبق يمنع بناء حزمة جديدة عند عودة أي من التعارضين.
- لا توجد هجرات أو تعديلات تلقائية على البيانات.

## بعد التركيب

```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update131_7_r4_previous_debt_contract accounting.test_previous_debt_services
python manage.py collectstatic --clear --noinput
```

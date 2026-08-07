# تثبيت OPAL Update 131.7 R1 — توافق عقد لوحة المدير

هذه الحزمة تصلح فشل `opal.E125 / executive_kpi_link_missing` الذي ظهر عند تركيب 131.7.

## السبب

صف المؤشرات الستة في 131.7 يستخدم روابط HTML صحيحة من نوع `opal-manager-quick-button`، لكن عقدًا قديمًا كان يقبل الرابط فقط عندما تبدأ أصناف CSS حرفيًا بـ `dashboard-card`. لذلك رفض الفحص واجهة صحيحة بسبب شكل CSS لا بسبب الوجهة.

## التركيب

1. ارفع ملف ZIP الخاص بـ R1 فقط من مركز تحديثات النظام.
2. انتظر اكتمال الفحص والاستعادة الآمنة.
3. اضغط إعادة تحميل الموقع مرة واحدة.
4. نفذ:

```bash
cd /home/Opalschool2016/opal_school
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core.test_update120_unified_ux_contract core.test_update126_school_finance_language_and_dashboard_links dashboard.test_update116_contract core.test_update131_7_fixed_manager_dashboard_contract
python manage.py collectstatic --clear --noinput
```

## النتيجة المطلوبة

- `System check identified no issues`
- `No changes detected`
- `OK`

لا توجد هجرات أو تغييرات بيانات في هذه الحزمة.

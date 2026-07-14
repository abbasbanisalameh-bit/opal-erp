# مركز التطوير - النسخة العربية النهائية

هذه الحزمة مبنية على النسخة التي رفعتها، وتتضمن:

- تعريب واجهات مركز التطوير الرئيسية.
- تحسين مخطط جانت بهوية OPAL الداكنة.
- إصلاح محرك سير العمل ليعيد نتائج مستقرة ويدعم القاموس والخصائص.
- تحديث حساب نسب الإنجاز بناءً على `progress` وليس فقط حالة `done`.
- تثبيت روابط لوحة المدير التنفيذي ومحرك سير العمل.
- حماية محرك سير العمل من التكرار أثناء إشارات Django.

## طريقة التركيب

ارفع الملف المضغوط إلى:

`/home/Opalschool2016/opal_school/opal_school/`

ثم نفذ:

```bash
cd ~/opal_school/opal_school
unzip -o development_center_v1_ar_workflow_final.zip
python manage.py check
python manage.py test development_center
```

ثم جرّب:

- /development/executive/
- /development/workflow/run/
- /development/gantt/
- /development/tasks/board/

## ملاحظات مهمة

- لا تضف `db.sqlite3` إلى Git.
- إذا أردت حفظ الحزمة بعد الاختبار:

```bash
git add development_center templates/development_center templates/includes/sidebar.html static/css/opal_dashboard_final_v2.css
git commit -m "Finalize Arabic development center v1 workflow"
git push
```

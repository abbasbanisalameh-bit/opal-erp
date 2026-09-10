# OPAL Development Center — Workflow Engine Package

هذه النسخة تحتوي على تحسينات جاهزة لمركز التطوير:

- إضافة Workflow Engine في `development_center/services/workflow_engine.py`.
- تنظيف `views.py` وإزالة تكرار `executive_dashboard`.
- توحيد روابط `urls.py` وترتيبها.
- ربط تغيير حالة المهام بمحرك سير العمل.
- تحديث تلقائي لتقدم الوحدات، المراحل، السبرنتات، والإشعارات.
- إضافة زر تشغيل محرك سير العمل إلى لوحة المدير التنفيذي.
- إضافة رابط لوحة المدير التنفيذي ومحرك العمل إلى القائمة الجانبية.
- إصلاح قالب Sprint Dashboard الذي كان يحتوي على HTML غير مكتمل.
- جعل Gantt يستخدم رابطًا نسبيًا بدل رابط ثابت للموقع.

## طريقة التركيب على PythonAnywhere

من داخل مجلد المشروع:

```bash
cd ~/opal_school/opal_school
unzip -o development_center_workflow_ready.zip
python manage.py check
python manage.py test development_center
```

ثم افتح:

https://opalschool2016.pythonanywhere.com/development/workflow/run/

ثم:

https://opalschool2016.pythonanywhere.com/development/executive/

إذا نجح كل شيء:

```bash
git add development_center templates/development_center templates/includes/sidebar.html
git commit -m "Add development center workflow engine"
git push
```

## ملاحظة
لا تضف `db.sqlite3` إلى Git.

# تركيب تحديث صلاحيات OPAL

1. احفظ نسخة الكود الحالية وقاعدة البيانات من مركز التحديثات.
2. ارفع `OPAL_ROLE_PERMISSIONS_ACADEMIC_WORKFLOW_CURRENT_READY_20260716.zip`.
3. اضغط **رفع التحديث والتحقق منه**.
4. اختر الإصدار `OPAL_ROLE_PERMISSIONS_ACADEMIC_WORKFLOW_20260716_V1` واضغط **استعادة**.
5. يطبق المركز `check` ثم `migrate` ثم `collectstatic`.
6. بعد رسالة النجاح اضغط **Reload** من صفحة Web في PythonAnywhere.

التحديث لا يحتوي قاعدة البيانات أو media أو البيئة الافتراضية أو `.env` أو Git.

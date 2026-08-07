# تركيب OPAL Update 131.7 R12

هذا التحديث يُظهر **منصة أوبال التعليمية** في القائمة الجانبية لمدير OPAL ERP، ويفتح لوحة إدارة المنصة من جلسة المدير الحالية. لا ينشئ حسابًا تعليميًا موازيًا للمدير.

يبقى دخول بقية مستخدمي المنصة منفصلًا:

- تسجيل مستخدم جديد: `/learning/register/`
- دخول المتعلم أو المدرّس: `/learning/login/`
- دخول المدير من OPAL ERP: القائمة الجانبية ← **منصة أوبال التعليمية**

## أوامر التركيب

```bash
cd /home/Opalschool2016/opal_school
source /home/Opalschool2016/.virtualenvs/opal/bin/activate
python tools/validate_opal_update_131_source.py .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test learning_platform core.tests_navigation_consolidation core.test_update131_7_r12_learning_platform_manager_gateway_contract
python manage.py collectstatic --clear --noinput
```

بعد نجاح الأوامر اضغط **Reload** من تبويب Web في PythonAnywhere، ثم سجل الدخول إلى OPAL ERP بحساب المدير. سيظهر رابط **منصة أوبال التعليمية** في القائمة الجانبية.

## اختبار القبول

1. افتح OPAL ERP بحساب المدير واضغط رابط المنصة من القائمة الجانبية.
2. تأكد أن الرابط يفتح `/learning/manage/` دون طلب دخول تعليمي مستقل.
3. افتح نافذة خاصة وانتقل إلى `/learning/login/`؛ يجب أن تظهر صفحة دخول المنصة المستقلة.
4. تأكد أن حساب ERP العادي غير الإداري لا يستطيع فتح `/learning/manage/`.

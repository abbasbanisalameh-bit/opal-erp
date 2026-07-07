# OPAL ERP – Smart Registration V2

تمت إضافة أساس نظام التسجيل الذكي داخل تطبيق `admissions` بدون إنشاء نموذج طالب جديد، مع الاعتماد على `students.Student` كنموذج الطالب الرسمي الوحيد.

## ما تم إنجازه

- إعدادات التسجيل والرسوم:
  - رسوم الصفوف `GradeFee`.
  - جولات المواصلات `TransportRoute`.
  - إعدادات الخصومات والدفعة الأولى `RegistrationSettings`.
- نموذج التسجيل المباشر:
  - `/admissions/register/`
  - يحسب رسوم الصف، رسوم المواصلات، الخصم، الدفعة الأولى، والمتبقي مباشرة في الصفحة.
- سجل التسجيل:
  - `/admissions/`
- إعدادات التسجيل:
  - `/admissions/settings/`
- إيصال التسجيل بنسختين:
  - `/admissions/registration/<id>/receipt/`
- عند الحفظ يتم إنشاء:
  - الطالب في `students.Student`.
  - قيد التسجيل في `admissions.StudentRegistration`.
  - فاتورة في `accounting.StudentInvoice`.
  - دفعة في `accounting.StudentPayment` إذا كانت الدفعة الأولى أكبر من صفر.
  - إيصال في `accounting.Receipt`.
  - ربط أكاديمي في `academics.Enrollment` إن وجد عام دراسي حالي.

## أوامر التشغيل بعد رفع النسخة

```bash
cd ~/opal_school/opal_school
python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
```

ثم افتح:

- `/admissions/settings/` لإدخال رسوم الصفوف وجولات المواصلات والخصومات.
- `/admissions/register/` لتسجيل طالب جديد.

## ملاحظات مهمة

- لم يتم تحويل `Development Center` لهوية OPAL، لأن له هوية مستقلة معتمدة.
- لم يتم إنشاء نموذج طالب بديل؛ الطالب الرسمي الوحيد هو `students.Student`.
- تم بناء المنطق الحسابي في `admissions/services.py` ليكون قابلاً لإعادة الاستخدام لاحقًا مع وزارة التربية وسندات القبض.

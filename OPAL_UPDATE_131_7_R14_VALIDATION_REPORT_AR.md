# تقرير تحقق OPAL Update 131.7 R14

## نطاق التحقق

- سلامة تركيب Python لجميع ملفات المصدر.
- وجود صفحات ومسارات ونماذج إدارة المدرّسين والمواد والدورات والدروس.
- حماية بوابات الإدارة بهوية مدير OPAL ERP.
- حصر تغييرات الحالة في POST مع CSRF.
- منع نشر دورة دون درس منشور أو بمدرّس/مادة غير فعالين.
- بقاء هوية المتعلم والمدرّس مستقلة وعدم إنشاء نموذج طالب أو مدرّس موازٍ.
- عدم وجود هجرة قاعدة بيانات جديدة في R14.
- اتساق هوية الإصدار وmanifest وسلامة حزمة ZIP.

## النتيجة المحلية

- `compileall`: ناجح لجميع ملفات Python.
- بوابة المصدر الساكن: **244/244 ناجح**.
- ملفات Python التي تم تحليلها: **597 ملفًا**.
- فحص مراجع مسارات قوالب المنصة: **لا توجد أسماء مسارات مفقودة**.
- `learning_platform/models.py`: لم يتغير عن R13.
- هجرات المنصة: بقيت `0001_initial.py` فقط.
- اختبارات Django التشغيلية لم تُشغّل محليًا لأن بيئة البناء لا تحتوي Django؛ يجب تشغيلها على PythonAnywhere بعد التركيب.

## أوامر القبول المطلوبة على الخادم

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py test learning_platform core.test_update131_7_r14_learning_platform_content_management_contract
python manage.py collectstatic --clear --noinput
```

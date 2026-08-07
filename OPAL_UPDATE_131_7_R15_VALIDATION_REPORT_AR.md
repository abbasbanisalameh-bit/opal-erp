# تقرير تحقق OPAL Update 131.7 R15

## العطل المثبت من سجل PythonAnywhere

ظهر الاستثناء:

`django.urls.exceptions.NoReverseMatch`

عند محاولة توليد `learning_platform:course_detail` للمعرف العربي:

`كورس-اللغة-الانجليزية-للصف-الثاني-ثانوي`

كان نموذج الدورة والنموذج الإدخالي يسمحان بـUnicode، بينما استخدم مسار العرض محول `<slug:slug>` غير المتوافق مع الأحرف العربية في نمط URL.

## الإصلاح

- أصبح مسار تفاصيل الدورة `courses/<str:slug>/`.
- بقي البحث عن الدورة بقيمة `slug` نفسها، لذلك لا يلزم تعديل أي سجل موجود.
- أضيف اختبار تراجع يغطي الصفحة الرئيسية، دليل الدورات، تفاصيل دورة عربية، وقائمة دورات المدير.
- لم تتغير النماذج أو الهجرات أو بيانات تسجيل الدخول.

## نتائج الفحص المحلي

- `compileall`: ناجح لجميع ملفات Python.
- بوابة المصدر الساكن: **251/251 ناجح**.
- ملفات Python التي تم تحليلها: **598 ملفًا**.
- التحقق من هوية R15 وmanifest: ناجح.
- التحقق من غياب `<slug:slug>` لمسار الدورة ووجود `<str:slug>`: ناجح.
- هجرات `learning_platform`: بقيت `0001_initial.py` فقط.
- اختبارات Django التشغيلية لم تُشغّل محليًا لعدم وجود Django في بيئة البناء؛ يجب تشغيلها على PythonAnywhere بعد التركيب.

## أوامر القبول المطلوبة على الخادم

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test learning_platform core.test_update131_7_r15_learning_platform_arabic_slug_runtime_fix_contract
python manage.py collectstatic --clear --noinput
```

## ملاحظة السجل

الرسالة `Not Found: /static/vendor/chartjs/chart.umd.min.js` ليست سبب خطأ 500 الوارد في التتبع؛ سبب 500 المثبت هو `NoReverseMatch`. يمكن معالجة ملف Chart.js لاحقًا ضمن تدقيق الأصول إذا بقيت الرسالة بعد `collectstatic`، دون خلطها بهذا الإصلاح.

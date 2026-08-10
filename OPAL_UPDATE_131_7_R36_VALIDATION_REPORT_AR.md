# تقرير تحقق R36

## فحوص المصدر
- نجحت بوابة المصدر الثابتة: **355/355 PASS**، وتم تحليل **673 ملف Python** دون خطأ نحوي.
- تم الحفاظ على مسارات دخول ولي الأمر والمعلم والإدارة كما هي.
- لا توجد Migration جديدة.
- لا توجد قاعدة بيانات أو `.env` أو مفاتيح توقيع ضمن الحزمة.
- الشعار المعتمد موجود في أصول Flutter وأصول منصة الويب.
- رقم تطبيق المنصة: `1.3.0+39`.

## التحقق المطلوب على PythonAnywhere

```bash
python manage.py check
python manage.py test core.test_update131_7_r36_learning_mobile_branding_contract --settings=config.settings_test_low_memory --verbosity 1 --noinput
```

ثم ينتج GitHub Actions APK/AAB بعد الـPush.

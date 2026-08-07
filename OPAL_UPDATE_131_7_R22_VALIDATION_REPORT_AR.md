# تقرير تحقق OPAL Update 131.7 R22

## الهوية

- الإصدار: `131.7`
- اسم الإصدار: `OPAL Update 131.7 R22 - Forward-Compatible Release Contract Fix`
- خط الأساس: `OPAL Update 131.7 R21 - Learning Platform Runtime Validation Fixes`
- نوع الحزمة: `code_only`
- مراجعة الحزمة: `25`
- لا توجد هجرة قاعدة بيانات جديدة.

## سبب الإصلاح

أثبت تشغيل الاختبارات على PythonAnywhere أن إصلاحات R21 نجحت، وبقي فشل واحد لأن عقد R20 التاريخي كان يثبت أن اسم الإصدار الحالي يجب أن يبقى R20. كشف التحليل أن عقود R11-R21 تحمل النمط نفسه، ولذلك كان تشغيل المجموعة الكاملة أو تركيب أي تحديث تالٍ سيؤدي إلى فشل متتابع لعقود الهوية القديمة.

## النطاق المنفذ

- إضافة عقد مركزي متوافق مع الإصدارات اللاحقة في `core/release_contract_assertions.py`.
- تحديث عقود R11-R21 لتتحقق من اتساق الإصدار الحالي وحد المراجعة الأدنى لكل مرحلة دون تثبيت اسم أو baseline تاريخي.
- إضافة عقد R22 يمنع عودة هذا النمط الهش.
- تحديث بوابتي المصدر والأرشيف لمراجعة الحزمة 25 وملفات R22.
- لا تغيير في البيانات أو وظائف المنصة أو الصلاحيات.

## التحقق المنفذ في بيئة البناء

- تحليل تركيب جميع ملفات Python: ناجح.
- بوابة المصدر: `306/306` ناجحة.
- عدد ملفات Python المحللة: `628`.
- اختبار مباشر للعقد المركزي بهوية R22 الحالية: ناجح.
- التحقق من استخدام العقد المركزي في عقود R11-R21 وعدم اعتمادها على `manifest["baseline"]`: ناجح.
- فحص الأرشيف النهائي: ناجح دون أخطاء أو تحذيرات؛ الحزمة تحتوي مشروعًا واحدًا و`1296` ملفًا، ولا تحتوي قاعدة بيانات أو وسائط أو بيئة افتراضية أو أسرار أو أرشيفات متداخلة.

## ما لم يُنفذ محليًا

لم تتوفر بيئة Django التشغيلية وقاعدة المشروع الفعلية داخل بيئة البناء، ولذلك يجب تشغيل اختبارات Django على PythonAnywhere بعد التركيب.

## أوامر الاعتماد على PythonAnywhere

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract core.test_update131_7_r21_learning_runtime_validation_fix_contract core.test_update131_7_r22_forward_compatible_release_contract
```

بعد ظهور `OK`:

```bash
python manage.py test
python manage.py collectstatic --clear --noinput
```

لا يعتمد R22 للتشغيل النهائي قبل نجاح الاختبارات المستهدفة والمجموعة الكاملة على PythonAnywhere.

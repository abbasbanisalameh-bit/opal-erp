# دليل تركيب OPAL Update 131.7 R33

**الاسم:** Production Readiness Alignment and Secure Subscription Cards  
**خط الأساس:** R32 — In-Page Lesson Video Player  
**نوع التحديث:** كود فقط — لا توجد هجرة قاعدة بيانات جديدة، ولا يغير أرقام البطاقات الموجودة.

## ماذا يصلح R33؟

1. فحص `CURRENT_SEMESTER` لم يعد يعتبر الفترة السابقة لبداية الدراسة أو عطلة منتصف العام خطأً؛ يطلب فصلًا تشغيليًا فقط عندما يكون تاريخ اليوم داخل الحدود الرسمية لفصل مفتوح.
2. بطاقات الاشتراك أصبحت وضع التحصيل الافتراضي للمنصة (`cards`) ولا تتطلب بوابة دفع إلكترونية خارجية حتى عند اعتماد الإطلاق العام.
3. أوضاع التحصيل أصبحت واضحة: `cards` أو `manual` أو `payment` عبر `OPAL_LEARNING_SUBSCRIPTION_SALES_MODE`.
4. تقرير الجاهزية يصنف كل بند إلى: إلزامي، اختياري، أو قيد استضافة.
5. إضافة أمر يكتب `requirements-lock-r20.txt` من بيئة Python الحية التي نجحت فيها الاختبارات بدل تخمين إصدارات الحزم.
6. كل بطاقة جديدة ينشئها النظام آليًا تستخدم مولدًا مشفرًا مركزيًا يقارب 100 bit من العشوائية، ولا يحتوي رقم طالب أو رقم طلب أو تسلسل قابل للتوقع.
7. بطاقات البيانات التجريبية أصبحت عشوائية أيضًا؛ البطاقات الموجودة قبل R33 تبقى كما هي وصالحة.

## التركيب

ارفع ZIP من مركز تحديثات النظام وثبته، ثم افتح Bash:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

النتيجة الصحيحة للهجرات في R33 هي عدم وجود هجرة جديدة مطلوبة.

## اختبارات R33

```bash
python manage.py test \
  core.test_update131_7_r33_production_readiness_alignment_contract \
  learning_platform.test_update131_7_r33_production_readiness_alignment \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

المتوقع اكتشاف **12 اختبارًا** وانتهاء التنفيذ بـ `OK`.

## تثبيت الاعتماديات من البيئة المختبرة

بعد نجاح الاختبارات السابقة مباشرة:

```bash
python manage.py write_learning_dependency_lock
```

ثم تحقق:

```bash
grep -Ei '^(Django|Pillow)==' requirements-lock-r20.txt
```

يجب أن يظهر الإصداران المثبتان فعليًا في بيئة PythonAnywhere.

## فحص سير العمليات والجاهزية

```bash
python manage.py audit_operation_flow --allow-issues
python manage.py verify_learning_production_readiness
```

في تاريخ خارج حدود فصل دراسي، يجب ألا يكون `CURRENT_SEMESTER` مشكلة. ومع الوضع الافتراضي `cards` يجب أن تظهر طريقة تحصيل الاشتراك `PASS` دون اشتراط بوابة دفع خارجية.

> ملاحظة: R33 لا يلغي شرط النسخة الاحتياطية المتحققة. إذا لم توجد نسخة متحققة حديثة فستظل بوابة المنصة تعرض فشلًا مانعًا لهذا البند عمدًا. كما تبقى SQLite مصنفة كـ«قيد استضافة» على PythonAnywhere المجاني.

## الملفات الثابتة وإعادة التحميل

```bash
python manage.py collectstatic --clear --noinput
python manage.py check
```

ثم من PythonAnywhere: **Web → Reload**.

## Git

بعد نجاح كل ما سبق:

```bash
git status --short
git add -A
git commit -m "OPAL R33: Align production readiness and secure subscription cards"
git push origin "$(git branch --show-current)"
```

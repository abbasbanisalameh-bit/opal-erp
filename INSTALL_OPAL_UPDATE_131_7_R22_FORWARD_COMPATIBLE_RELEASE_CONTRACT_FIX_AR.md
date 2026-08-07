# تركيب OPAL Update 131.7 R22

## Forward-Compatible Release Contract Fix

يُركب هذا التحديث فوق:

`OPAL Update 131.7 R21 - Learning Platform Runtime Validation Fixes`

## سبب التحديث

بعد نجاح إصلاحات R21 بقي اختبار R20 التاريخي يطالب بأن يكون الإصدار الحالي R20، بينما أصبحت هوية النشر الصحيحة R21. كما أن اختبارات R11-R19 وR21 كانت تستخدم النمط نفسه، ولذلك كانت ستفشل تباعًا عند تشغيل مجموعة الاختبارات الكاملة أو عند تركيب أي إصدار لاحق.

## ما يصلحه R22

- إضافة عقد مركزي لهوية الإصدار الحالية.
- تحويل عقود R11 حتى R21 إلى عقود متوافقة مع الإصدارات اللاحقة.
- كل عقد تاريخي يتحقق من إصدار `131.7`، واتساق `OPAL_RELEASE_NAME.txt` مع manifest، ومن حد أدنى لرقم الحزمة، دون تثبيت اسم إصدار تاريخي أو baseline قديم.
- إضافة اختبار R22 يمنع إعادة إدخال عقود هوية هشة مستقبلًا.
- لا توجد هجرة قاعدة بيانات ولا تغيير على الحسابات أو الدورات أو الاشتراكات أو المدفوعات أو الصلاحيات.

## التركيب

1. خذ نسخة احتياطية من الكود وقاعدة البيانات.
2. ثبّت R22 من مركز تحديثات OPAL فوق R21.
3. بعد اكتمال التركيب افتح Bash ونفّذ:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract core.test_update131_7_r21_learning_runtime_validation_fix_contract core.test_update131_7_r22_forward_compatible_release_contract
```

النتيجة المطلوبة:

```text
OK
```

بعد نجاح الاختبارات المستهدفة:

```bash
python manage.py test
python manage.py collectstatic --clear --noinput
```

ثم اضغط **Reload** من صفحة Web.

## التراجع

لا توجد هجرة جديدة. عند فشل التركيب استعد نسخة الكود السابقة R21 عبر نقطة الأمان في مركز التحديثات، ولا تستخدم `migrate --fake`.

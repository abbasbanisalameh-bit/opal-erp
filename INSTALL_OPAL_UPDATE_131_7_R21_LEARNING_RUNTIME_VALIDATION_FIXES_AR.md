# تركيب OPAL Update 131.7 R21

## Learning Platform Runtime Validation Fixes

يُركب هذا التحديث فوق:

`OPAL Update 131.7 R20 - Learning Platform Production Release Candidate`

## سبب التحديث

أظهرت اختبارات PythonAnywhere بعد تركيب R20 ثلاث مشكلات في بوابة الاعتماد، وليست ثلاثة أعطال وظيفية في المنصة:

1. اختبار رفض دورة غير مسجل بها المتعلم اعتمد على ترجمة عربية ثابتة لرسالة Django.
2. عقد مصدر API بحث عن `Authorization` بدل مفتاح Django الفعلي `HTTP_AUTHORIZATION`.
3. مركز التحديثات في R20 كان يتعمد عدم نسخ `OPAL_UPDATE_MANIFEST.json` إلى جذر المشروع، بينما عقد الإصدار يحتاجه.

## ما يصلحه R21

- قياس رفض الدورة خارج تسجيل المتعلم من خلال أخطاء الحقل وقائمة الدورات المسموحة، دون الاعتماد على ترجمة الرسالة.
- تحديث عقد API للتحقق من `HTTP_AUTHORIZATION` وصيغة Bearer الفعلية.
- تعديل محرك التحديثات ليحتفظ بملف manifest في التحديثات اللاحقة.
- هجرة إصلاحية `0007_r21_runtime_validation_fixes` تعيد إنشاء manifest أثناء تركيب R21، لأن محرك R20 الذي ينفذ التركيب لا ينسخه.
- لا تغيير على بيانات الطلاب أو الحسابات أو الدورات أو الاشتراكات أو صلاحيات المنصة.

## التركيب

1. خذ نسخة احتياطية من الكود وقاعدة البيانات.
2. ثبّت R21 من مركز تحديثات OPAL فوق R20.
3. مركز التحديثات يشغّل الفحص والهجرات و`collectstatic` تلقائيًا.
4. بعد نجاح التركيب افتح Bash ونفّذ اختبارات الاعتماد أدناه.

## أوامر الاعتماد

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract core.test_update131_7_r21_learning_runtime_validation_fix_contract
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

## تحقق manifest

```bash
ls -l OPAL_UPDATE_MANIFEST.json
python - <<'PY'
import json
from pathlib import Path
p = Path('OPAL_UPDATE_MANIFEST.json')
data = json.loads(p.read_text(encoding='utf-8'))
print(data['version_name'])
print(data['package_revision'])
PY
```

النتيجة المتوقعة:

```text
OPAL Update 131.7 R21 - Learning Platform Runtime Validation Fixes
24
```

## التراجع

لا تستخدم `migrate --fake`. عند فشل تركيب R21، يفترض أن يعيد مركز التحديثات الكود وقاعدة SQLite تلقائيًا إلى نقطة الأمان السابقة. أرسل نص الخطأ الكامل إذا حدث ذلك.

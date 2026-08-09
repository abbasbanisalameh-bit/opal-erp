# تركيب OPAL Update 131.7 R35.2 — دخول الإدارة من تطبيق Android

## الهدف
يضيف R35.2 دخول إدارة OPAL إلى تطبيق Android باستخدام **نفس اسم المستخدم وكلمة مرور OPAL ERP**، دون إنشاء كلمة مرور ثانية للمنصة.

## ما يضيفه
- رمز إدارة موبايل منفصل وقصير العمر يبدأ بـ `olm_`، وتُخزن بصمته Hash فقط.
- مراجعة صلاحية المستخدم الإداري في كل طلب حسب قاعدة OPAL الرسمية `is_management_user`.
- لوحة إدارة موبايل: الملخص والجاهزية، الحسابات، الدورات وحالة النشر، بطاقات الاشتراك العشوائية، وإتاحة المنصة للجميع/المعلمين/الصف/الطالب.
- لا يغير تسجيل دخول ولي الأمر أو المعلم أو حسابات المنصة المستقلة.

## التركيب
ركّب ZIP من مركز تحديثات النظام، ثم في Bash:

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
```

يجب أن تظهر الهجرة:

```text
learning_platform.0009_manager_mobile_api_token
```

## اختبارات R35.2

```bash
python manage.py test \
  core.test_update131_7_r35_2_manager_mobile_contract \
  learning_platform.test_update131_7_r35_2_manager_mobile \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

المتوقع: `Found 10 test(s).` ثم `OK`.

## اختبار رجعي للموبايل

```bash
python manage.py test \
  core.test_update131_7_r35_android_production_app_contract \
  core.test_update131_7_r35_1_flutter_radio_group_hotfix_contract \
  core.test_update131_7_r35_2_manager_mobile_contract \
  learning_platform.test_update131_7_r34_mobile_school_sso \
  learning_platform.test_update131_7_r35_2_manager_mobile \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

المتوقع: `Found 20 test(s).` ثم `OK`.

## بعد نجاح الاختبارات

```bash
python manage.py collectstatic --clear --noinput
python manage.py check
```

ثم Web → Reload.

## GitHub وAPK
لأن R35.2 يعدل ملفات `mobile/opal_learning_app/**`، فإن `git push` سيشغل `OPAL Android Build` تلقائيًا بعد حفظ التحديث على GitHub. لا تحتاج لإعادة تثبيت workflow إذا كان R35/R35.1 قد تم اعتماده بالفعل.

## ملاحظة أمان
- لا ترسل رمز `olm_` يدويًا ولا تخزنه خارج التخزين الآمن للتطبيق.
- إذا فقد المستخدم صفة الإدارة في OPAL ERP، تُرفض رموزه الإدارية القائمة عند الطلب التالي حتى قبل انتهاء مدتها.
- شرط النسخة الاحتياطية في بوابة الجاهزية لم يتغير في R35.2.

# تثبيت OPAL Update 131.7 R37

R37 ينشئ تطبيق Android أصليًا مستقلًا لنظام OPAL ERP. يستخدم التطبيق شعار مدرسة أوبال الدولية الدائري الرسمي، ويدخل المستخدم بنفس بيانات حسابه في النظام.

## المتطلب
ركّب R36 أولًا ثم R37، حتى تبقى هوية تطبيق المنصة المعتمدة موجودة بالتوازي مع تطبيق النظام.

## بعد رفع ZIP من مركز تحديثات OPAL

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate

python manage.py test \
  core.test_update131_7_r37_erp_mobile_app_contract \
  --settings=config.settings_test_low_memory \
  --verbosity 1 \
  --noinput
```

المتوقع: **6 tests / OK**.

## تثبيت GitHub Actions الخاص بتطبيق النظام

```bash
python manage.py install_erp_mobile_android_ci
```

سينشئ:

```text
.github/workflows/opal-erp-android-build.yml
```

ثم ارفع ملفات R37 وملف الـWorkflow إلى GitHub. سيظهر Workflow مستقل باسم **OPAL ERP Android Build** ويبني APK وAAB باسم artifact: `opal-erp-android-release`.

## ملاحظة الأمان
وحدات البيانات في R37 قراءة وبحث فقط. لا توجد عمليات حذف أو تعديل أو دفع أو إدخال علامات من التطبيق في هذا الإصدار.

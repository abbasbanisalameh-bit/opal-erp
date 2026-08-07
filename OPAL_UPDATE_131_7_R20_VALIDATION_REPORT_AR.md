# تقرير تحقق OPAL Update 131.7 R20

## الهوية

- الإصدار: `131.7`
- اسم الإصدار: `OPAL Update 131.7 R20 - Learning Platform Production Release Candidate`
- خط الأساس: `OPAL Update 131.7 R19 - Grounded AI Assistant and Teacher Tools`
- نوع الحزمة: `code_only`
- الهجرة الجديدة: `learning_platform/0006_learning_production_release.py`

## النطاق المنفذ

- توثيق البريد، قبول الشروط والخصوصية، القفل المؤقت وحدود الطلبات المشتركة.
- رموز API للأجهزة مخزنة كبصمات ومنتهية الصلاحية وقابلة للإلغاء.
- API v1 للدورات والدروس والتقدم والتقييمات والإشعارات والشهادات والخطط والمساعد.
- PWA تحفظ الأصول العامة فقط، ومصدر Flutter وظيفي أولي دون مفاتيح توقيع أو أسرار.
- خطط وأوامر دفع مانعة للتكرار، وWebhook موقع، والتحقق من المبلغ والعملة قبل تفعيل الاستحقاق.
- إلغاء الوصول عند refund/chargeback الموثق.
- مركز جاهزية، ودعم PostgreSQL بالبيئة، وأوامر نسخة احتياطية وتحقق بنيوي.
- وثائق تشغيل وانتقال PostgreSQL وAPI والموبايل.

## التحقق الساكن في بيئة البناء

- تحليل تركيب جميع ملفات Python: `PASS`.
- بوابة مصدر OPAL: `275/275` ناجحة، دون فشل أو تحذير.
- عدد ملفات Python المحللة: `624`.
- فحص أسماء المسارات ومراجع القوالب: `PASS`، دون مسارات مفقودة أو مكررة.
- فحص تركيب JavaScript لطبقة الرسوم المحلية وService Worker: `PASS`.
- فحص الأرشيف النهائي: `PASS`؛ دون أخطاء أو تحذيرات.
- عدد ملفات الأرشيف النهائي: `1284` ملفًا.
- لا تحتوي الحزمة قاعدة بيانات أو وسائط أو بيئة افتراضية أو `.env` أو `.git` أو أرشيفات متداخلة.

## ما لم يُنفذ داخل بيئة البناء

- لم تتوفر Django واعتماديات المشروع في بيئة البناء، لذلك لم تُشغّل اختبارات Django Runtime محليًا.
- لم يتوفر Flutter أو Dart، لذلك لم يُبنَ أو يُوقّع تطبيق Android/iOS؛ تم فحص المصدر والبنية فقط.
- لم تُختبر خدمة SMTP أو مزود دفع حقيقي أو PostgreSQL فعلي؛ هذه تتطلب بيانات اعتماد وبنية خارج الحزمة.
- التحقق من النسخة الاحتياطية بنيوي، ولا يستبدل اختبار استعادة داخل قاعدة معزولة.

## أوامر الاعتماد الإلزامية على PythonAnywhere

```bash
cd /home/Opalschool2016/opal_school
source venv/bin/activate

pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test learning_platform core.test_update131_7_r20_learning_production_release_contract
python manage.py test
python -m pip freeze > requirements-lock-r20.txt
python manage.py collectstatic --clear --noinput
python manage.py backup_learning_platform
python manage.py verify_learning_backup /path/to/generated-backup.zip
python manage.py verify_learning_production_readiness --strict
```

بعدها يجب إجراء اختبار قبول يدوي كامل، واختبار استعادة معزولة، وفحص سجلات الأخطاء واختبار التزامن.

## قرار الجاهزية

R20 **مرشح إصدار إنتاج** وليس اعتماد تشغيل فعلي تلقائيًا. لا يصبح جاهزًا للإطلاق العام إلا بعد نجاح جميع أوامر PythonAnywhere ومجموعة الاختبارات الكاملة، وتوفير SMTP ومزود الدفع وقاعدة الإنتاج والسياسات القانونية النهائية ومفاتيح توقيع تطبيقات المتاجر عند طلب تطبيق أصلي.

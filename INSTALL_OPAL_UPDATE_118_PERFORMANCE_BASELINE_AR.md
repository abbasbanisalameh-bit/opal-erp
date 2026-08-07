# تركيب OPAL Update 118 — خط أساس الأداء

1. هذا التحديث مبني مباشرة على **OPAL Update 117**.
2. ارفع ملف `OPAL_UPDATE_118_PERFORMANCE_BASELINE_AND_DASHBOARD_QUICK_WINS_FULL.zip` من مركز تحديثات OPAL.
3. نفّذ الاستعادة بالطريقة المعتادة.
4. سيشغّل المركز تلقائيًا `check` وفحص الترحيلات و`migrate` و`collectstatic` وإعادة تحميل الموقع.
5. لا توجد Migration جديدة ولا تعديل تلقائي للبيانات.

## إنشاء خط الأساس
من Console الخاصة بالموقع، وبعد تفعيل البيئة الافتراضية، شغّل:

```bash
python manage.py audit_runtime_performance --iterations 5
```

يختار الأمر أول مدير نظام فعّال تلقائيًا. ويمكن تحديد حساب إداري:

```bash
python manage.py audit_runtime_performance --username USERNAME --iterations 5
```

سيظهر في النهاية مسار ملفي JSON وMarkdown المحفوظين داخل مساحة OPAL الخاصة.

## قياس صفحة محددة

```bash
python manage.py audit_runtime_performance --route dashboard:home --iterations 5
```

## مقارنة تحديث لاحق بخط الأساس

```bash
python manage.py audit_runtime_performance --iterations 5 --compare-to /path/to/before.json
```

## بوابة صارمة اختيارية

```bash
python manage.py audit_runtime_performance --iterations 5 --fail-on-budget
```

الأمر للقراءة فقط، لكنه يفتح الصفحات فعليًا بالحساب الإداري المحدد حتى يقيس القالب والاستعلامات والصلاحيات الواقعية.

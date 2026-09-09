# OPAL ERP — Update 130.0

حزمة تثبيت كاملة تجمع تحديثات 128–129.2 مع إصلاحات الاستقرار المطلوبة للاعتماد الفعلي.

- عرض جميع الجداول كمصفوفة أفقية موحّدة: اليوم مرة واحدة في اليمين والحصص أفقيًا.
- تمييز صف اليوم والحصة الجارية لحظيًا وفق اليوم ووقت بداية الحصة ونهايتها.
- منع تمدد الصفحة أفقيًا على الهاتف، وتثبيت القائمة الجانبية داخل حدود الشاشة.
- إصلاح ترتيب هجرات القبول والوثائق كي ينجح إنشاء قاعدة جديدة أو ترقية قاعدة قائمة.
- تثبيت أمان قاعدة SQLite قبل تطبيق التحديث، وتحسين استعلامات لوحة القيادة.
- تصحيح عقود الحضور وملف الطالب 360 وإنهاء المعلم ومؤشر TPI واختبارات البوابات.
- لا تتضمن الحزمة قاعدة بيانات أو ملفات وسائط أو أسرار بيئة، ولا تمس البيانات التشغيلية.

راجع `OPAL_UPDATE_130_PRODUCTION_STABILITY_RELEASE_NOTES_AR.md` للتفاصيل،
و`INSTALL_OPAL_UPDATE_130_PRODUCTION_STABILITY_AR.md` لطريقة التثبيت.


## R39 Transport Fixes
- Driver templates use the canonical base/base.html.
- Driver credential redirect uses transport:driver-credentials.
- Transport center owns the route-management UI while persisting the canonical admissions.TransportRoute records.
- Duplicate trip/driver action blocks and duplicate URL patterns were removed from the transport package.

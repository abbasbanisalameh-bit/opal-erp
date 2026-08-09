# OPAL Update 131.7 R31
## Teacher Portal Learning Platform Link Visibility Fix

يصلح هذا التحديث عدم ظهور رابط **منصة أوبال التعليمية** في بوابة المعلم.

### السبب
القالب `templates/teachers/portal_dashboard.html` كان يحتوي الرابط بالفعل ويعرضه فقط عند تحقق `learning_platform_enabled`، لكن الدالة `teachers.views.portal_dashboard` لم تكن تمرر هذا المتغير إلى القالب.

### الإصلاح
- تمرير `learning_platform_enabled = teacher_learning_access(teacher)` إلى قالب بوابة المعلم.
- الإبقاء على مفتاح **إتاحة المنصة للمعلمين من بوابة المعلم** هو المتحكم الفعلي في ظهور الرابط.
- لا تغييرات في قاعدة البيانات أو migrations.
- لا تغييرات على `students.Student` أو أي بيانات تشغيلية.

### النتيجة
عندما يكون المعلم نشطًا، مرتبطًا بمدرسة، ومفتاح إتاحة المنصة للمعلمين مفعّلًا، تظهر بطاقة **منصة أوبال التعليمية** في صفحة المعلم وتدخل عبر SSO إلى المنصة.

# OPAL 131.7 R89 — Combined R88 + R89 Repository Hygiene and CSS Authority Audit

هذه الحزمة مصممة للتركيب مباشرة فوق OPAL Update 131.7 R87.

## ما تم جمعه من R88
- إضافة قواعد Repository Hygiene إلى `.gitignore` لمنع تتبع `staticfiles/` وملفات التشغيل والبيئات المحلية مستقبلًا.
- لا يتم حذف أي ملف من السيرفر بواسطة هذه الحزمة.
- لا يتم تغيير قاعدة البيانات أو البيانات أو الـ Models أو الـ URLs أو الـ Migrations.

## ما تم جمعه من R89
- تثبيت `static/css/opal_theme_system.css` كسلطة CSS المشتركة الحالية.
- إضافة أداة فحص قابلة للتكرار لجميع ملفات `static/css`.
- تسجيل الـ selectors المتكررة والكتل المتطابقة تمامًا في تقرير JSON.
- عدم حذف قواعد تعتمد على ترتيب CSS Cascade أو Responsive أو Light/Dark mode.

## ضمان التوافق
- تم بناء هذه الحزمة من بنية R87 نفسها، وليس من نسخة أقدم.
- لذلك لا تعيد ملفات R68 أو تغييرات قديمة فوق R87.

# OPAL Update 131.7 R32 — In-Page Lesson Video Player

## الهدف
إبقاء الطالب/ولي الأمر داخل منصة أوبال أثناء مشاهدة فيديو الدرس وعدم نقله إلى صفحة أو تبويب خارجي.

## التغييرات
- إضافة عارض فيديو مدمج داخل `lesson_detail.html`.
- تحويل روابط YouTube إلى `youtube-nocookie.com/embed/...`.
- تحويل Vimeo إلى `player.vimeo.com/video/...`.
- تشغيل روابط الفيديو المباشرة عبر HTML5 `<video>`.
- استخدام iframe محمي `sandbox` للروابط الأخرى التي تسمح بالتضمين.
- إضافة تصميم responsive للمشغل على الهاتف والكمبيوتر.
- لا توجد migrations ولا تغييرات على نماذج البيانات.

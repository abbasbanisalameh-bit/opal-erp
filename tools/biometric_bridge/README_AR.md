# جسر أجهزة البصمة إلى OPAL

الغرض: تشغيل برنامج صغير على كمبيوتر **داخل شبكة المدرسة** يستطيع الوصول إلى جهاز البصمة وإلى موقع OPAL عبر HTTPS.

OPAL لا يخزن قالب البصمة أو صورة الإصبع. الجهاز يظل المصدر البيومتري، والجسر يرسل فقط:

- معرف المعلم داخل الجهاز.
- وقت الحركة.
- دخول/خروج إن كان الجهاز يوفرها.
- معرف حدث لمنع التكرار.

## الإعداد داخل OPAL

1. افتح `الهيكل الأكاديمي → تكامل البصمة`.
2. أضف الجهاز.
3. انسخ رمز الربط الذي يظهر مرة واحدة.
4. اربط كل `device_user_id` بالمعلم الصحيح.

## إعداد الكمبيوتر المحلي

```bash
export OPAL_BIOMETRIC_API_URL="https://YOUR-DOMAIN/timetable/biometric/api/v1/punches/"
export OPAL_BIOMETRIC_TOKEN="opal_bio_..."
```

### ZKTeco

```bash
pip install pyzk
export OPAL_BIOMETRIC_DEVICE_IP="192.168.1.201"
export OPAL_BIOMETRIC_DEVICE_PORT="4370"
python opal_biometric_bridge.py --zkteco
```

شغله كل دقيقة أو كل عدة دقائق من Task Scheduler/cron. الجسر يحتفظ بقائمة الأحداث التي أرسلها، والخادم يطبق منع تكرار ثانيًا.

### جهاز آخر

صدّر/حوّل حركات الجهاز إلى JSON بهذا الشكل:

```json
{"events":[{"user_id":"17","timestamp":"2026-08-09T07:24:10+03:00","direction":"in","event_uid":"optional-unique-id"}]}
```

ثم:

```bash
python opal_biometric_bridge.py --json-file punches.json
```

إذا كان جهازك يدعم بروتوكولًا مختلفًا (ADMS/Push/SDK خاص بالشركة)، يبقى Backend OPAL نفسه صالحًا، ونضيف Adapter للجهاز دون تغيير نماذج الدوام.

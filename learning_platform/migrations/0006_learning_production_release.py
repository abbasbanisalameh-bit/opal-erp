from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("learning_platform", "0005_learning_ai_governance"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningaccount",
            name="email_verified_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="توثيق البريد"),
        ),
        migrations.AddField(
            model_name="learningaccount",
            name="failed_login_count",
            field=models.PositiveSmallIntegerField(default=0, editable=False, verbose_name="محاولات الدخول الفاشلة"),
        ),
        migrations.AddField(
            model_name="learningaccount",
            name="locked_until",
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="الحساب مقفل حتى"),
        ),
        migrations.AddField(
            model_name="learningaccount",
            name="privacy_accepted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="قبول سياسة الخصوصية"),
        ),
        migrations.AddField(
            model_name="learningaccount",
            name="terms_accepted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="قبول شروط الاستخدام"),
        ),
        migrations.CreateModel(
            name="LearningEmailVerificationRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="بصمة الرمز")),
                ("expires_at", models.DateTimeField(db_index=True, verbose_name="ينتهي في")),
                ("used_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="استخدم في")),
                ("request_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="عنوان الطلب")),
                ("delivery_status", models.CharField(choices=[("pending", "بانتظار الإرسال"), ("sent", "تم الإرسال"), ("failed", "تعذر الإرسال")], db_index=True, default="pending", max_length=20, verbose_name="حالة الإرسال")),
                ("delivery_error", models.CharField(blank=True, max_length=240, verbose_name="خطأ الإرسال")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="email_verification_requests", to="learning_platform.learningaccount", verbose_name="الحساب")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="LearningSubscriptionPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, verbose_name="اسم الخطة")),
                ("slug", models.SlugField(allow_unicode=True, max_length=180, unique=True, verbose_name="المعرف")),
                ("duration", models.CharField(choices=[("monthly", "شهري"), ("termly", "فصلي"), ("yearly", "سنوي")], max_length=20, verbose_name="المدة")),
                ("price", models.DecimalField(decimal_places=3, max_digits=10, verbose_name="السعر")),
                ("currency", models.CharField(default="JOD", max_length=3, verbose_name="العملة")),
                ("grants_all_subjects", models.BooleanField(default=False, verbose_name="جميع المواد")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="فعالة")),
                ("display_order", models.PositiveSmallIntegerField(default=1, verbose_name="الترتيب")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subjects", models.ManyToManyField(blank=True, related_name="subscription_plans", to="learning_platform.learningsubject")),
            ],
            options={
                "ordering": ["display_order", "price", "id"],
                "constraints": [models.CheckConstraint(condition=models.Q(("price__gte", 0)), name="learning_plan_price_nonnegative")],
            },
        ),
        migrations.CreateModel(
            name="LearningPaymentOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.CharField(db_index=True, max_length=40, unique=True, verbose_name="المعرف العام")),
                ("amount", models.DecimalField(decimal_places=3, max_digits=10, verbose_name="المبلغ")),
                ("currency", models.CharField(default="JOD", max_length=3, verbose_name="العملة")),
                ("status", models.CharField(choices=[("pending", "بانتظار الدفع"), ("processing", "قيد المعالجة"), ("paid", "مدفوع"), ("failed", "فشل"), ("cancelled", "ملغي"), ("refunded", "مسترد")], db_index=True, default="pending", max_length=20, verbose_name="الحالة")),
                ("provider", models.CharField(default="manual", max_length=80, verbose_name="مزود الدفع")),
                ("provider_reference", models.CharField(blank=True, db_index=True, max_length=160, verbose_name="مرجع المزود")),
                ("checkout_url", models.URLField(blank=True, max_length=1000, verbose_name="رابط الدفع")),
                ("idempotency_key", models.CharField(max_length=80, unique=True, verbose_name="مفتاح منع التكرار")),
                ("paid_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("failure_reason", models.CharField(blank=True, max_length=500, verbose_name="سبب الفشل")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("learner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_orders", to="learning_platform.learningaccount", verbose_name="المتعلم")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_orders", to="learning_platform.learningsubscriptionplan", verbose_name="الخطة")),
                ("subscription_card", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payment_order", to="learning_platform.learningsubscriptioncard")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "constraints": [models.CheckConstraint(condition=models.Q(("amount__gte", 0)), name="learning_payment_amount_nonnegative")],
                "indexes": [
                    models.Index(fields=["learner", "status", "created_at"], name="learn_pay_learner_idx"),
                    models.Index(fields=["provider", "provider_reference"], name="learn_pay_provider_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="LearningPaymentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_event_id", models.CharField(max_length=180, unique=True, verbose_name="معرف حدث المزود")),
                ("event_type", models.CharField(max_length=80, verbose_name="نوع الحدث")),
                ("signature_valid", models.BooleanField(default=False, verbose_name="التوقيع صحيح")),
                ("payload_hash", models.CharField(max_length=64, verbose_name="بصمة الحمولة")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="الحمولة")),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="learning_platform.learningpaymentorder", verbose_name="طلب الدفع")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="LearningAPIToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="بصمة الرمز")),
                ("token_prefix", models.CharField(db_index=True, max_length=12, verbose_name="بداية الرمز")),
                ("device_name", models.CharField(blank=True, max_length=120, verbose_name="اسم الجهاز")),
                ("expires_at", models.DateTimeField(db_index=True, verbose_name="ينتهي في")),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="api_tokens", to="learning_platform.learningaccount", verbose_name="الحساب")),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["account", "revoked_at", "expires_at"], name="learn_api_account_idx")],
            },
        ),
        migrations.CreateModel(
            name="LearningRateLimitBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key_hash", models.CharField(db_index=True, max_length=64, unique=True, verbose_name="مفتاح الحد")),
                ("action", models.CharField(db_index=True, max_length=40, verbose_name="العملية")),
                ("window_started_at", models.DateTimeField(db_index=True, verbose_name="بداية النافذة")),
                ("count", models.PositiveIntegerField(default=0, verbose_name="العدد")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-updated_at"],
                "indexes": [models.Index(fields=["action", "window_started_at"], name="learn_rate_window_idx")],
            },
        ),
        migrations.AddIndex(
            model_name="learningemailverificationrequest",
            index=models.Index(fields=["account", "used_at", "expires_at"], name="learn_verify_account_idx"),
        ),
    ]

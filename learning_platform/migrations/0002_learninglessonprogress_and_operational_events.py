import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learning_platform", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LearningLessonProgress",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("last_viewed_at", models.DateTimeField(blank=True, null=True, verbose_name="آخر مشاهدة")),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True,
                        db_index=True,
                        null=True,
                        verbose_name="تاريخ الإكمال",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "enrollment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lesson_progress",
                        to="learning_platform.learningenrollment",
                        verbose_name="التسجيل",
                    ),
                ),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="learner_progress",
                        to="learning_platform.learninglesson",
                        verbose_name="الدرس",
                    ),
                ),
            ],
            options={
                "ordering": ["lesson_id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("enrollment", "lesson"),
                        name="uniq_learning_lesson_progress",
                    )
                ],
            },
        ),
        migrations.AlterField(
            model_name="learningauditevent",
            name="action",
            field=models.CharField(
                choices=[
                    ("registered", "تسجيل حساب"),
                    ("login", "تسجيل دخول"),
                    ("logout", "تسجيل خروج"),
                    ("subscription_activated", "تفعيل اشتراك"),
                    ("subscription_created", "إنشاء بطاقة اشتراك"),
                    ("subscription_cancelled", "إلغاء بطاقة اشتراك"),
                    ("course_enrolled", "تسجيل في دورة"),
                    ("lesson_completed", "إكمال درس"),
                ],
                db_index=True,
                max_length=40,
            ),
        ),
    ]

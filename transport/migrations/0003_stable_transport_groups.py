import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("transport", "0002_transportdriver_transportfamilylocation_and_more")]

    operations = [
        migrations.AlterField(
            model_name="transportgroup",
            name="direction",
            field=models.CharField(
                blank=True,
                choices=[("morning", "ذهاب صباحي"), ("return", "عودة مسائية")],
                max_length=20,
                null=True,
                verbose_name="الاتجاه",
            ),
        ),
        migrations.AddField(
            model_name="transportgroup",
            name="source",
            field=models.CharField(
                choices=[("auto", "تلقائية"), ("manual", "يدوية")],
                default="auto", max_length=20, verbose_name="مصدر المجموعة"
            ),
        ),
        migrations.AddField(
            model_name="transportgroup",
            name="is_locked",
            field=models.BooleanField(default=False, verbose_name="مثبتة"),
        ),
        migrations.AddField(
            model_name="transportgroup",
            name="is_stable",
            field=models.BooleanField(default=False, verbose_name="مجموعة مستقرة"),
        ),
        migrations.AddField(
            model_name="transportgroup",
            name="assigned_driver",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="transport_groups",
                to="transport.transportdriver",
                verbose_name="السائق المسند",
            ),
        ),
        migrations.AddField(
            model_name="transporttrip",
            name="planning_group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="daily_trips",
                to="transport.transportgroup",
                verbose_name="مجموعة التخطيط",
            ),
        ),
        migrations.CreateModel(
            name="TransportGroupMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="transport.transportgroup", verbose_name="مجموعة المواصلات")),
                ("registration", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transport_group_memberships", to="admissions.studentregistration", verbose_name="التسجيل")),
            ],
            options={
                "verbose_name": "عضو مجموعة مواصلات",
                "verbose_name_plural": "أعضاء مجموعات المواصلات",
            },
        ),
        migrations.AddIndex(
            model_name="transportgroup",
            index=models.Index(fields=["route", "is_stable", "is_locked"], name="transport_g_route_i_5b7d6a_idx"),
        ),
        migrations.AddConstraint(
            model_name="transportgroupmember",
            constraint=models.UniqueConstraint(fields=("group", "registration"), name="uniq_transport_group_member"),
        ),
        migrations.AddConstraint(
            model_name="transportgroupmember",
            constraint=models.UniqueConstraint(fields=("registration",), name="uniq_transport_registration_group_membership"),
        ),
    ]

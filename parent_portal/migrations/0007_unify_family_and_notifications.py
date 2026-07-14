from django.db import migrations


def normalize_phone(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


def migrate_legacy_parent_data(apps, schema_editor):
    ParentProfile = apps.get_model("parent_portal", "ParentProfile")
    ParentMessage = apps.get_model("parent_portal", "ParentMessage")
    LegacyNotification = apps.get_model("parent_portal", "Notification")
    Family = apps.get_model("parent_portal", "Family")
    FamilyStudent = apps.get_model("parent_portal", "FamilyStudent")
    UserProfile = apps.get_model("accounts", "UserProfile")
    School = apps.get_model("core", "School")
    AuditLog = apps.get_model("core", "AuditLog")
    Notification = apps.get_model("enterprise_ops", "Notification")

    default_school = School.objects.filter(is_active=True).first()

    for family in Family.objects.all().iterator():
        changed = []
        normalized = normalize_phone(family.phone)
        if normalized and family.phone != normalized:
            family.phone = normalized
            changed.append("phone")
        if family.national_id and not family.guardian_national_id:
            family.guardian_national_id = family.national_id
            changed.append("guardian_national_id")
        if changed:
            family.save(update_fields=changed)

    for legacy in ParentProfile.objects.select_related("user").all().iterator():
        family = Family.objects.filter(user_id=legacy.user_id).first()
        if family is None:
            user_profile = UserProfile.objects.filter(user_id=legacy.user_id).first()
            school_id = getattr(user_profile, "school_id", None) or getattr(default_school, "pk", None)
            guardian_name = " ".join(
                part for part in [legacy.user.first_name, legacy.user.last_name] if part
            ).strip() or legacy.user.username
            family = Family.objects.create(
                school_id=school_id,
                user_id=legacy.user_id,
                guardian_name=guardian_name,
                phone=normalize_phone(legacy.phone),
            )
            family.family_code = f"FAM-{family.pk:06d}"
            family.save(update_fields=["family_code"])
        FamilyStudent.objects.get_or_create(
            family_id=family.pk,
            student_id=legacy.student_id,
            defaults={"relation": "ولي أمر", "is_active": True},
        )

    for item in LegacyNotification.objects.all().iterator():
        recipient_ids = Family.objects.filter(
            children__student_id=item.student_id,
            children__is_active=True,
            user_id__isnull=False,
        ).values_list("user_id", flat=True).distinct()
        for recipient_id in recipient_ids:
            Notification.objects.create(
                recipient_id=recipient_id,
                title=item.title,
                message=item.body,
                level="info",
                link=f"/parent/student/{item.student_id}/",
                is_read=item.is_read,
                created_at=item.created_at,
            )

    for message in ParentMessage.objects.all().iterator():
        AuditLog.objects.create(
            user_id=message.sender_id,
            action="create",
            model_name="legacy.ParentMessage",
            object_id=str(message.pk),
            description=f"{message.subject}: {message.body}",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("parent_portal", "0006_family_family_code_family_guardian_national_id"),
        ("accounts", "0001_initial"),
        ("core", "0003_alter_academicyear_options_alter_semester_options_and_more"),
        ("enterprise_ops", "0003_alter_rolepermissionrule_feature_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_legacy_parent_data, migrations.RunPython.noop),
        migrations.RemoveField(model_name="family", name="national_id"),
        migrations.DeleteModel(name="ParentMessage"),
        migrations.DeleteModel(name="Notification"),
        migrations.DeleteModel(name="ParentProfile"),
    ]

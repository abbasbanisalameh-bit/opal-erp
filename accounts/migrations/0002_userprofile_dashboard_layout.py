from django.db import migrations, models


def _column_names(schema_editor, model):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(
            cursor, model._meta.db_table
        )
    return {column.name for column in description}


def add_dashboard_layout_if_missing(apps, schema_editor):
    """Handle a database that retained the column after a code-only restore."""

    UserProfile = apps.get_model("accounts", "UserProfile")
    if "dashboard_layout" in _column_names(schema_editor, UserProfile):
        return
    field = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="تخطيط لوحة التحكم",
    )
    field.set_attributes_from_name("dashboard_layout")
    schema_editor.add_field(UserProfile, field)


def remove_dashboard_layout_if_present(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")
    if "dashboard_layout" not in _column_names(schema_editor, UserProfile):
        return
    field = models.JSONField(
        blank=True,
        default=dict,
        verbose_name="تخطيط لوحة التحكم",
    )
    field.set_attributes_from_name("dashboard_layout")
    schema_editor.remove_field(UserProfile, field)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_dashboard_layout_if_missing,
                    remove_dashboard_layout_if_present,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="userprofile",
                    name="dashboard_layout",
                    field=models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="تخطيط لوحة التحكم",
                    ),
                ),
            ],
        ),
    ]

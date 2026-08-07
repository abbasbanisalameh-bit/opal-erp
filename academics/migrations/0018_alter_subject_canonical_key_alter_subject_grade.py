"""Synchronize the final Subject model state with the migration graph.

Update 131 changes ``Subject.canonical_key`` from a staging field that allowed
blank/default values to its final required state, and protects ``Subject.grade``
from cascade deletion.  The runtime model already carried these definitions;
this migration records them explicitly so ``makemigrations --check`` remains
clean before the update engine applies migrations.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0017_finalize_annual_subject_plan"),
    ]

    operations = [
        migrations.AlterField(
            model_name="subject",
            name="canonical_key",
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=140,
                verbose_name="هوية المادة الموحدة",
            ),
        ),
        migrations.AlterField(
            model_name="subject",
            name="grade",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subjects",
                to="academics.grade",
            ),
        ),
    ]

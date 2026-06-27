from datetime import date
from django.db import transaction
from core.models import Sequence


@transaction.atomic
def generate_code(key, prefix=None):
    current_year = date.today().year

    sequence, created = Sequence.objects.select_for_update().get_or_create(
        key=key,
        defaults={
            "prefix": prefix or key.upper(),
            "current_number": 0,
            "padding": 6,
            "yearly_reset": True,
        }
    )

    sequence.current_number += 1
    sequence.save()

    number = str(sequence.current_number).zfill(sequence.padding)

    if sequence.yearly_reset:
        return f"{sequence.prefix}-{current_year}-{number}"

    return f"{sequence.prefix}-{number}"

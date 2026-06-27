from datetime import datetime
from core.models import Sequence


def generate_application_number():
    year = datetime.now().year

    seq, _ = Sequence.objects.get_or_create(
        key=f"admission_{year}",
        defaults={
            "prefix": f"ADM-{year}-",
            "next_number": 1,
            "digits": 6,
            "yearly_reset": True,
        },
    )

    number = f"{seq.prefix}{str(seq.next_number).zfill(seq.digits)}"

    seq.next_number += 1
    seq.save()

    return number

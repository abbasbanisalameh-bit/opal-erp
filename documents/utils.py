from datetime import datetime
from documents.models import IssuedDocument


def generate_document_number():
    year = datetime.now().year
    last = IssuedDocument.objects.filter(
        document_number__startswith=f"DOC-{year}"
    ).count() + 1

    return f"DOC-{year}-{last:05d}"

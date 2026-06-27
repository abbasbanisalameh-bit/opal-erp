from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import FileResponse

from academics.models import StudentRecord
from .models import IssuedDocument
from .utils import generate_document_number
from .services.pdf import student_certificate


@login_required
def document_list(request):
    documents = IssuedDocument.objects.all()
    return render(request, "documents/document_list.html", {
        "documents": documents,
    })


@login_required
def issue_student_certificate(request, student_id):
    student = StudentRecord.objects.get(pk=student_id)

    number = generate_document_number()

    IssuedDocument.objects.create(
        student=student,
        applicant_name=student.full_name,
        document_number=number,
        title="إثبات طالب",
        content="Student Certificate",
        issued_by=request.user,
    )

    pdf = student_certificate(student, number)

    return FileResponse(
        pdf,
        filename=f"{number}.pdf",
        content_type="application/pdf",
    )

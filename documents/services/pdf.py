from io import BytesIO
import qrcode

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def make_qr(data):
    img = qrcode.make(data)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def student_certificate(student, document_number):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    verify_url = f"https://opalschool2016.pythonanywhere.com/documents/verify/{document_number}/"

    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 2 * cm, "OPAL INTERNATIONAL SCHOOL")

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 3.2 * cm, "Student Certificate")

    p.setFont("Helvetica", 11)
    p.drawString(2 * cm, height - 4.5 * cm, f"Document No: {document_number}")

    qr = make_qr(verify_url)
    p.drawImage(qr, width - 4 * cm, height - 5.2 * cm, 2.5 * cm, 2.5 * cm)

    p.line(2 * cm, height - 5.5 * cm, width - 2 * cm, height - 5.5 * cm)

    y = height - 7 * cm
    p.setFont("Helvetica", 13)

    p.drawString(2 * cm, y, f"Student Name: {student.full_name}")
    y -= 1 * cm
    p.drawString(2 * cm, y, f"Student Number: {student.student_number}")
    y -= 1 * cm
    p.drawString(2 * cm, y, f"National ID: {student.national_id or '-'}")
    y -= 1 * cm
    p.drawString(2 * cm, y, f"Guardian: {student.father_name or '-'}")
    y -= 1.5 * cm

    text = f"This is to certify that {student.full_name} is enrolled at OPAL International School."
    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, y, text)

    p.line(2 * cm, 5 * cm, width - 2 * cm, 5 * cm)
    p.setFont("Helvetica", 11)
    p.drawString(2 * cm, 4 * cm, "Principal Signature")
    p.drawRightString(width - 2 * cm, 4 * cm, "School Stamp")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

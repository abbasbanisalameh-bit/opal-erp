from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm


def receipt_pdf(receipt):
    buffer = BytesIO()

    p = canvas.Canvas(buffer, pagesize=A4)

    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(300, 800, "OPAL INTERNATIONAL SCHOOL")

    p.setFont("Helvetica-Bold", 15)
    p.drawCentredString(300, 770, "Payment Receipt")

    p.setFont("Helvetica", 12)

    y = 720

    p.drawString(2 * cm, y, f"Receipt No: {receipt.receipt_number}")
    y -= 25

    p.drawString(2 * cm, y, f"Student: {receipt.payment.invoice.student.full_name}")
    y -= 25

    p.drawString(2 * cm, y, f"Amount: {receipt.payment.amount}")
    y -= 25

    p.drawString(2 * cm, y, f"Date: {receipt.created_at.strftime('%Y-%m-%d')}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return buffer

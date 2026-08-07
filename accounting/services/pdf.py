from io import BytesIO

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def _draw_receipt_copy(pdf, receipt, *, x, y, width, height, copy_label):
    payment = receipt.payment
    student = payment.invoice.student

    pdf.setLineWidth(1.2)
    pdf.roundRect(x, y, width, height, 10, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(x + width - 14, y + height - 18, copy_label)

    center = x + (width / 2)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawCentredString(center, y + height - 42, "OPAL INTERNATIONAL SCHOOL")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawCentredString(center, y + height - 64, "PAYMENT RECEIPT")

    line_y = y + height - 86
    pdf.line(x + 18, line_y, x + width - 18, line_y)
    pdf.setFont("Helvetica", 10.5)
    rows = [
        ("Receipt No", receipt.receipt_number),
        ("Student", student.full_name),
        ("Student No", getattr(student, "student_number", "") or "-"),
        ("Amount", f"{payment.amount} JOD"),
        ("Payment Method", payment.get_payment_method_display()),
        ("Date", receipt.created_at.strftime("%Y-%m-%d %H:%M")),
        ("Received By", getattr(payment.created_by, "username", "") or "System"),
    ]
    cursor = line_y - 30
    for label, value in rows:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x + 24, cursor, f"{label}:")
        pdf.setFont("Helvetica", 10)
        text = str(value)
        if len(text) > 48:
            text = text[:45] + "..."
        pdf.drawString(x + 118, cursor, text)
        cursor -= 24

    cursor -= 4
    pdf.line(x + 24, cursor, x + width - 24, cursor)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(center, cursor - 18, "This receipt is stored in OPAL ERP and can be reprinted from the payment archive.")

    signature_y = y + 44
    half = width / 2
    pdf.line(x + 28, signature_y, x + half - 18, signature_y)
    pdf.line(x + half + 18, signature_y, x + width - 28, signature_y)
    pdf.setFont("Helvetica", 9)
    pdf.drawCentredString(x + half / 2, signature_y - 15, "Guardian Signature")
    pdf.drawCentredString(x + half + half / 2, signature_y - 15, "Receiver Signature")


def receipt_pdf(receipt):
    """Return the legacy receipt as two copies on one A4 landscape page."""
    buffer = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    margin = 0.7 * cm
    gap = 0.55 * cm
    copy_width = (page_width - (2 * margin) - gap) / 2
    copy_height = page_height - (2 * margin)

    _draw_receipt_copy(
        pdf,
        receipt,
        x=margin,
        y=margin,
        width=copy_width,
        height=copy_height,
        copy_label="SCHOOL COPY",
    )
    _draw_receipt_copy(
        pdf,
        receipt,
        x=margin + copy_width + gap,
        y=margin,
        width=copy_width,
        height=copy_height,
        copy_label="GUARDIAN COPY",
    )

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer

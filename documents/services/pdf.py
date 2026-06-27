from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO


def student_certificate(student, document_number):
    buffer = BytesIO()

    pdf = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    story = []

    story.append(Paragraph("OPAL INTERNATIONAL SCHOOL", styles["Heading1"]))
    story.append(Paragraph("Student Certificate", styles["Heading2"]))
    story.append(Paragraph(f"Document No: {document_number}", styles["Normal"]))
    story.append(Paragraph("<br/><br/>", styles["Normal"]))

    story.append(
        Paragraph(
            f"This is to certify that <b>{student.full_name}</b> is enrolled at OPAL International School.",
            styles["BodyText"],
        )
    )

    pdf.build(story)

    buffer.seek(0)

    return buffer

from django.http import HttpResponse
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from datetime import datetime
from decimal import Decimal
from reportlab.pdfgen import canvas
from io import BytesIO
from django.conf import settings
import os
from reportlab.platypus import Image


# =====================================================
# MAIN DOWNLOAD PDF
# =====================================================



def generate_payslip_pdf(payslip):

    response = HttpResponse(content_type="application/pdf")
    filename = f"Payslip_{payslip.employee.employee_id}_{payslip.month}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    elements = []
    styles = getSampleStyleSheet()

    # =====================================================
    # 🔥 ADD COMPANY LOGO
    # =====================================================

    logo_path = os.path.join(
        settings.BASE_DIR,
        "static",
        "company",
        "logo.png"
    )

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=120, height=60)
        logo.hAlign = "CENTER"
        elements.append(logo)
        elements.append(Spacer(1, 0.2 * inch))

    # =====================================================
    # COMPANY HEADER
    # =====================================================

    header_style = styles["Heading1"]
    header_style.alignment = 1  # center

    elements.append(Paragraph("GMMC HRMS", header_style))
    elements.append(Spacer(1, 0.2 * inch))

    elements.append(Paragraph("Salary Payslip", styles["Heading2"]))
    elements.append(Spacer(1, 0.3 * inch))
# =====================================================
# BUFFER VERSION (ZIP / EMAIL)
# =====================================================

def generate_payslip_pdf_buffer(payslip):

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "PAYSLIP")
    y -= 40

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Employee: {payslip.employee.first_name} {payslip.employee.last_name}")
    y -= 20
    c.drawString(50, y, f"Month: {payslip.month.strftime('%B %Y')}")
    y -= 30

    c.drawString(50, y, f"Gross Salary: ₹ {payslip.gross_salary}")
    y -= 20
    c.drawString(50, y, f"Working Days: {payslip.working_days}")
    y -= 20
    c.drawString(50, y, f"Absent: {payslip.absent_days}")
    y -= 20
    c.drawString(50, y, f"Half Days: {payslip.half_days}")
    y -= 20
    c.drawString(50, y, f"Late: {payslip.late_days}")
    y -= 20
    c.drawString(50, y, f"Attendance Deduction: ₹ {payslip.attendance_deduction}")
    y -= 20
    c.drawString(50, y, f"Late Penalty: ₹ {payslip.late_penalty}")
    y -= 20
    c.drawString(50, y, f"Fixed Deductions: ₹ {payslip.fixed_deductions}")
    y -= 30

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, f"Net Pay: ₹ {payslip.net_pay}")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer
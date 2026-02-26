from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from datetime import datetime


def generate_payslip_pdf(payslip):

    response = HttpResponse(content_type="application/pdf")
    filename = f"Payslip_{payslip.employee.user.username}_{payslip.month}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    c = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 50

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, y, "PAYSLIP")
    y -= 40

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Employee: {payslip.employee.user.username}")
    y -= 20
    c.drawString(50, y, f"Employee ID: {payslip.employee.employee_id}")
    y -= 20
    c.drawString(50, y, f"Month: {payslip.month.strftime('%Y-%m')}")
    y -= 30

    c.drawString(50, y, f"Basic: ₹ {payslip.basic}")
    y -= 20
    c.drawString(50, y, f"HRA: ₹ {payslip.hra}")
    y -= 20
    c.drawString(50, y, f"Allowances: ₹ {payslip.allowances}")
    y -= 20
    c.drawString(50, y, f"Deductions: ₹ {payslip.deductions}")
    y -= 30

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Net Pay: ₹ {payslip.net_pay}")
    y -= 40

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(
        50,
        y,
        f"Generated on {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    )

    c.showPage()
    c.save()

    return response

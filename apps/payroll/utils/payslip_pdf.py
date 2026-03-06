from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from io import BytesIO
from num2words import num2words
from calendar import monthrange
from django.conf import settings
import os


def generate_payslip_pdf(payslip):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20,
        rightMargin=20,
        topMargin=20,
        bottomMargin=20
    )

    styles = getSampleStyleSheet()
    elements = []

    employee = payslip.employee
    month_text = payslip.month.strftime("%B %Y")

    # ==============================
    # HEADER WITH LOGO
    # ==============================

    logo_path = os.path.join(settings.BASE_DIR, "static", "company-logo.png")

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=40 * mm, height=15 * mm)
    else:
        logo = Paragraph("", styles["Normal"])

    header_table = Table([
        [
            Paragraph("<b>GMMC Company Pvt Ltd</b>", styles["Title"])
        ],
        [
            Paragraph(
                f"Pay Slip for the Month of {month_text}",
                styles["Normal"]
            )
        ]
    ], colWidths=[180*mm])

    header_table.setStyle(TableStyle([
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("BOX",(0,0),(-1,-1),1,colors.black),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1,10))

    # ==============================
    # EMPLOYEE DETAILS
    # ==============================

    total_days = monthrange(payslip.month.year, payslip.month.month)[1]

    emp_data = [
        ["EMPCODE", getattr(employee, "employee_id", ""), "PF NO", getattr(employee, "pf_number", "")],
        ["EMPNAME", getattr(employee, "first_name", ""), "STD DAYS", total_days],
        ["DESIGNATION", getattr(employee, "designation", ""), "WRK DAYS", total_days],
        ["DOJ", getattr(employee, "date_of_joining", ""), "LOP DAYS", payslip.lop_days],
        ["BUSINESS UNIT", getattr(employee, "department", ""), "BANK NAME", getattr(employee, "bank_name", "")],
        ["PAN", getattr(employee, "pan_number", ""), "ACCOUNT NO", getattr(employee, "bank_account_number", "")],
        ["LOCATION", getattr(employee, "location", ""), "UAN", getattr(employee, "uan_number", "")],
    ]

    emp_table = Table(emp_data, colWidths=[40*mm,50*mm,40*mm,50*mm])

    emp_table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.5,colors.black),
    ]))

    elements.append(emp_table)
    elements.append(Spacer(1, 10))

    # ==============================
    # EARNINGS + DEDUCTIONS
    # ==============================

    # ==============================
# EARNINGS + DEDUCTIONS
# ==============================

    earnings = [
        ["BASIC", payslip.basic],
        ["FIXED ALLOWANCES", payslip.special_allowance],
        ["FOOD ALLOWANCES", getattr(payslip, "food_allowance", 0)],
        ["HOUSE RENT ALLOWANCE", payslip.hra],
        ["MEDICAL ALLOWANCE", payslip.medical],
        ["TELEPHONE ALLOWANCE", getattr(payslip, "telephone_allowance", 0)],
        ["TRANSPORTATION ALLOWANCE", payslip.conveyance],
    ]

    deductions = [
        ["PROVIDENT FUND", payslip.employee_pf],
        ["LABOUR WELFARE FUND", getattr(payslip, "labour_welfare_fund", 0)],
        ["PROFESSIONAL TAX", payslip.professional_tax],
        ["ESI", payslip.employee_esi],
        ["TDS", payslip.tds_amount],
        ["LOP DEDUCTION", payslip.lop_deduction],
    ]

    max_rows = max(len(earnings), len(deductions))

    table_data = [
        ["EARNINGS", "AMOUNT", "YTD", "DEDUCTIONS", "AMOUNT", "YTD"]
    ]

    for i in range(max_rows):

        earn = earnings[i] if i < len(earnings) else ["", 0]
        ded = deductions[i] if i < len(deductions) else ["", 0]

        table_data.append([
            earn[0],
            f"{float(earn[1] or 0):,.2f}",
            "",
            ded[0],
            f"{float(ded[1] or 0):,.2f}",
            ""
        ])

    earn_ded_table = Table(
        table_data,
        colWidths=[65*mm, 30*mm, 25*mm, 65*mm, 30*mm, 25*mm]
    )

    earn_ded_table.setStyle(TableStyle([

        ("GRID", (0,0), (-1,-1), 0.5, colors.black),

        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),

        ("FONTNAME", (0,-1), (-1,-1), "Helvetica-Bold"),

        ("ALIGN", (1,1), (1,-1), "RIGHT"),
        ("ALIGN", (4,1), (4,-1), "RIGHT"),

    ]))

    elements.append(earn_ded_table)

    # ==============================
    # GROSS ROW
    # ==============================

    gross_deductions = (
    float(payslip.employee_pf or 0)
    + float(payslip.employee_esi or 0)
    + float(payslip.professional_tax or 0)
    + float(payslip.tds_amount or 0)
    + float(payslip.lop_deduction or 0)
)

    gross_table = Table([
        [
            "GROSS EARNINGS",
            f"{float(payslip.gross_salary or 0):,.2f}",
            "",
            "GROSS DEDUCTION",
            f"{float(gross_deductions):,.2f}",
            ""
        ]
    ], colWidths=[65*mm, 30*mm, 25*mm, 65*mm, 30*mm, 25*mm])

    gross_table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.5,colors.black),
        ("BACKGROUND",(0,0),(-1,-1),colors.whitesmoke),
    ]))

    elements.append(gross_table)
    elements.append(Spacer(1, 10))

    # ==============================
    # NET PAY
    # ==============================

    net_table = Table(
        [["NET PAY", f"₹ {payslip.net_pay:,.2f}"]],
        colWidths=[130*mm, 80*mm]
    )

    net_table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),1,colors.black),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),14),
        ("ALIGN",(1,0),(1,0),"RIGHT"),
    ]))

    elements.append(net_table)

    # ==============================
    # IN WORDS
    # ==============================

    words = num2words(float(payslip.net_pay), lang="en_IN").title()

    elements.append(
        Paragraph(
            f"<b>IN WORDS :</b> Rupees {words} Only",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 20))

    # ==============================
    # FOOTER
    # ==============================

    elements.append(
        Paragraph(
            "This is a computer generated document, hence no signature is required.",
            styles["Italic"]
        )
    )

    doc.build(elements)

    buffer.seek(0)

    return buffer.getvalue()
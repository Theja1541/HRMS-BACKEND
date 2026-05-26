from calendar import monthrange
from io import BytesIO

from django.conf import settings
from num2words import num2words
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


DOC_WIDTH = 180 * mm


def _to_money(value):
    return f"{float(value or 0):,.2f}"


def _mask_account(account_number):
    account_number = str(account_number or "").strip()
    if not account_number:
        return "-"
    if len(account_number) <= 4:
        return account_number
    return f"{'X' * (len(account_number) - 4)}{account_number[-4:]}"


def _safe_text(value, fallback="-"):
    text = str(value).strip() if value is not None else ""
    return text if text else fallback


def _employee_name(employee):
    first = str(getattr(employee, "first_name", "") or "").strip()
    last = str(getattr(employee, "last_name", "") or "").strip()
    full = f"{first} {last}".strip()
    return full if full else _safe_text(getattr(employee, "employee_id", ""), "Employee")


def _build_company_logo(company):
    logo_field = getattr(company, "logo", None)
    if not logo_field or not getattr(logo_field, "name", None):
        return ""
    try:
        with logo_field.storage.open(logo_field.name, "rb") as handle:
            data = handle.read()
        if not data:
            return ""
        image_buffer = BytesIO(data)
        with PILImage.open(BytesIO(data)) as pil_img:
            width_px, height_px = pil_img.size
        max_w = 24 * mm
        max_h = 12 * mm
        if width_px <= 0 or height_px <= 0:
            return ""
        scale = min(float(max_w) / float(width_px), float(max_h) / float(height_px))
        draw_w = max(1, width_px * scale)
        draw_h = max(1, height_px * scale)
        return Image(image_buffer, width=draw_w, height=draw_h)
    except Exception:
        return ""


def generate_payslip_pdf(payslip):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    employee = payslip.employee
    company = getattr(employee, "company", None) or getattr(payslip, "company", None)
    if not company:
        from apps.accounts.models import Company
        company = Company.objects.first()
        
    month_text = payslip.month.strftime("%B %Y")
    total_days = monthrange(payslip.month.year, payslip.month.month)[1]
    company_name = _safe_text(getattr(company, "name", None), getattr(settings, "PAYSLIP_COMPANY_NAME", "HRMS Company"))

    title_style = ParagraphStyle(
        "PayslipTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        alignment=1,
        leading=17,
    )
    subtitle_style = ParagraphStyle(
        "PayslipSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        alignment=1,
        leading=14,
    )
    footer_style = ParagraphStyle(
        "PayslipFooter",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        alignment=1,
    )

    logo_cell = ""
    logo_cell = _build_company_logo(company)

    header_right = Paragraph(
        f"<b>{company_name}</b><br/>Pay Slip for the Month of {month_text}",
        title_style,
    )

    header_table = Table([[logo_cell, header_right]], colWidths=[30 * mm, 150 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("ALIGN", (1, 0), (1, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(header_table)

    doj = employee.joining_date.strftime("%d/%m/%Y") if getattr(employee, "joining_date", None) else "-"
    left_emp_rows = [
        ["EMPCODE", _safe_text(getattr(employee, "employee_id", ""), "-")],
        ["EMPNAME", _employee_name(employee)],
        ["DESIGNATION", _safe_text(getattr(employee, "designation", ""), "-")],
        ["DOJ", doj],
        ["BUSINESS UNIT", _safe_text(getattr(employee, "department", ""), "-")],
        ["PAN", _safe_text(getattr(employee, "pan", ""), "-")],
        ["LOCATION", _safe_text(getattr(employee, "work_location", ""), "-")],
    ]
    right_emp_rows = [
        ["PF NO", _safe_text(getattr(employee, "pf_number", ""), "-")],
        ["STD DAYS", str(total_days)],
        ["WRK DAYS", str(total_days)],
        ["LOP DAYS", f"{float(getattr(payslip, 'lop_days', 0) or 0):.0f}"],
        ["BANK NAME", _safe_text(getattr(employee, "bank_name", ""), "-")],
        ["ACCOUNT NO", _mask_account(getattr(employee, "account_number", ""))],
        ["UAN", _safe_text(getattr(employee, "uan_number", ""), "-")],
    ]

    emp_data = []
    for idx in range(max(len(left_emp_rows), len(right_emp_rows))):
        left = left_emp_rows[idx] if idx < len(left_emp_rows) else ["", ""]
        right = right_emp_rows[idx] if idx < len(right_emp_rows) else ["", ""]
        emp_data.append([left[0], left[1], right[0], right[1]])

    emp_table = Table(emp_data, colWidths=[32 * mm, 58 * mm, 32 * mm, 58 * mm])
    emp_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(emp_table)

    earnings = [
        ["BASIC", float(payslip.basic or 0)],
        ["FIXED ALLOWANCES", float(payslip.special_allowance or 0)],
        ["FOOD ALLOWANCES", float(payslip.da or 0)],
        ["HOUSE RENT ALLOWANCE", float(payslip.hra or 0)],
        ["MEDICAL ALLOWANCE", float(payslip.medical or 0)],
        ["TELEPHONE ALLOWANCE", 1000.00],
        ["TRANSPORT ALLOWANCE", float(payslip.conveyance or 0)],
    ]
    deductions = [
        ["PROVIDENT FUND (Employee)", float(payslip.employee_pf or 0)],
        ["PROVIDENT FUND (Employeer)", float(payslip.employer_pf or 0)],
        ["PROFESSIONAL TAX", float(payslip.professional_tax or 0)],
        ["ESI", float(payslip.employee_esi or 0)],
        ["TDS", float(payslip.tds_amount or 0)],
        ["LOP DEDUCTION", float(payslip.lop_deduction or 0)],
    ]

    table_data = [["EARNINGS", "AMOUNT", "DEDUCTIONS", "AMOUNT"]]
    max_rows = max(len(earnings), len(deductions))
    for i in range(max_rows):
        earn = earnings[i] if i < len(earnings) else ["", 0.0]
        ded = deductions[i] if i < len(deductions) else ["", 0.0]
        # Use label presence, not truthiness of amount: 0.00 must show (e.g. LOP, ESI).
        earn_amt = _to_money(earn[1]) if earn[0] else ""
        ded_amt = _to_money(ded[1]) if ded[0] else ""
        table_data.append([earn[0], earn_amt, ded[0], ded_amt])

    earning_deduction_table = Table(
        table_data,
        colWidths=[72 * mm, 24 * mm, 60 * mm, 24 * mm],
    )
    earning_deduction_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("ALIGN", (2, 0), (2, -1), "LEFT"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
            ]
        )
    )
    elements.append(earning_deduction_table)

    gross_earnings = float(payslip.gross_salary or 0)
    employer_pf = float(payslip.employer_pf or 0)
    gross_deductions = (
        float(payslip.employee_pf or 0)
        + float(payslip.professional_tax or 0)
        + float(payslip.employee_esi or 0)
        + float(payslip.tds_amount or 0)
        + float(payslip.lop_deduction or 0)
    )
    total_payable = gross_earnings + employer_pf
    net_pay = gross_earnings - gross_deductions
    if net_pay < 0:
        net_pay = 0.0
    gross_table = Table(
        [
            [
                "GROSS EARNINGS",
                _to_money(gross_earnings),
                "GROSS DEDUCTION",
                _to_money(gross_deductions),
            ]
        ],
        colWidths=[72 * mm, 24 * mm, 60 * mm, 24 * mm],
    )
    gross_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("ALIGN", (3, 0), (3, 0), "RIGHT"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f2f2")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(gross_table)

    total_payable_table = Table([["TOTAL PAYABLE", f"₹{_to_money(total_payable)}"]], colWidths=[120 * mm, 60 * mm])
    total_payable_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    elements.append(total_payable_table)

    net_pay_table = Table([["NET PAY", f"₹{_to_money(net_pay)}"]], colWidths=[120 * mm, 60 * mm])
    net_pay_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(net_pay_table)

    try:
        words = num2words(net_pay, lang="en_IN").title()
    except Exception:
        words = "Amount In Words Not Available"

    words_table = Table(
        [[Paragraph(f"IN WORDS : <b>Rupees {words} Only</b>", subtitle_style)]],
        colWidths=[DOC_WIDTH],
    )
    words_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(words_table)
    elements.append(Spacer(1, 8))

    elements.append(
        Paragraph(
            "This is a computer generated document, hence no signature is required.",
            footer_style,
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
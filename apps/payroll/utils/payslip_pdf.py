from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
        leftMargin=15*mm,
        rightMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    styles = getSampleStyleSheet()
    elements = []
    
    employee = payslip.employee
    month_text = payslip.month.strftime("%B %Y")
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,  # Center
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        alignment=1,  # Center
        fontName='Helvetica',
        spaceAfter=10
    )
    
    # ==============================
    # HEADER WITH LOGO AND COMPANY INFO
    # ==============================
    
    # Header without logo
    header_data = [[
        Paragraph("<b>Genius Minds Making Code Pvt Ltd</b>", title_style)
    ]]
    header_table = Table(header_data, colWidths=[180*mm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(header_table)
    
    # Pay slip title
    payslip_title = Table([[
        Paragraph(f"Pay Slip for the Month of {month_text}", subtitle_style)
    ]], colWidths=[180*mm])
    
    payslip_title.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5)
    ]))
    
    elements.append(payslip_title)
    elements.append(Spacer(1, 5))
    
    # ==============================
    # EMPLOYEE DETAILS
    # ==============================
    
    total_days = monthrange(payslip.month.year, payslip.month.month)[1]
    
    # Format date of joining
    doj_formatted = ""
    if hasattr(employee, 'joining_date') and employee.joining_date:
        doj_formatted = employee.joining_date.strftime("%d/%m/%Y")
    
    # Format bank account number with masking
    bank_account = getattr(employee, 'account_number', '')
    if bank_account and len(bank_account) > 4:
        masked_account = bank_account[-4:].rjust(len(bank_account), 'X')
    else:
        masked_account = bank_account
    
    emp_data = [
        ["EMPCODE", f": {getattr(employee, 'employee_id', '')}", "PF NO", f": {getattr(employee, 'pf_number', '')}"],
        ["EMPNAME", f": {getattr(employee, 'first_name', '')} {getattr(employee, 'last_name', '')}", "STD DAYS", f": {total_days}"],
        ["DESIGNATION", f": {getattr(employee, 'designation', '')}", "WRK DAYS", f": {total_days}"],
        ["DOJ", f": {doj_formatted}", "LOP DAYS", f": {payslip.lop_days}"],
        ["BUSINESS UNIT", f": {getattr(employee, 'department', 'IT')}", "BANK NAME", f": {getattr(employee, 'bank_name', 'HDFC Bank')}"],
        ["PAN", f": {getattr(employee, 'pan', '')}", "ACCOUNT NO", f": {masked_account}"],
        ["LOCATION", f": {getattr(employee, 'work_location', 'Bengaluru')}", "UAN", f": {getattr(employee, 'uan_number', '')[:6] + 'xxx' if getattr(employee, 'uan_number', '') else ''}"]
    ]
    
    emp_table = Table(emp_data, colWidths=[45*mm, 45*mm, 45*mm, 45*mm])
    
    emp_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),  # Left column bold
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),  # Third column bold
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
    ]))
    
    elements.append(emp_table)
    elements.append(Spacer(1, 5))
    
    # ==============================
    # EARNINGS + DEDUCTIONS TABLE
    # ==============================
    
    # Calculate YTD values (assuming 12 months for example)
    ytd_multiplier = 12
    
    # Earnings data
    earnings = [
        ["BASIC", float(payslip.basic or 0), float(payslip.basic or 0) * ytd_multiplier],
        ["FIXED ALLOWANCES", float(payslip.special_allowance or 0), float(payslip.special_allowance or 0) * ytd_multiplier],
        ["FOOD ALLOWANCES", float(payslip.da or 0), float(payslip.da or 0) * ytd_multiplier],
        ["HOUSE RENT ALLOWANCE", float(payslip.hra or 0), float(payslip.hra or 0) * ytd_multiplier],
        ["MEDICAL ALLOWANCE", float(payslip.medical or 0), float(payslip.medical or 0) * ytd_multiplier],
        ["TELEPHONE ALLOWANCE", 1000.00, 12000.00],  # Fixed as per template
        ["TRANSPORTATION ALLOWANCE", float(payslip.conveyance or 0), float(payslip.conveyance or 0) * ytd_multiplier]
    ]
    
    # Deductions data
    deductions = [
        ["PROVIDENT FUND", float(payslip.employee_pf or 0), float(payslip.employee_pf or 0) * ytd_multiplier],
        ["LABOUR WELFARE FUND", 200.00, 2400.00],  # Fixed as per template
        ["PROFESSIONAL TAX", float(payslip.professional_tax or 0), float(payslip.professional_tax or 0) * ytd_multiplier],
        ["ESI", float(payslip.employee_esi or 0), float(payslip.employee_esi or 0) * ytd_multiplier],
        ["TDS", float(payslip.tds_amount or 0), float(payslip.tds_amount or 0) * ytd_multiplier],
        ["LOP DEDUCTION", float(payslip.lop_deduction or 0), 0.00]
    ]
    
    # Create the main earnings/deductions table
    max_rows = max(len(earnings), len(deductions))
    
    table_data = [
        ["EARNINGS", "AMOUNT", "YTD", "DEDUCTIONS", "AMOUNT", "YTD"]
    ]
    
    for i in range(max_rows):
        earn = earnings[i] if i < len(earnings) else ["", 0, 0]
        ded = deductions[i] if i < len(deductions) else ["", 0, 0]
        
        table_data.append([
            earn[0],
            f"{earn[1]:,.2f}" if earn[1] else "",
            f"{earn[2]:,.2f}" if earn[2] else "",
            ded[0],
            f"{ded[1]:,.2f}" if ded[1] else "",
            f"{ded[2]:,.2f}" if ded[2] else ""
        ])
    
    earn_ded_table = Table(
        table_data,
        colWidths=[50*mm, 25*mm, 25*mm, 50*mm, 25*mm, 25*mm]
    )
    
    earn_ded_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header row bold
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (1, 1), (2, -1), 'RIGHT'),  # Right align amounts
        ('ALIGN', (4, 1), (5, -1), 'RIGHT'),  # Right align amounts
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
    ]))
    
    elements.append(earn_ded_table)
    
    # ==============================
    # GROSS TOTALS ROW
    # ==============================
    
    gross_earnings = float(payslip.gross_salary or 0)
    gross_earnings_ytd = gross_earnings * ytd_multiplier
    
    gross_deductions = (
        float(payslip.employee_pf or 0) +
        200.00 +  # Labour welfare fund
        float(payslip.professional_tax or 0) +
        float(payslip.employee_esi or 0) +
        float(payslip.tds_amount or 0) +
        float(payslip.lop_deduction or 0)
    )
    gross_deductions_ytd = gross_deductions * ytd_multiplier
    
    gross_table = Table([
        [
            "GROSS EARNINGS",
            f"{gross_earnings:,.2f}",
            f"{gross_earnings_ytd:,.2f}",
            "GROSS DEDUCTION",
            f"{gross_deductions:,.2f}",
            f"{gross_deductions_ytd:,.2f}"
        ]
    ], colWidths=[50*mm, 25*mm, 25*mm, 50*mm, 25*mm, 25*mm])
    
    gross_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (1, 0), (2, 0), 'RIGHT'),
        ('ALIGN', (4, 0), (5, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
    ]))
    
    elements.append(gross_table)
    elements.append(Spacer(1, 5))
    
    # ==============================
    # NET PAY
    # ==============================
    
    net_pay_table = Table([
        ["NET PAY", f"₹{float(payslip.net_pay):,.2f}"]
    ], colWidths=[140*mm, 40*mm])
    
    net_pay_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
    ]))
    
    elements.append(net_pay_table)
    elements.append(Spacer(1, 5))
    
    # ==============================
    # IN WORDS
    # ==============================
    
    try:
        words = num2words(float(payslip.net_pay), lang="en_IN").title()
    except:
        words = "Amount in words not available"
    
    words_table = Table([
        [f"IN WORDS : Rupees {words} Only"]
    ], colWidths=[180*mm])
    
    words_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5)
    ]))
    
    elements.append(words_table)
    elements.append(Spacer(1, 15))
    
    # ==============================
    # FOOTER
    # ==============================
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,  # Center
        fontName='Helvetica-Oblique'
    )
    
    elements.append(
        Paragraph(
            "This is a computer generated document, hence no signature is required.",
            footer_style
        )
    )
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
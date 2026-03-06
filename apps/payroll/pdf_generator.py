from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import io


def num2words_simple(n):
    """Simple number to words converter for Indian currency"""
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    
    if n == 0:
        return "Zero"
    
    n = int(n)
    
    def convert_hundreds(num):
        result = ""
        if num >= 100:
            result += ones[num // 100] + " Hundred "
            num %= 100
        if num >= 20:
            result += tens[num // 10] + " "
            num %= 10
        elif num >= 10:
            result += teens[num - 10] + " "
            return result
        if num > 0:
            result += ones[num] + " "
        return result
    
    if n >= 10000000:
        result = convert_hundreds(n // 10000000) + "Crore "
        n %= 10000000
    else:
        result = ""
    
    if n >= 100000:
        result += convert_hundreds(n // 100000) + "Lakh "
        n %= 100000
    
    if n >= 1000:
        result += convert_hundreds(n // 1000) + "Thousand "
        n %= 1000
    
    if n > 0:
        result += convert_hundreds(n)
    
    return result.strip()


def generate_payslip_pdf(payslip):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20, bottomMargin=20, leftMargin=30, rightMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # Company Header
    header_style = ParagraphStyle('Header', parent=styles['Heading1'], fontSize=12, alignment=1, spaceAfter=3, fontName='Helvetica-Bold')
    elements.append(Paragraph("<b>NEELBLUE TECHNOLOGIES INDIA PRIVATE LIMITED</b>", header_style))
    
    month_style = ParagraphStyle('Month', parent=styles['Normal'], fontSize=10, alignment=1, spaceAfter=8)
    elements.append(Paragraph(f"Pay Slip for the Month of {payslip.month.strftime('%B %Y')}", month_style))
    
    # Employee Details Table
    emp_data = [
        ["EMPCODE", f": {payslip.employee.employee_id}", "PF NO", f": {getattr(payslip.employee, 'pf_number', '')}"],
        ["EMPNAME", f": {payslip.employee.first_name} {payslip.employee.last_name}", "STDAYS", ": 31.00"],
        ["DESIGNATION", f": {getattr(payslip.employee, 'designation', 'Manager')}", "WRKDAYS", ": 31.00"],
        ["DOJ", f": {getattr(payslip.employee, 'date_of_joining', '').strftime('%d/%m/%Y') if hasattr(payslip.employee, 'date_of_joining') and payslip.employee.date_of_joining else ''}", "LOP DAYS", f": {payslip.lop_days:.2f}"],
        ["BUSINESS UNIT", ":", "BANK NAME", f": {getattr(payslip.employee, 'bank_name', 'ICICI Bank')}"],
        ["PAN", f": {getattr(payslip.employee, 'pan_number', '')}", "ACCOUNT NO", f": {getattr(payslip.employee, 'bank_account_number', '')}"],
        ["LOCATION", ": Hyderabad", "UAN", f": {getattr(payslip.employee, 'uan_number', '')}"],
    ]
    
    emp_table = Table(emp_data, colWidths=[90, 140, 90, 140])
    emp_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(emp_table)
    elements.append(Spacer(1, 8))

    # Earnings and Deductions Table
    ytd_multiplier = 12
    earnings_deductions_data = [
        ["EARNINGS", "AMOUNT", "YTD", "DEDUCTIONS", "AMOUNT", "YTD"],
        ["BASIC", f"{payslip.basic:.2f}", f"{payslip.basic * ytd_multiplier:.2f}", "PROVIDENT FUND", f"{payslip.employee_pf:.2f}", f"{payslip.employee_pf * ytd_multiplier:.2f}"],
        ["FIXED ALLOWANCES", f"{payslip.special_allowance:.2f}", f"{payslip.special_allowance * ytd_multiplier:.2f}", "LABOUR WELFARE FUND", "0.00", "2.00"],
        ["FOOD ALLOWANCES", f"{payslip.da:.2f}", f"{payslip.da * ytd_multiplier:.2f}", "PROFESSIONAL TAX", f"{payslip.professional_tax:.2f}", f"{payslip.professional_tax * ytd_multiplier:.2f}"],
        ["HOUSE RENT ALLOWANCE", f"{payslip.hra:.2f}", f"{payslip.hra * ytd_multiplier:.2f}", "", "", ""],
        ["MEDICAL ALLOWANCE", f"{payslip.medical:.2f}", f"{payslip.medical * ytd_multiplier:.2f}", "", "", ""],
        ["TELEPHONE ALLOWANCE", "0.00", "0.00", "", "", ""],
        ["TRANSPORTATION ALLOWANCE", f"{payslip.conveyance:.2f}", f"{payslip.conveyance * ytd_multiplier:.2f}", "", "", ""],
        ["GROSS EARNINGS", f"{payslip.gross_salary:.2f}", f"{payslip.gross_salary * ytd_multiplier:.2f}", "GROSS DEDUCTION", f"{payslip.employee_pf + payslip.professional_tax:.2f}", f"{(payslip.employee_pf + payslip.professional_tax) * ytd_multiplier:.2f}"],
    ]
    
    earnings_table = Table(earnings_deductions_data, colWidths=[115, 60, 60, 115, 60, 60])
    earnings_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (0, -1), (2, -1), colors.lightgrey),
        ('BACKGROUND', (3, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 1), (2, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (5, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(earnings_table)
    elements.append(Spacer(1, 8))

    # Net Pay
    net_pay_data = [[f"NET PAY  : {payslip.net_pay:.2f}"]]
    net_pay_table = Table(net_pay_data, colWidths=[470])
    net_pay_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(net_pay_table)
    elements.append(Spacer(1, 3))

    # In Words
    words = num2words_simple(payslip.net_pay)
    words_data = [[f"IN WORDS  : Rupees {words} Only"]]
    words_table = Table(words_data, colWidths=[470])
    words_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(words_table)
    elements.append(Spacer(1, 10))

    # Footer
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=7, alignment=1)
    elements.append(Paragraph("This is a computer generated document, hence no signature is required.", footer_style))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

import csv
import io
from datetime import datetime


SUPPORTED_BANKS = {"SBI", "HDFC", "ICICI"}


def _parse_month(month):
    if isinstance(month, datetime):
        return month
    if hasattr(month, "year") and hasattr(month, "month"):
        return datetime(month.year, month.month, 1)
    return datetime.strptime(str(month), "%Y-%m")


def _build_reference(month_dt):
    return f"Salary{month_dt.strftime('%b')}{month_dt.year}"


def generate_bank_salary_file(bank, employees, company_account, month):
    bank_name = (bank or "").upper()
    if bank_name not in SUPPORTED_BANKS:
        raise ValueError(f"Unsupported bank '{bank}'. Supported banks: SBI, HDFC, ICICI")

    month_dt = _parse_month(month)
    transaction_date = datetime(month_dt.year, month_dt.month, 28).strftime("%d/%m/%Y")
    salary_reference = _build_reference(month_dt)

    output = io.StringIO()
    writer = csv.writer(output)

    if bank_name == "SBI":
        writer.writerow([
            "Debit Account Number",
            "Transaction Amount",
            "Transaction Currency",
            "Beneficiary Name",
            "Beneficiary Account Number",
            "Beneficiary IFSC Code",
            "Transaction Date",
            "Payment Mode",
            "Customer Reference Number",
            "Beneficiary Nickname",
        ])
        for emp in employees:
            writer.writerow([
                company_account,
                emp["net_pay"],
                "INR",
                emp["employee_name"],
                emp["account_number"],
                emp["ifsc"],
                transaction_date,
                "N",
                salary_reference,
                emp["employee_name"].replace(" ", ""),
            ])

    elif bank_name == "HDFC":
        writer.writerow([
            "Debit Account No",
            "Beneficiary Name",
            "Beneficiary Account No",
            "Beneficiary IFSC",
            "Amount",
            "Payment Details",
            "Remarks",
        ])
        for emp in employees:
            writer.writerow([
                company_account,
                emp["employee_name"],
                emp["account_number"],
                emp["ifsc"],
                emp["net_pay"],
                f"Salary for {month_dt.strftime('%B %Y')}",
                emp["employee_id"],
            ])

    else:  # ICICI
        writer.writerow([
            "Debit Account No",
            "Beneficiary Account No",
            "Beneficiary Name",
            "IFSC Code",
            "Amount",
            "Payment Mode",
            "Remarks",
        ])
        for emp in employees:
            writer.writerow([
                company_account,
                emp["account_number"],
                emp["employee_name"],
                emp["ifsc"],
                emp["net_pay"],
                "NEFT",
                salary_reference,
            ])

    filename = f"{bank_name}_Salary_{month_dt.strftime('%Y_%m')}.csv"
    return filename, output.getvalue()

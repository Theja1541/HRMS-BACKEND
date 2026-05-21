from .utils.payroll_calculations import calculate_payslip_totals


class PayrollCalculator:

    @staticmethod
    def calculate(employee, attendance_summary):
        salary = employee.salary
        lop_days = attendance_summary.get("deductible_days", 0)
        year = attendance_summary.get("year")
        month = attendance_summary.get("month")
        totals = calculate_payslip_totals(salary, year, month, lop_days)

        return {
            "earnings": {
                "gross_salary": totals["gross_salary"],
                "lop_deduction": totals["lop_deduction"],
            },
            "deductions": {
                "employee_pf": totals["employee_pf"],
                "employer_pf": totals["employer_pf"],
                "employee_esi": totals["employee_esi"],
                "employer_esi": totals["employer_esi"],
                "professional_tax": totals["professional_tax"],
                "lop_days": totals["lop_days"],
                "fixed_deductions": totals["base_deductions"],
            },
            "net_salary": totals["net_pay"],
            "additional_benefits": {
                "ctc": totals["ctc"],
            },
            "ctc": totals["ctc"],
        }
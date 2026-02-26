from decimal import Decimal


def calculate_new_regime_tax(annual_income):

    tax = Decimal("0")

    slabs = [
        (300000, 0),
        (600000, 0.05),
        (900000, 0.10),
        (1200000, 0.15),
        (1500000, 0.20),
    ]

    previous_limit = 0

    for limit, rate in slabs:
        if annual_income > limit:
            taxable = limit - previous_limit
            tax += Decimal(taxable) * Decimal(rate)
            previous_limit = limit
        else:
            taxable = annual_income - previous_limit
            tax += Decimal(taxable) * Decimal(rate)
            return tax

    # Above 15L
    if annual_income > 1500000:
        tax += Decimal(annual_income - 1500000) * Decimal("0.30")

    return tax


def calculate_old_regime_tax(annual_income):

    tax = Decimal("0")

    slabs = [
        (250000, 0),
        (500000, 0.05),
        (1000000, 0.20),
    ]

    previous_limit = 0

    for limit, rate in slabs:
        if annual_income > limit:
            taxable = limit - previous_limit
            tax += Decimal(taxable) * Decimal(rate)
            previous_limit = limit
        else:
            taxable = annual_income - previous_limit
            tax += Decimal(taxable) * Decimal(rate)
            return tax

    if annual_income > 1000000:
        tax += Decimal(annual_income - 1000000) * Decimal("0.30")

    return tax


def calculate_monthly_tds(employee, annual_gross):

    salary = employee.salary

    # Standard deduction
    taxable_income = annual_gross - Decimal("50000")

    if salary.tax_regime == "NEW":
        annual_tax = calculate_new_regime_tax(taxable_income)
    else:
        # Simplified old regime (without investment logic yet)
        annual_tax = calculate_old_regime_tax(taxable_income)

    # 4% cess
    annual_tax += annual_tax * Decimal("0.04")

    monthly_tds = annual_tax / Decimal("12")

    return monthly_tds.quantize(Decimal("1"))
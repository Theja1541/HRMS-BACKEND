from decimal import Decimal

def calculate_new_regime_tax(annual_income):

    tax = Decimal("0")

    slabs = [
        (Decimal("300000"), Decimal("0.00")),
        (Decimal("600000"), Decimal("0.05")),
        (Decimal("900000"), Decimal("0.10")),
        (Decimal("1200000"), Decimal("0.15")),
        (Decimal("1500000"), Decimal("0.20")),
    ]

    previous_limit = Decimal("0")

    for limit, rate in slabs:
        if annual_income > limit:
            taxable = limit - previous_limit
            tax += taxable * rate
            previous_limit = limit
        else:
            taxable = annual_income - previous_limit
            tax += taxable * rate
            return tax

    # Above 15L
    if annual_income > Decimal("1500000"):
        tax += (annual_income - Decimal("1500000")) * Decimal("0.30")

    return tax


def calculate_old_regime_tax(annual_income):

    tax = Decimal("0")

    slabs = [
        (Decimal("250000"), Decimal("0.00")),
        (Decimal("500000"), Decimal("0.05")),
        (Decimal("1000000"), Decimal("0.20")),
    ]

    previous_limit = Decimal("0")

    for limit, rate in slabs:
        if annual_income > limit:
            taxable = limit - previous_limit
            tax += taxable * rate
            previous_limit = limit
        else:
            taxable = annual_income - previous_limit
            tax += taxable * rate
            return tax

    if annual_income > Decimal("1000000"):
        tax += (annual_income - Decimal("1000000")) * Decimal("0.30")

    return tax


def calculate_monthly_tds(employee, annual_gross):
    annual_gross = Decimal(str(annual_gross))

    # Standard deduction
    taxable_income = annual_gross - Decimal("50000")

    if taxable_income < 0:
        taxable_income = Decimal("0")

    # Get employee tax regime safely
    tax_regime = getattr(employee, "tax_regime", "NEW")

    if tax_regime == "NEW":
        annual_tax = calculate_new_regime_tax(taxable_income)
    else:
        # simplified old regime (no investments yet)
        annual_tax = calculate_old_regime_tax(taxable_income)

    # 4% health & education cess
    annual_tax += annual_tax * Decimal("0.04")

    monthly_tds = annual_tax / Decimal("12")

    return monthly_tds.quantize(Decimal("1"))
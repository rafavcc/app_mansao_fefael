"""Brazilian payroll taxes (INSS and IRRF) for a monthly gross salary.

Tables valid from January/2026:
- INSS: Portaria Interministerial MPS/MF nº 13/2026 (progressive, per bracket).
- IRRF: Lei 15.191/2025 (progressive table) and Lei 15.270/2025 (monthly reduction).
Update the constants below when the government publishes new values.
"""

# (upper limit of the bracket, rate)
INSS_BRACKETS = (
    (1621.00, 0.075),
    (2902.84, 0.09),
    (4354.27, 0.12),
    (8475.55, 0.14),
)
INSS_CEILING = INSS_BRACKETS[-1][0]

# (upper limit of the base, rate, deduction); the last bracket has no limit
IRRF_BRACKETS = (
    (2428.80, 0.0, 0.0),
    (2826.65, 0.075, 182.16),
    (3751.05, 0.15, 394.16),
    (4664.68, 0.225, 675.49),
    (float("inf"), 0.275, 908.73),
)
IRRF_DEPENDENT_DEDUCTION = 189.59
IRRF_SIMPLIFIED_DISCOUNT = 607.20  # 25% of the exempt bracket

# Lei 15.270/2025: reduction that zeroes the tax up to R$ 5.000 and fades out at R$ 7.350
REDUCTION_FULL_UNTIL = 5000.00
REDUCTION_MAX = 312.89
REDUCTION_ZERO_FROM = 7350.00
REDUCTION_BASE = 978.62
REDUCTION_FACTOR = 0.133145


def calculate_inss(gross: float) -> float:
    """Progressive INSS for employees: each rate applies only to its own bracket."""
    contribution = 0.0
    lower = 0.0
    for upper, rate in INSS_BRACKETS:
        if gross <= lower:
            break
        contribution += (min(gross, upper) - lower) * rate
        lower = upper
    return round(contribution, 2)


def _progressive_tax(base: float) -> float:
    for upper, rate, deduction in IRRF_BRACKETS:
        if base <= upper:
            return max(base * rate - deduction, 0.0)
    return 0.0


def _reduction(gross: float) -> float:
    if gross <= REDUCTION_FULL_UNTIL:
        return REDUCTION_MAX
    if gross < REDUCTION_ZERO_FROM:
        return max(REDUCTION_BASE - REDUCTION_FACTOR * gross, 0.0)
    return 0.0


def calculate_irrf(gross: float, inss: float, dependents: int = 0) -> float:
    """Monthly income tax withheld at source, using the most favorable deduction."""
    legal_deductions = inss + dependents * IRRF_DEPENDENT_DEDUCTION
    base = max(gross - max(legal_deductions, IRRF_SIMPLIFIED_DISCOUNT), 0.0)
    tax = round(_progressive_tax(base), 2)
    return round(max(tax - _reduction(gross), 0.0), 2)


def calculate_net_salary(gross: float, dependents: int = 0) -> dict:
    inss = calculate_inss(gross)
    irrf = calculate_irrf(gross, inss, dependents)
    return {
        "gross": round(gross, 2),
        "inss": inss,
        "irrf": irrf,
        "taxes": round(inss + irrf, 2),
        "net": round(gross - inss - irrf, 2),
    }

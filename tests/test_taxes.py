import pytest

from app.taxes import calculate_inss, calculate_irrf, calculate_net_salary


@pytest.mark.parametrize("gross, expected", [
    (0, 0),
    (1621.00, 121.575),
    (2902.84, 236.94),
    (4354.27, 411.11),
    (5000.00, 501.51),
    (8475.55, 988.09),
    (20000.00, 988.09),  # capped at the ceiling
])
def test_inss_is_progressive_and_capped(gross, expected):
    assert calculate_inss(gross) == pytest.approx(expected, abs=0.01)


# Examples published by Receita Federal for Lei 15.270/2025 (gross, INSS, expected IRRF)
@pytest.mark.parametrize("gross, inss, expected", [
    (3036.00, 257.73, 0.00),
    (4000.00, 373.41, 0.00),
    (5000.00, 509.60, 0.00),
    (6000.00, 649.60, 382.88),
    (7607.20, 0.00, 1016.27),
])
def test_irrf_matches_receita_examples(gross, inss, expected):
    assert calculate_irrf(gross, inss) == pytest.approx(expected, abs=0.01)


def test_no_tax_up_to_5000_with_real_inss():
    for gross in (1500, 3000, 4500, 5000):
        assert calculate_irrf(gross, calculate_inss(gross)) == 0


def test_reduction_fades_out_between_5000_and_7350():
    previous = 0.0
    for gross in range(5000, 7400, 50):
        tax = calculate_irrf(gross, calculate_inss(gross))
        assert tax >= previous - 0.01
        previous = tax


def test_dependents_reduce_tax_when_legal_deductions_win():
    without = calculate_irrf(10000, calculate_inss(10000))
    with_two = calculate_irrf(10000, calculate_inss(10000), dependents=2)
    assert with_two == pytest.approx(without - 2 * 189.59 * 0.275, abs=0.01)


def test_net_salary_breakdown_adds_up():
    pay = calculate_net_salary(8000, dependents=1)
    assert pay["net"] == pytest.approx(pay["gross"] - pay["inss"] - pay["irrf"])
    assert pay == {"gross": 8000, "inss": 921.51, "irrf": 985.72, "taxes": 1907.23, "net": 6092.77}


def test_tiny_salary_has_no_negative_values():
    pay = calculate_net_salary(100)
    assert pay["irrf"] == 0 and pay["net"] > 0

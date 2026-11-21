from datetime import date, timedelta

import pytest

from app.schemas import variable_expense_problem


def valid(**over) -> dict:
    today = date.today()
    data = {
        "place": "Mercado", "day": today.day, "month": today.month, "year": today.year,
        "value": 10.0, "paid_by": "FEFE", "category_name": "Comida", "notes": None,
    }
    data.update(over)
    return data


def test_valid_data_has_no_problem():
    assert variable_expense_problem(valid()) is None


def test_future_date_is_a_problem():
    tomorrow = date.today() + timedelta(days=1)
    data = valid(day=tomorrow.day, month=tomorrow.month, year=tomorrow.year)
    assert variable_expense_problem(data) == "A data não pode estar no futuro."


@pytest.mark.parametrize("over, message", [
    ({"place": "  "}, "Preencha o local."),
    ({"day": 31, "month": 4, "year": 2025}, "Data inválida."),
    ({"day": None}, "Data inválida."),
    ({"value": 0}, "Valor deve ser maior que zero."),
    ({"value": float("inf")}, "Valor deve ser maior que zero."),
    ({"value": float("nan")}, "Valor deve ser maior que zero."),
    ({"value": 10**400}, "Valor deve ser maior que zero."),
    ({"value": None}, "Valor deve ser maior que zero."),
    ({"category_name": None}, "Selecione um grupo."),
    ({"paid_by": "X"}, "Selecione quem pagou."),
    ({"place": "x" * 301}, "Dados inválidos."),
])
def test_each_problem_message(over, message):
    assert variable_expense_problem(valid(**over)) == message


def test_value_above_the_limit_is_too_high():
    from datetime import date
    from app.schemas import variable_expense_problem

    data = {"place": "x", "day": 1, "month": 1, "year": 2020, "value": 2_000_000,
            "paid_by": "FAFA", "category_name": "Outros"}
    assert variable_expense_problem(data) == "Valor muito alto."
    assert variable_expense_problem({**data, "value": 1_000_000}) is None
    assert variable_expense_problem({**data, "value": 1e308}) == "Valor muito alto."

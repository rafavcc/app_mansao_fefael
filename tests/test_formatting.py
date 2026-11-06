from datetime import date

import pytest

from app.formatting import (
    format_brl, format_date_br, format_number_br, format_pct, month_name, parse_date_br, parse_money,
)


@pytest.mark.parametrize("value, expected", [
    (0, "R$ 0,00"),
    (1234.5, "R$ 1.234,50"),
    (1234567.891, "R$ 1.234.567,89"),
    (-10, "-R$ 10,00"),
    (-0.001, "R$ 0,00"),
])
def test_format_brl(value, expected):
    assert format_brl(value) == expected


def test_format_number_and_pct():
    assert format_number_br(1234.5) == "1.234,50"
    assert format_pct(12.345) == "12,3%"
    assert format_pct(5, digits=0) == "5%"


@pytest.mark.parametrize("text, expected", [
    ("1.234,56", 1234.56),
    ("12,5", 12.5),
    ("12.50", 1250.0),
    ("R$ 30", 30.0),
    ("  7 ", 7.0),
    ("0", 0.0),
    ("", None),
    (None, None),
    ("abc", None),
    ("1,2,3", None),
])
def test_parse_money(text, expected):
    assert parse_money(text) == expected


def test_money_round_trip():
    assert parse_money(format_number_br(1234.56)) == 1234.56


def test_dates_and_months():
    assert format_date_br(date(2026, 1, 5)) == "05/01/2026"
    assert parse_date_br("05/01/2026") == date(2026, 1, 5)
    assert parse_date_br("31/02/2026") is None
    assert parse_date_br(None) is None
    assert month_name(3) == "Março" and month_name(3, short=True) == "Mar"

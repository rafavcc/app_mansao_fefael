from datetime import date, datetime
from typing import Optional

MONTHS_PT = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)
MONTHS_PT_SHORT = tuple(name[:3] for name in MONTHS_PT)

PAYER_LABELS = {"FAFA": "Fafa", "FEFE": "Fefe"}


def month_name(month: int, short: bool = False) -> str:
    return (MONTHS_PT_SHORT if short else MONTHS_PT)[month - 1]


def format_number_br(value: float) -> str:
    """1234.5 -> '1.234,50'"""
    text = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{text}" if round(value, 2) < 0 else text


def format_brl(value: float) -> str:
    """1234.5 -> 'R$ 1.234,50'; -10 -> '-R$ 10,00'."""
    text = format_number_br(value)
    if text.startswith("-"):
        return f"-R$ {text[1:]}"
    return f"R$ {text}"


def format_pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%".replace(".", ",")


def parse_money(text: Optional[str]) -> Optional[float]:
    """Parse user input such as '1.234,56', '12,5', '12.50' or 'R$ 30'. Returns None if invalid."""
    if text is None:
        return None
    cleaned = str(text).replace("R$", "").replace(".", "").replace(" ", "").strip()
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def format_date_br(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def parse_date_br(text: Optional[str]) -> Optional[date]:
    try:
        return datetime.strptime(text or "", "%d/%m/%Y").date()
    except ValueError:
        return None
from datetime import date
from typing import Callable, Optional

from nicegui import ui

from app import crud
from app.database import get_session
from app.formatting import format_brl, format_pct, month_name
from app.theme import card_classes

COLORS = {
    "variable": "#0ea5e9",
    "regular": "#8b5cf6",
    "FAFA": "#2563eb",
    "FEFE": "#e11d48",
    "previous": "#94a3b8",
}

# Mid-tone gray stays readable on both light and dark backgrounds.
CHART_TEXT = "#8a94a6"
CHART_GRID = "rgba(138, 148, 166, 0.25)"

BRL_JS = """
(v) => v == null ? "R$ -" : "R$ " + Number(v).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
})
"""

COMPACT_JS = "(v) => Number(v).toLocaleString('pt-BR', {notation: 'compact', maximumFractionDigits: 1})"


def year_options() -> list[int]:
    with get_session() as db:
        years = set(crud.get_available_years(db))
        years.add(date.today().year)
    return sorted(years, reverse=True)


def month_select(
    value: int,
    on_change: Optional[Callable] = None,
    label: str = "Mês",
) -> ui.select:
    return ui.select(
        options={m: month_name(m) for m in range(1, 13)},
        value=value,
        label=label,
        on_change=on_change,
        with_input=True,
    ).classes("min-w-[9rem]")


def year_select(
    value: int,
    on_change: Optional[Callable] = None,
    label: str = "Ano",
) -> ui.select:
    options = year_options()
    if value not in options:
        options = sorted({*options, value}, reverse=True)
    return ui.select(
        options=options,
        value=value,
        label=label,
        on_change=on_change,
        with_input=True,
    ).classes("min-w-[6rem]")


def money_input(
    label: str = "Valor (R$)",
    value: str = "",
) -> ui.input:
    # Text input + decimal keypad: iOS's pt-BR keypad types "," which <input type=number> rejects.
    return ui.input(label, value=value).props("inputmode=decimal autocomplete=off")


def date_input(label: str, value: date) -> ui.input:
    """Native <input type="date">: typed per field on desktop, the system wheel/picker on iOS and Android.

    The value is ISO (YYYY-MM-DD); read it with parse_date_input().
    """
    return ui.input(label, value=value.isoformat()).props("type=date stack-label outlined")


def parse_date_input(text: Optional[str]) -> Optional[date]:
    try:
        return date.fromisoformat(text or "")
    except ValueError:
        return None


def kpi_card(
    label: str,
    value: str,
    hint: Optional[str] = None,
    hint_classes: str = "casa-muted",
) -> None:
    with ui.card().classes(card_classes("w-full gap-1 p-3")):
        ui.label(label).classes(
            "text-xs casa-muted uppercase tracking-wide"
        )
        ui.label(value).classes("text-xl font-bold")
        if hint:
            ui.label(hint).classes(f"text-xs {hint_classes}")


def settlement_text(balance: float) -> str:
    if balance > 0:
        return f"Fefe deve {format_brl(balance)} para Fafa"
    if balance < 0:
        return f"Fafa deve {format_brl(-balance)} para Fefe"
    return "Contas iguais"


def change_hint(detail: dict) -> tuple[str, str]:
    """Text and CSS classes comparing a month's total with the previous month."""
    previous = month_name(
        12 if detail["month"] == 1 else detail["month"] - 1
    )
    pct = detail["total_change_pct"]

    if pct is None:
        return f"Sem gastos em {previous}", "casa-muted"

    sign = "+" if detail["total_change"] > 0 else ""

    # Spending more than the previous month is shown as negative.
    tone = (
        "casa-negative"
        if detail["total_change"] > 0
        else "casa-positive"
    )

    return (
        f"{sign}{format_pct(pct)} vs {previous} "
        f"({sign}{format_brl(detail['total_change'])})",
        tone,
    )


def settlement_banner(bal: dict) -> None:
    with ui.card().classes(card_classes("w-full p-3")):
        with ui.row().classes("items-center gap-2 no-wrap"):
            ui.icon(
                "swap_horiz" if bal["balance"] else "check_circle"
            ).classes("text-2xl casa-muted")
            ui.label(
                settlement_text(bal["balance"])
            ).classes("text-lg font-medium")


def person_split(bal: dict) -> None:
    """Should pay / paid / saldo for each person, side by side."""
    with ui.element("div").classes("grid grid-cols-1 sm:grid-cols-2 gap-3 w-full"):
        for name, ratio, should, paid, saldo in (
            (
                "Fafa",
                bal["fafa_ratio"],
                bal["fafa_should_pay"],
                bal["fafa_paid"],
                bal["balance"],
            ),
            (
                "Fefe",
                bal["fefe_ratio"],
                bal["fefe_should_pay"],
                bal["fefe_paid"],
                -bal["balance"],
            ),
        ):
            with ui.card().classes(card_classes("w-full gap-1 p-3")):
                with ui.row().classes(
                    "w-full items-center justify-between"
                ):
                    ui.label(name).classes("font-bold")
                    ui.label(
                        f"{ratio * 100:.1f}%".replace(".", ",")
                    ).classes("text-xs casa-muted")
                _line("Deve pagar", format_brl(should))
                _line("Pagou", format_brl(paid))
                tone = (
                    "casa-positive"
                    if saldo >= 0
                    else "casa-negative"
                )
                _line(
                    "Saldo",
                    format_brl(saldo),
                    f"font-bold {tone}",
                )


def _line(
    label: str,
    value: str,
    value_classes: str = "",
) -> None:
    with ui.row().classes("w-full justify-between text-sm"):
        ui.label(label).classes("casa-muted")
        ui.label(value).classes(value_classes)


def base_chart(**overrides) -> dict:
    """Shared ECharts options: transparent, theme-neutral text, BRL tooltips that stay on screen."""
    options = {
        "backgroundColor": "transparent",
        "textStyle": {"color": CHART_TEXT},
        "grid": {
            "left": 8,
            "right": 12,
            "top": 16,
            "bottom": 40,
            "containLabel": True,
        },
        "tooltip": {
            "trigger": "axis",
            "confine": True,
            ":valueFormatter": BRL_JS,
        },
        "legend": {
            "bottom": 0,
            "textStyle": {"color": CHART_TEXT},
        },
    }
    options.update(overrides)
    return options


def value_axis(**extra) -> dict:
    return {
        "type": "value",
        "axisLabel": {
            "color": CHART_TEXT,
            ":formatter": COMPACT_JS,
        },
        "splitLine": {
            "lineStyle": {"color": CHART_GRID},
        },
        **extra,
    }


def category_axis(labels: list[str], **extra) -> dict:
    return {
        "type": "category",
        "data": labels,
        "axisLabel": {"color": CHART_TEXT},
        "axisLine": {
            "lineStyle": {"color": CHART_GRID},
        },
        "axisTick": {"show": False},
        **extra,
    }

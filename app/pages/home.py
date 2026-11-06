from datetime import date
from nicegui import ui

from app.balance import calculate_month_detail
from app.components import (
    change_hint,
    kpi_card,
    month_select,
    person_split,
    settlement_banner,
    year_select,
)
from app.database import get_session
from app.formatting import format_brl
from app.theme import page_container


def build_home() -> None:
    today = date.today()

    with page_container():
        ui.label("Casa Fafa & Fefe").classes(
            "casa-page-title text-2xl font-bold"
        )

        with ui.row().classes("casa-filter gap-3 items-center w-full"):
            month = month_select(
                today.month,
                on_change=lambda: refresh(),
            ).mark("home-month")

            year = year_select(
                today.year,
                on_change=lambda: refresh(),
            ).mark("home-year")

        with ui.element("div").classes(
            "grid grid-cols-2 gap-3 w-full"
        ):
            ui.button(
                "Novo gasto",
                icon="add_circle",
                on_click=lambda: ui.navigate.to("/variable"),
            ).props("unelevated no-caps size=lg").classes("w-full")

            ui.button(
                "Gastos fixos",
                icon="event_repeat",
                on_click=lambda: ui.navigate.to("/regular"),
            ).props("outline no-caps size=lg").classes("w-full")

        content = ui.column().classes("w-full gap-4")

        ui.button(
            "Ver todos os meses",
            icon="calendar_month",
            on_click=lambda: ui.navigate.to("/balance"),
        ).props("flat no-caps").classes("self-center")

    def refresh() -> None:
        with get_session() as db:
            detail = calculate_month_detail(
                db,
                month.value,
                int(year.value),
            )

        content.clear()

        with content:
            hint, hint_classes = change_hint(detail)

            with ui.element("div").classes(
                "grid grid-cols-1 sm:grid-cols-3 gap-3 w-full"
            ):
                kpi_card(
                    "Total do mês",
                    format_brl(detail["total_expenses"]),
                    hint,
                    hint_classes,
                )
                kpi_card(
                    "Variável",
                    format_brl(detail["variable_total"]),
                )
                kpi_card(
                    "Fixo",
                    format_brl(detail["regular_total"]),
                )

            settlement_banner(detail)
            person_split(detail)

    refresh()
import calendar
from datetime import date

from nicegui import ui

from app import crud
from app.components import money_input, month_select, year_select
from app.database import get_session
from app.dates import is_future_month
from app.formatting import format_brl, format_number_br, parse_money
from app.models import FAFA
from app.theme import card_classes, page_container


def build_regular_expenses() -> None:
    today = date.today()

    with page_container():
        with ui.column().classes("gap-0"):
            ui.label("Gastos Fixos").classes("casa-page-title text-2xl font-bold")
            ui.label("Sempre pagos por Fafa.").classes("text-sm casa-muted")

        with ui.row().classes("casa-filter gap-3 items-center w-full"):
            month = month_select(today.month, on_change=lambda: build_form())
            year = year_select(today.year, on_change=lambda: build_form())

        form_container = ui.column().classes("w-full")

    def build_form() -> None:
        selected_month, selected_year = month.value, int(year.value)
        if is_future_month(selected_year, selected_month):
            form_container.clear()
            with form_container:
                ui.label("Não é possível lançar gastos fixos em meses futuros.").classes("casa-muted py-3")
            return
        last_day = calendar.monthrange(selected_year, selected_month)[1]
        with get_session() as db:
            categories = [c.name for c in crud.get_regular_categories(db)]
            existing = {
                e.category_name: {"id": e.id, "day": e.day, "value": e.value}
                for e in crud.get_regular_expenses(db, month=selected_month, year=selected_year)
            }

        rows = {}
        form_container.clear()
        with form_container, ui.card().classes(card_classes("w-full p-3 gap-0")):
            for name in categories:
                current = existing.get(name, {})
                with ui.row().classes("w-full items-center gap-2 py-2 border-b flex-wrap"):
                    ui.label(name).classes("font-medium w-full sm:w-auto sm:flex-1")
                    day_input = ui.select(
                        {d: f"{d:02d}" for d in range(1, last_day + 1)},
                        value=min(current.get("day", 15), last_day),
                        label="Dia",
                        with_input=True,
                    ).props("dense").classes("w-20")
                    value_input = money_input(
                        value=format_number_br(current["value"]) if current else "",
                    ).props("dense").classes("flex-1 sm:flex-none sm:w-32").mark(f"value-{name}")
                    rows[name] = (day_input, value_input)

            def save_all() -> None:
                parsed = {}
                invalid = []
                for name, (_, value_input) in rows.items():
                    raw = (value_input.value or "").strip()
                    value = parse_money(raw) if raw else 0.0
                    if value is None or value < 0:
                        invalid.append(name)
                        continue
                    parsed[name] = value
                if invalid:
                    ui.notify(f"Valor inválido: {', '.join(invalid)}", type="warning")
                    return

                with get_session() as db:
                    for name, (day_input, _) in rows.items():
                        if parsed[name] == 0:
                            if name in existing:
                                crud.delete_regular_expense(db, existing[name]["id"])
                            continue
                        crud.upsert_regular_expense(db, {
                            "day": int(day_input.value),
                            "month": selected_month,
                            "year": selected_year,
                            "value": parsed[name],
                            "paid_by": FAFA,
                            "category_name": name,
                        })

                ui.notify("Salvo!", type="positive")
                build_form()

            total = sum(e["value"] for e in existing.values())
            with ui.row().classes("w-full items-center justify-between mt-3 gap-2"):
                ui.label(f"Total: {format_brl(total)}").classes("text-lg font-bold")
            with ui.row().classes("gap-2"):
                ui.button("Desfazer", icon="undo", on_click=build_form).props("flat no-caps")
                ui.button("Salvar tudo", icon="save", on_click=save_all).props("unelevated no-caps").mark("save")

    build_form()

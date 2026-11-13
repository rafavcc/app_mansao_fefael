from datetime import date
from typing import Optional

from nicegui import app, ui

from app import crud
from app.components import date_input, parse_date_input, money_input, month_select, year_select
from app.database import get_session
from app.dates import is_future_date
from app.formatting import (
    PAYER_LABELS, format_brl, format_number_br, parse_money,
)
from app.native_select import NativeSelect
from app.models import FAFA, PAYERS, VariableExpense
from app.theme import card_classes, page_container

QUICK_VALUES = [10, 20, 50, 70, 100, 200, 250, 500]
LAST_CATEGORY_KEY = "last_variable_category"


class ExpenseForm:
    """Fields shared by the 'new expense' card and the edit dialog."""

    def __init__(self, categories: list[str], values: Optional[dict] = None, place_shortcuts: list[str] = ()):
        values = values or {}
        self.place = ui.input("Local", value=values.get("place", "")).classes("w-full").mark("place")
        if place_shortcuts:
            with ui.row().classes("gap-1 flex-wrap"):
                for p in place_shortcuts:
                    ui.button(p, on_click=lambda p=p: self.place.set_value(p)).props("flat dense no-caps")

        self.date = date_input("Data", values.get("date", date.today())).props(f'max={date.today().isoformat()}') \
            .classes("w-full").mark("date")

        value = values.get("value")
        self.value = money_input(value=format_number_br(value) if value else "").classes("w-full").mark("value")
        with ui.row().classes("gap-1 flex-wrap"):
            for quick in QUICK_VALUES:
                ui.button(f"R$ {quick}", on_click=lambda q=quick: self.value.set_value(format_number_br(q))) \
                    .props("flat dense no-caps")

        self.category = NativeSelect(categories, label="Grupo", value=values.get("category_name")) \
            .classes("w-full").mark("category")

        with ui.row().classes("items-center gap-3"):
            ui.label("Pago por").classes("text-sm casa-muted")
            self.paid_by = ui.toggle(PAYER_LABELS, value=values.get("paid_by")) \
                .props("no-caps unelevated").mark("paid_by")

        self.notes = ui.input("Notas", value=values.get("notes") or "").classes("w-full").mark("notes")

    def read(self) -> Optional[dict]:
        """Validated expense data, or None after notifying the user of the first problem."""
        place = (self.place.value or "").strip()
        when = parse_date_input(self.date.value)
        value = parse_money(self.value.value)
        problem = None
        if not place:
            problem = "Preencha o local."
        elif when is None:
            problem = "Data inválida."
        elif is_future_date(when.year, when.month, when.day):
            problem = "A data não pode estar no futuro."
        elif value is None or value <= 0:
            problem = "Valor deve ser maior que zero."
        elif not self.category.value:
            problem = "Selecione um grupo."
        elif self.paid_by.value not in PAYERS:
            problem = "Selecione quem pagou."
        if problem:
            ui.notify(problem, type="warning")
            return None
        return {
            "place": place,
            "day": when.day,
            "month": when.month,
            "year": when.year,
            "value": value,
            "paid_by": self.paid_by.value,
            "category_name": self.category.value,
            "notes": (self.notes.value or "").strip() or None,
        }


def build_variable_expenses() -> None:
    today = date.today()
    with get_session() as db:
        categories = [c.name for c in crud.get_variable_categories(db)]
        top_places = crud.get_top_places(db)

    last_category = app.storage.user.get(LAST_CATEGORY_KEY)

    with page_container():
        ui.label("Gastos Variáveis").classes("casa-page-title text-2xl font-bold")

        with ui.card().classes(card_classes("w-full p-3 gap-2")):
            ui.label("Novo gasto").classes("text-lg font-bold")
            form = ExpenseForm(
                categories,
                {"category_name": last_category if last_category in categories else None},
                place_shortcuts=top_places,
            )

            def add_expense() -> None:
                data = form.read()
                if data is None:
                    return
                with get_session() as db:
                    crud.create_variable_expense(db, data)
                app.storage.user[LAST_CATEGORY_KEY] = data["category_name"]
                ui.notify("Adicionado!", type="positive")
                form.place.set_value("")
                form.value.set_value("")
                form.notes.set_value("")
                form.paid_by.set_value(None)
                if data["year"] not in filter_year.options:
                    filter_year.set_options(sorted({*filter_year.options, data["year"]}, reverse=True))
                filter_month.set_value(data["month"])
                filter_year.set_value(data["year"])
                refresh_list()

            ui.button("Adicionar", icon="add", on_click=add_expense) \
                .props("unelevated no-caps size=lg").classes("w-full mt-1")

        with ui.row().classes("casa-filter gap-3 items-center w-full"):
            filter_month = month_select(today.month, on_change=lambda: refresh_list())
            filter_year = year_select(today.year, on_change=lambda: refresh_list())

        summary = ui.row().classes("w-full justify-between items-center px-1")
        expense_list = ui.column().classes("w-full gap-2")
        dialog_host = ui.element("div")

        def refresh_list() -> None:
            with get_session() as db:
                expenses = crud.get_variable_expenses(db, month=filter_month.value, year=int(filter_year.value))

            summary.clear()
            expense_list.clear()
            with summary:
                total = sum(e.value for e in expenses)
                fafa = sum(e.value for e in expenses if e.paid_by == FAFA)
                ui.label(f"{len(expenses)} gasto(s)").classes("text-sm casa-muted")
                ui.label(f"Total {format_brl(total)}").classes("font-bold")
                if expenses:
                    ui.label(f"Fafa {format_brl(fafa)} · Fefe {format_brl(total - fafa)}") \
                        .classes("text-xs casa-muted w-full text-right")

            with expense_list:
                if not expenses:
                    ui.label("Nenhum gasto neste mês.").classes("casa-muted")
                for e in expenses:
                    with ui.card().classes(card_classes("w-full p-3 casa-clickable")).mark(f"expense-{e.id}") \
                            .on("click", lambda expense_id=e.id: open_edit(expense_id)):
                        with ui.row().classes("w-full items-center no-wrap gap-3"):
                            ui.label(f"{e.day:02d}").classes("text-lg font-bold casa-muted w-8 text-center")
                            with ui.column().classes("flex-1 gap-0 min-w-0"):
                                ui.label(e.place).classes("font-medium truncate w-full")
                                ui.label(f"{e.category_name} · {PAYER_LABELS.get(e.paid_by, e.paid_by)}") \
                                    .classes("text-xs casa-muted")
                                if e.notes:
                                    ui.label(e.notes).classes("text-xs casa-muted truncate w-full")
                            ui.label(format_brl(e.value)).classes("font-bold whitespace-nowrap")

        def open_edit(expense_id: int) -> None:
            with get_session() as db:
                expense = db.get(VariableExpense, expense_id)
                if expense is None:
                    ui.notify("Gasto não encontrado.", type="negative")
                    refresh_list()
                    return
                values = {
                    "place": expense.place,
                    "date": date(expense.year, expense.month, expense.day),
                    "value": expense.value,
                    "category_name": expense.category_name,
                    "paid_by": expense.paid_by,
                    "notes": expense.notes,
                }

            dialog_host.clear()
            with dialog_host, ui.dialog() as dialog, ui.card().classes(card_classes("w-full max-w-lg p-4 gap-2")):
                ui.label("Editar gasto").classes("text-lg font-bold")
                edit_form = ExpenseForm(categories, values)
                confirm = {"pending": False}

                def save() -> None:
                    data = edit_form.read()
                    if data is None:
                        return
                    with get_session() as db:
                        crud.update_variable_expense(db, expense_id, data)
                    dialog.close()
                    ui.notify("Gasto atualizado!", type="positive")
                    refresh_list()

                def delete() -> None:
                    if not confirm["pending"]:
                        confirm["pending"] = True
                        delete_button.set_text("Confirmar exclusão")
                        return
                    with get_session() as db:
                        crud.delete_variable_expense(db, expense_id)
                    dialog.close()
                    ui.notify("Gasto excluído.", type="positive")
                    refresh_list()

                with ui.row().classes("w-full justify-between items-center mt-2"):
                    delete_button = ui.button("Excluir", icon="delete", on_click=delete) \
                        .props("flat no-caps color=negative").mark("delete")
                    with ui.row().classes("gap-2"):
                        ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                        ui.button("Salvar", icon="save", on_click=save).props("unelevated no-caps").mark("save")
            dialog.open()

        refresh_list()
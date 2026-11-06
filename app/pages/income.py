from datetime import date

from nicegui import ui

from app import crud
from app.components import kpi_card, money_input
from app.database import get_session
from app.formatting import format_brl, format_number_br, format_pct, parse_money
from app.planning import calculate_plan, income_breakdown
from app.theme import card_classes, page_container


def build_income() -> None:
    with page_container():
        with ui.column().classes("gap-0"):
            ui.label("Planejamento").classes("casa-page-title text-2xl font-bold")
            ui.label("Plano mensal recorrente da casa, sem mês específico.").classes("text-sm casa-muted")
        content = ui.column().classes("w-full gap-4")

    def open_dialog(kind: str, item=None) -> None:
        with get_session() as db:
            categories = crud.get_planning_categories(db)

        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md gap-3"):
            ui.label("Editar item" if item else "Novo item").classes("text-lg font-bold")
            description = ui.input("Descrição", value=item.description if item else "").classes("w-full")
            value = money_input(value=format_number_br(item.value) if item else "").classes("w-full")
            is_gross = dependents = category = None
            if kind == "income":
                is_gross = ui.switch(
                    "Salário bruto (descontar INSS e IRRF)",
                    value=item.is_gross if item else True,
                ).mark("is-gross")
                dependents = ui.number(
                    "Dependentes", value=item.dependents if item else 0, min=0, step=1, precision=0,
                ).classes("w-full").bind_visibility_from(is_gross, "value")
            if kind == "expense":
                category = ui.select(
                    categories,
                    value=item.category_name if item else None,
                    label="Categoria",
                    with_input=True,
                ).classes("w-full")

            def save() -> None:
                text = (description.value or "").strip()
                amount = parse_money(value.value)
                if not text:
                    ui.notify("Informe a descrição.", type="warning")
                    return
                if amount is None or amount <= 0:
                    ui.notify("Informe um valor maior que zero.", type="warning")
                    return
                data = {"description": text, "value": amount}
                if kind == "income":
                    data.update(is_gross=bool(is_gross.value), dependents=int(dependents.value or 0))
                if kind == "expense":
                    if not category.value:
                        ui.notify("Escolha uma categoria.", type="warning")
                        return
                    data.update(category_name=category.value)
                with get_session() as db:
                    crud.save_plan_item(db, kind, data, item.id if item else None)
                dialog.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Salvar", icon="save", on_click=save).props("unelevated no-caps").mark("save")
        dialog.open()

    def confirm_delete(kind: str, item) -> None:
        with ui.dialog() as dialog, ui.card().classes("gap-3"):
            ui.label(f"Excluir '{item.description}'?")

            def delete() -> None:
                with get_session() as db:
                    crud.delete_plan_item(db, kind, item.id)
                dialog.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Excluir", icon="delete", on_click=delete).props("unelevated no-caps color=negative")
        dialog.open()

    def section(title: str, kind: str, items: list, totals: list[tuple[str, list[str]]], headers: list[str]) -> None:
        """Every row is a grid with the same column template, so totals sit exactly above the item values."""
        template = f"minmax(0,1fr) repeat({len(headers)}, minmax(5.5rem, 7.5rem)) 4.5rem"
        num = "text-right whitespace-nowrap text-sm sm:text-base"

        def grid_row(classes: str = ""):
            return ui.element("div").classes(f"w-full items-center {classes}") \
                .style(f"display:grid;grid-template-columns:{template};column-gap:0.5rem")

        with ui.card().classes(card_classes("w-full p-3 sm:p-4 gap-0")):
            ui.label(title).classes("text-lg font-bold mb-2")
            with grid_row("text-xs casa-muted uppercase tracking-wide pb-1"):
                ui.label("")
                for header in headers:
                    ui.label(header).classes("text-right")
                ui.label("")
            for index, (label, cells) in enumerate(totals):
                last = index == len(totals) - 1
                with grid_row("py-2" + (" border-b font-bold" if last else " casa-muted")):
                    ui.label(label)
                    for text in cells:
                        ui.label(text).classes(num)
                    ui.label("")
            if not items:
                ui.label("Nenhum item adicionado.").classes("casa-muted py-3")
            for item in items:
                with grid_row("py-2 border-b"):
                    with ui.column().classes("gap-0 min-w-0"):
                        ui.label(item.description).classes("font-medium")
                        if kind == "expense":
                            ui.label(f"{item.category_name}").classes("text-xs casa-muted")
                        if kind == "income" and item.is_gross and item.dependents:
                            ui.label(f"{item.dependents} dependente(s)").classes("text-xs casa-muted")
                    if kind == "income":
                        pay = income_breakdown(item)
                        ui.label(format_brl(pay["gross"])).classes(f"{num} casa-muted")
                        ui.label(format_brl(pay["taxes"]) if pay["taxes"] else "—").classes(f"{num} casa-muted")
                        ui.label(format_brl(pay["net"])).classes(f"{num} font-bold")
                    else:
                        ui.label(format_brl(item.value)).classes(f"{num} font-bold")
                    with ui.row().classes("gap-0 flex-nowrap justify-end"):
                        ui.button(icon="edit", on_click=lambda i=item: open_dialog(kind, i)).props("flat round dense size=sm")
                        ui.button(icon="delete", on_click=lambda i=item: confirm_delete(kind, i)).props("flat round dense size=sm")
            ui.button("Adicionar item", icon="add", on_click=lambda: open_dialog(kind)) \
                .props("flat no-caps").classes("self-center mt-1").mark(f"add-{kind}")

    def refresh() -> None:
        today = date.today()
        with get_session() as db:
            income = crud.get_plan_items(db, "income")
            expenses = crud.get_plan_items(db, "expense")
            savings = crud.get_plan_items(db, "savings")
            plan = calculate_plan(db, today.month, today.year)

        free = plan["free_balance"]
        free_pct = plan["free_balance_pct"]
        diff = plan["actual_vs_planned"]
        if diff > 0:
            diff_text, diff_classes = f"{format_brl(diff)} acima do planejado", "text-red-600"
        elif diff < 0:
            diff_text, diff_classes = f"{format_brl(-diff)} abaixo do planejado", "text-green-600"
        else:
            diff_text, diff_classes = "Exatamente como planejado", "casa-muted"

        content.clear()
        with content:
            with ui.element("div").classes("grid grid-cols-1 sm:grid-cols-2 gap-3 w-full"):
                kpi_card(
                    "Saldo livre",
                    format_brl(free),
                    f"{format_pct(free_pct)} da renda" if free_pct is not None else None,
                    "text-red-600" if free < 0 else "casa-muted",
                )
                kpi_card(
                    "Realizado no mês atual",
                    format_brl(plan["actual_total"]),
                    f"{diff_text} ({format_brl(plan['expenses_total'])})",
                    diff_classes,
                )
            section(
                "Renda mensal", "income", income,
                [("Renda total", [
                    format_brl(plan["gross_income_total"]),
                    format_brl(plan["taxes_total"]),
                    format_brl(plan["income_total"]),
                ])],
                ["Bruto", "Impostos", "Líquido"],
            )
            section(
                "Despesas mensais", "expense", expenses,
                [
                    ("Despesas totais", [format_brl(plan["expenses_total"])]),
                ],
                ["Valor"],
            )
            section(
                "Poupanças e investimentos mensais", "savings", savings,
                [("Total poupado", [format_brl(plan["savings_total"])])],
                ["Valor"],
            )
    refresh()

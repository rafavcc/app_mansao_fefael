from datetime import date

from nicegui import ui

from app import crud
from app.budgets import (
    BudgetError, PeriodConflict, add_period, budget_counts, budget_for_month, covered_months,
    create_budget, delete_budget, delete_period, format_period, list_budgets, rename_budget,
    update_period,
)
from app.components import kpi_card, money_input, month_select
from app.database import get_session
from app.formatting import format_brl, format_number_br, format_pct, month_name, parse_money
from app.models import Budget
from app.native_select import NativeSelect
from app.planning import calculate_plan, income_breakdown
from app.theme import card_classes, page_container


def build_income() -> None:
    with page_container():
        with ui.column().classes("gap-0"):
            ui.label("Planejamento").classes("casa-page-title text-2xl font-bold")
            ui.label("Orçamentos mensais por período.").classes("text-sm casa-muted")
        content = ui.column().classes("w-full gap-4")

    # budget_id: selected budget; month: compared month as year * 100 + month
    state = {"budget_id": None, "month": None}

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
                category = NativeSelect(
                    categories,
                    value=item.category_name if item else None,
                    label="Categoria",
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
                if item is None:
                    data["budget_id"] = state["budget_id"]
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
        # Layout lives in theme.py (.plan-row): one table row on wide screens; on phones the
        # description sits on its own line and the values get the full width below it.
        num = "text-right whitespace-nowrap text-sm sm:text-base"
        wide = " plan-wide" if len(headers) > 1 else ""

        def grid_row(classes: str = ""):
            return ui.element("div").classes(f"plan-row w-full items-center {classes}{wide}") \
                .style(f"--plan-cols:{len(headers)}")

        with ui.card().classes(card_classes("w-full p-3 sm:p-4 gap-0")):
            ui.label(title).classes("text-lg font-bold mb-2")
            with grid_row("text-xs casa-muted uppercase tracking-wide pb-1"):
                ui.label("").classes("plan-skip")
                for header in headers:
                    ui.label(header).classes("text-right")
                ui.label("").classes("plan-skip")
            for index, (label, cells) in enumerate(totals):
                last = index == len(totals) - 1
                with grid_row("py-2" + (" border-b font-bold" if last else " casa-muted")):
                    ui.label(label).classes("plan-label")
                    for text in cells:
                        ui.label(text).classes(num)
                    ui.label("").classes("plan-skip")
            if not items:
                ui.label("Nenhum item adicionado.").classes("casa-muted py-3")
            for item in items:
                with grid_row("py-2 border-b"):
                    with ui.column().classes("plan-label gap-0 min-w-0"):
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
                    with ui.row().classes("plan-actions gap-0 flex-nowrap justify-end"):
                        ui.button(icon="edit", on_click=lambda i=item: open_dialog(kind, i)).props("flat round dense size=sm")
                        ui.button(icon="delete", on_click=lambda i=item: confirm_delete(kind, i)).props("flat round dense size=sm")
            ui.button("Adicionar item", icon="add", on_click=lambda: open_dialog(kind)) \
                .props("flat no-caps").classes("self-center mt-1").mark(f"add-{kind}")

    def warn(error: Exception) -> None:
        ui.notify(str(error), type="warning")

    def pick_budget(budgets: list, today: date):
        """Budget covering the current month, else the first by name."""
        with get_session() as db:
            current = budget_for_month(db, today.month, today.year)
        if current is not None:
            return current.id
        return budgets[0].id if budgets else None

    def select_budget(budget_id) -> None:
        state["budget_id"] = budget_id
        state["month"] = None
        refresh()

    def name_dialog(title: str, value: str, on_save, extra=None) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md gap-3"):
            ui.label(title).classes("text-lg font-bold")
            name = ui.input("Nome", value=value).classes("w-full").mark("budget-name")
            extra_control = extra() if extra else None

            def save() -> None:
                try:
                    on_save((name.value or "").strip(), extra_control)
                except BudgetError as error:
                    warn(error)
                    return
                dialog.close()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Salvar", icon="save", on_click=save).props("unelevated no-caps").mark("save-budget")
        dialog.open()

    def new_budget_dialog() -> None:
        def extra():
            if state["budget_id"] is None:
                return None
            return ui.radio(
                {"copy": "Copiar o orçamento selecionado", "empty": "Começar vazio"}, value="copy",
            )

        def save(name: str, mode) -> None:
            copy_from = state["budget_id"] if mode is not None and mode.value == "copy" else None
            with get_session() as db:
                budget = create_budget(db, name, copy_from=copy_from)
                new_id = budget.id
            select_budget(new_id)

        name_dialog("Novo orçamento", "", save, extra)

    def rename_dialog(budget) -> None:
        def save(name: str, _extra) -> None:
            with get_session() as db:
                rename_budget(db, budget.id, name)
            refresh()

        name_dialog("Renomear orçamento", budget.name, save)

    def delete_budget_dialog(budget) -> None:
        with get_session() as db:
            counts = budget_counts(db, budget.id)
        items = counts["income"] + counts["expenses"]
        with ui.dialog() as dialog, ui.card().classes("gap-3"):
            ui.label(
                f"Excluir '{budget.name}'? {items} itens e {counts['periods']} períodos serão removidos."
            )

            def delete() -> None:
                with get_session() as db:
                    delete_budget(db, budget.id)
                dialog.close()
                select_budget(None)

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Excluir", icon="delete", on_click=delete) \
                    .props("unelevated no-caps color=negative").mark("confirm-delete-budget")
        dialog.open()

    def year_choice(value: int, label: str):
        this_year = date.today().year
        years = sorted({*range(2000, this_year + 7), value}, reverse=True)
        return NativeSelect(years, value=value, label=label).classes("min-w-[6rem]")

    def period_dialog(budget, period=None) -> None:
        today = date.today()
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md gap-3"):
            ui.label("Editar período" if period else "Novo período").classes("text-lg font-bold")
            ui.label("Início").classes("text-sm casa-muted")
            with ui.row().classes("w-full gap-2 flex-nowrap"):
                start_month = month_select(period.start_month if period else today.month)
                start_year = year_choice(period.start_year if period else today.year, "Ano")
            open_ended = ui.switch("Sem data final", value=period.end_year is None if period else True).mark("open-ended")
            with ui.column().classes("w-full gap-1").bind_visibility_from(open_ended, "value", backward=lambda v: not v):
                ui.label("Fim").classes("text-sm casa-muted")
                with ui.row().classes("w-full gap-2 flex-nowrap"):
                    end_month = month_select(period.end_month if period and period.end_year else today.month)
                    end_year = year_choice(period.end_year if period and period.end_year else today.year, "Ano")

            def save(close_conflict: bool = False) -> None:
                start = (int(start_year.value), int(start_month.value))
                end = None if open_ended.value else (int(end_year.value), int(end_month.value))
                try:
                    with get_session() as db:
                        if period:
                            update_period(db, period.id, start, end, close_conflict)
                        else:
                            add_period(db, budget.id, start, end, close_conflict)
                except PeriodConflict as conflict:
                    if conflict.closable is None:
                        warn(conflict)
                        return
                    confirm_close(budget, conflict, start, lambda: save(True))
                    return
                except BudgetError as error:
                    warn(error)
                    return
                dialog.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Salvar", icon="save", on_click=save).props("unelevated no-caps").mark("save-period")
        dialog.open()

    def confirm_close(budget, conflict, start, retry) -> None:
        other = conflict.closable
        year, month = start
        end_year, end_month = (year - 1, 12) if month == 1 else (year, month - 1)
        with ui.dialog() as dialog, ui.card().classes("gap-3"):
            ui.label(f"Encerrar '{other.budget.name}' em {month_name(end_month, short=True)}/{end_year}?")

            def confirm() -> None:
                dialog.close()
                retry()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Encerrar", on_click=confirm).props("unelevated no-caps").mark("confirm-close")
        dialog.open()

    def confirm_delete_period(period) -> None:
        with ui.dialog() as dialog, ui.card().classes("gap-3"):
            ui.label(f"Excluir o período {format_period(period)}?")

            def delete() -> None:
                with get_session() as db:
                    delete_period(db, period.id)
                dialog.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Excluir", icon="delete", on_click=delete).props("unelevated no-caps color=negative")
        dialog.open()

    def empty_state() -> None:
        with ui.card().classes(card_classes("w-full p-4 gap-2 items-center")):
            ui.label("Nenhum orçamento criado.").classes("casa-muted")
            ui.button("Criar orçamento", icon="add", on_click=new_budget_dialog) \
                .props("unelevated no-caps").mark("create-first-budget")

    def refresh() -> None:
        today = date.today()
        with get_session() as db:
            budgets = list_budgets(db)
            ids = {b.id for b in budgets}
            if state["budget_id"] not in ids:
                state["budget_id"] = pick_budget(budgets, today)
            budget = db.get(Budget, state["budget_id"]) if budgets else None
            if budget is None:
                options, periods, months, plan, income, expenses = {}, [], [], None, [], []
                compared = None
            else:
                options = {b.id: b.name for b in budgets}
                periods = sorted(budget.periods, key=lambda p: (p.start_year, p.start_month))
                months = covered_months(budget, today)
                key = state["month"]
                if key is None or key not in {y * 100 + m for y, m in months}:
                    key = months[0][0] * 100 + months[0][1] if months else None
                state["month"] = key
                income = crud.get_plan_items(db, "income", budget.id)
                expenses = sorted(crud.get_plan_items(db, "expense", budget.id), key=lambda e: e.value, reverse=True)
                month_plan = None
                if key is not None:
                    year, month = divmod(key, 100)
                    owner = budget_for_month(db, month, year)
                    if owner is not None and owner.id == budget.id:
                        month_plan = calculate_plan(db, budget.id, month, year)
                plan = month_plan or calculate_plan(db, budget.id, today.month, today.year)
                compared = "ok" if month_plan else ("none" if key is None else "other")

        content.clear()
        with content:
            if budget is None:
                empty_state()
                return

            with ui.row().classes("w-full items-end gap-2"):
                NativeSelect(
                    options, value=budget.id, label="Orçamento",
                    on_change=lambda e: select_budget(e.value) if e.value != state["budget_id"] else None,
                ).classes("min-w-[12rem] grow").mark("budget-select")
                ui.button("Novo", icon="add", on_click=new_budget_dialog).props("flat no-caps dense").mark("new-budget")
                ui.button("Renomear", icon="edit", on_click=lambda: rename_dialog(budget)) \
                    .props("flat no-caps dense").mark("rename-budget")
                ui.button("Excluir", icon="delete", on_click=lambda: delete_budget_dialog(budget)) \
                    .props("flat no-caps dense color=negative").mark("delete-budget")

            with ui.card().classes(card_classes("w-full p-3 sm:p-4 gap-1")):
                ui.label("Períodos").classes("text-lg font-bold")
                if not periods:
                    ui.label("Nenhum período definido.").classes("casa-muted")
                for period in periods:
                    with ui.row().classes("w-full items-center justify-between flex-nowrap border-b py-1"):
                        ui.label(format_period(period)).classes("font-medium")
                        with ui.row().classes("gap-0 flex-nowrap"):
                            ui.button(icon="edit", on_click=lambda p=period: period_dialog(budget, p)) \
                                .props("flat round dense size=sm")
                            ui.button(icon="delete", on_click=lambda p=period: confirm_delete_period(p)) \
                                .props("flat round dense size=sm")
                ui.button("Adicionar período", icon="add", on_click=lambda: period_dialog(budget)) \
                    .props("flat no-caps").classes("self-center mt-1").mark("add-period")

            if months:
                NativeSelect(
                    {y * 100 + m: f"{month_name(m, short=True)}/{y}" for y, m in months},
                    value=state["month"], label="Mês comparado",
                    on_change=lambda e: (state.update(month=e.value), refresh()),
                ).classes("min-w-[9rem]").mark("compared-month")

            free = plan["free_balance"]
            free_pct = plan["free_balance_pct"]
            diff = plan["actual_vs_planned"]
            if diff > 0:
                diff_text, diff_classes = f"{format_brl(diff)} acima do planejado", "text-red-600"
            elif diff < 0:
                diff_text, diff_classes = f"{format_brl(-diff)} abaixo do planejado", "text-green-600"
            else:
                diff_text, diff_classes = "Exatamente como planejado", "casa-muted"

            with ui.element("div").classes("grid grid-cols-1 sm:grid-cols-2 gap-3 w-full"):
                kpi_card(
                    "Saldo livre",
                    format_brl(free),
                    f"{format_pct(free_pct)} da renda" if free_pct is not None else None,
                    "text-red-600" if free < 0 else "casa-muted",
                )
                if compared == "ok":
                    year, month = divmod(state["month"], 100)
                    kpi_card(
                        f"Realizado em {month_name(month, short=True)}/{year}",
                        format_brl(plan["actual_total"]),
                        f"{diff_text} ({format_brl(plan['expenses_total'])})",
                        diff_classes,
                    )
                else:
                    kpi_card(
                        "Realizado",
                        ("Nenhum mês até hoje" if periods else "Sem períodos") if compared == "none" else "Sem orçamento",
                        None, "casa-muted",
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
                [("Despesas totais", [format_brl(plan["expenses_total"])])],
                ["Valor"],
            )

    refresh()

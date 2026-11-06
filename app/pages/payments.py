from datetime import date

from nicegui import ui

from app import crud
from app.components import date_input, kpi_card, money_input
from app.database import get_session
from app.formatting import (
    format_brl, format_date_br, format_number_br, month_name, parse_date_br, parse_money,
)
from app.payments import FIRST_BILLED_MONTH, calculate_payments
from app.theme import card_classes, page_container

METHODS = ["Pix", "Transferência", "Dinheiro", "Outro"]

STATUS = {
    "paid": ("Pago", "text-green-600"),
    "partial": ("Parcial", "text-orange-500"),
    "open": ("Em aberto", "text-red-600"),
    "settled": ("Quite", "casa-muted"),
    "credit": ("Fafa deve", "text-sky-500"),
}


def build_payments() -> None:
    with page_container():
        with ui.column().classes("gap-0"):
            ui.label("Pagamentos").classes("casa-page-title text-2xl font-bold")
            ui.label(
                f"Quanto Fefe deve a Fafa. Cada mês vira dívida quando termina "
                f"(contando desde {month_name(FIRST_BILLED_MONTH[1])}/{FIRST_BILLED_MONTH[0]})."
            ).classes("text-sm casa-muted")
        content = ui.column().classes("w-full gap-4")

    def open_dialog(payment=None) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md gap-3"):
            ui.label("Editar pagamento" if payment else "Novo pagamento").classes("text-lg font-bold")
            paid_on = date_input("Data", payment.paid_on if payment else date.today())
            value = money_input(value=format_number_br(payment.value) if payment else "").classes("w-full")
            method = ui.select(
                METHODS, value=payment.method if payment else "Pix", label="Forma", with_input=True,
            ).classes("w-full")
            notes = ui.input("Observação", value=payment.notes if payment and payment.notes else "").classes("w-full")

            def save() -> None:
                day = parse_date_br(paid_on.value)
                amount = parse_money(value.value)
                if day is None:
                    ui.notify("Data inválida.", type="warning")
                    return
                if amount is None or amount <= 0:
                    ui.notify("Informe um valor maior que zero.", type="warning")
                    return
                with get_session() as db:
                    crud.save_payment(db, {
                        "paid_on": day,
                        "value": amount,
                        "method": method.value or None,
                        "notes": (notes.value or "").strip() or None,
                    }, payment.id if payment else None)
                dialog.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Salvar", icon="save", on_click=save).props("unelevated no-caps").mark("save")
        dialog.open()

    def confirm_delete(payment) -> None:
        with ui.dialog() as dialog, ui.card().classes("gap-3"):
            ui.label(f"Excluir pagamento de {format_brl(payment.value)}?")

            def delete() -> None:
                with get_session() as db:
                    crud.delete_payment(db, payment.id)
                dialog.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Excluir", icon="delete", on_click=delete).props("unelevated no-caps color=negative")
        dialog.open()

    def refresh() -> None:
        with get_session() as db:
            summary = calculate_payments(db)
            payments = crud.get_payments(db)

        debt = summary["debt"]
        if debt > 0:
            debt_label, debt_text, debt_hint, hint_classes = (
                "Fefe deve", format_brl(debt),
                f"{summary['open_months']} mês(es) em aberto", "text-red-600",
            )
        elif debt < 0:
            debt_label, debt_text, debt_hint, hint_classes = (
                "Crédito da Fefe", format_brl(-debt), "Pago adiantado; abate os próximos meses", "text-green-600",
            )
        else:
            debt_label, debt_text, debt_hint, hint_classes = "Fefe deve", format_brl(0), "Tudo em dia", "text-green-600"

        content.clear()
        with content:
            with ui.element("div").classes("grid grid-cols-1 sm:grid-cols-3 gap-3 w-full"):
                kpi_card(debt_label, debt_text, debt_hint, hint_classes)
                kpi_card("Total dos meses encerrados", format_brl(summary["billed_total"]))
                kpi_card("Total pago", format_brl(summary["paid_total"]))

            ui.button("Registrar pagamento", icon="add", on_click=lambda: open_dialog()) \
                .props("unelevated no-caps").mark("add-payment")

            with ui.card().classes(card_classes("w-full p-3 sm:p-4 gap-0")):
                ui.label("Meses encerrados").classes("text-lg font-bold mb-2")
                if not summary["months"]:
                    ui.label("Nenhum mês encerrado ainda.").classes("casa-muted py-2")
                for m in reversed(summary["months"]):
                    text, classes = STATUS[m["status"]]
                    with ui.row().classes("w-full items-center justify-between py-2 border-b flex-nowrap"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"{month_name(m['month'])}/{m['year']}").classes("font-medium")
                            ui.label(text).classes(f"text-xs {classes}")
                        with ui.column().classes("gap-0 items-end"):
                            ui.label(format_brl(abs(m["owed"]))).classes("font-bold whitespace-nowrap")
                            if m["status"] == "partial":
                                ui.label(f"Falta {format_brl(m['remaining'])}").classes("text-xs casa-muted")

            with ui.card().classes(card_classes("w-full p-3 sm:p-4 gap-0")):
                ui.label("Pagamentos feitos").classes("text-lg font-bold mb-2")
                if not payments:
                    ui.label("Nenhum pagamento registrado.").classes("casa-muted py-2")
                for p in payments:
                    with ui.row().classes("w-full items-center gap-2 py-2 border-b flex-nowrap"):
                        with ui.column().classes("gap-0 flex-1 min-w-0"):
                            ui.label(format_date_br(p.paid_on)).classes("font-medium")
                            detail = " · ".join(x for x in (p.method, p.notes) if x)
                            if detail:
                                ui.label(detail).classes("text-xs casa-muted")
                        ui.label(format_brl(p.value)).classes("font-bold whitespace-nowrap")
                        ui.button(icon="edit", on_click=lambda i=p: open_dialog(i)).props("flat round dense size=sm")
                        ui.button(icon="delete", on_click=lambda i=p: confirm_delete(i)).props("flat round dense size=sm")

    refresh()

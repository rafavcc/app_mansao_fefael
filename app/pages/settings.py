from nicegui import ui

from app import crud
from app.database import get_session
from app.theme import card_classes, page_container

KINDS = {"variable": "Categorias variáveis", "regular": "Categorias fixas"}


def build_settings() -> None:
    with page_container():
        with ui.column().classes("gap-0"):
            ui.label("Configurações").classes("casa-page-title text-2xl font-bold")
            ui.label("Remova categorias. As despesas existentes precisam ser reclassificadas.") \
                .classes("text-sm casa-muted")
        content = ui.column().classes("w-full gap-4")

    def load(kind: str) -> list[tuple[str, int]]:
        with get_session() as db:
            cats = crud.get_variable_categories(db) if kind == "variable" else crud.get_regular_categories(db)
            return sorted(
                ((c.name, crud.count_category_expenses(db, kind, c.name)) for c in cats),
                key=lambda row: row[0].casefold(),
            )

    def open_remove(kind: str, name: str, count: int) -> None:
        options = [n for n, _ in load(kind) if n != name]
        with ui.dialog() as dialog, ui.card().classes("w-full max-w-md gap-3"):
            ui.label(f"Remover '{name}'?").classes("text-lg font-bold")
            target = None
            if count:
                ui.label(f"{count} despesa(s) usam esta categoria. Escolha para onde elas vão:")
                target = ui.select(options, label="Nova categoria", with_input=True).classes("w-full").mark("target")
            else:
                ui.label("Nenhuma despesa usa esta categoria.")

            def confirm() -> None:
                replacement = target.value if target else None
                if count and not replacement:
                    ui.notify("Escolha a nova categoria antes de remover.", type="warning")
                    return
                try:
                    with get_session() as db:
                        result = crud.delete_category(db, kind, name, replacement)
                except crud.CategoryError as error:
                    ui.notify(str(error), type="warning")
                    return
                msg = f"'{name}' removida."
                if count:
                    msg += f" {result['moved'] + result['merged']} despesa(s) movida(s) para '{replacement}'."
                    if result["merged"]:
                        msg += f" {result['merged']} somada(s) a lançamentos já existentes no mês."
                ui.notify(msg, type="positive")
                dialog.close()
                refresh()

            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancelar", on_click=dialog.close).props("flat no-caps")
                ui.button("Remover", icon="delete", on_click=confirm) \
                    .props("unelevated no-caps color=negative").mark("confirm")
        dialog.open()

    def refresh() -> None:
        content.clear()
        with content:
            for kind, title in KINDS.items():
                rows = load(kind)
                with ui.card().classes(card_classes("w-full p-3 sm:p-4 gap-0")):
                    ui.label(title).classes("text-lg font-bold mb-2")
                    if not rows:
                        ui.label("Nenhuma categoria.").classes("casa-muted py-2")
                    for name, count in rows:
                        with ui.row().classes("w-full items-center justify-between py-2 border-b"):
                            with ui.column().classes("gap-0"):
                                ui.label(name).classes("font-medium")
                                ui.label(f"{count} despesa(s)").classes("text-xs casa-muted")
                            ui.button(icon="delete", on_click=lambda k=kind, n=name, c=count: open_remove(k, n, c)) \
                                .props("flat round dense size=sm")

    refresh()

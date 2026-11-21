from datetime import date
from typing import Optional

from nicegui import app, run, ui

from app.components import date_input, money_input, parse_date_input
from app.database import get_session
from app.formatting import PAYER_LABELS, format_brl, format_number_br, month_name, parse_money
from app.llm import available_models, llm_config, model_label
from app.native_select import NativeSelect
from app.photo_import import (
    MAX_PHOTO_BYTES, PhotoImportError, load_context, extract_photo, mark_duplicates, save_drafts,
)
from app.schemas import DraftExpense, PhotoExtraction, variable_expense_problem
from app.theme import card_classes, page_container

MODEL_KEY = "photo_import_model"


class DraftRow:
    """One editable row of the review table, bound to its DraftExpense."""

    def __init__(self, draft: DraftExpense, categories: list[str], on_change):
        self.draft = draft
        self.on_change = on_change
        self.container = ui.card().classes(card_classes("w-full p-2 gap-1"))
        with self.container:
            with ui.row().classes("w-full items-center gap-2"):
                self.checkbox = ui.checkbox(value=draft.selected, on_change=self._select).mark("row-select")
                self.date = date_input("Data", self._date()).props(f"max={date.today().isoformat()}") \
                    .classes("w-40").mark("row-date")
                self.date.on_value_change(self._edit)
                self.place = ui.input("Local", value=draft.place).classes("flex-1 min-w-[10rem]").mark("row-place")
                self.place.on_value_change(self._edit)
                value = draft.value
                self.value = money_input("Valor", format_number_br(value) if value else "") \
                    .classes("w-28").mark("row-value")
                self.value.on_value_change(self._edit)
                self.category = NativeSelect(categories, label="Grupo", value=draft.category_name) \
                    .classes("w-40").mark("row-category")
                self.category.on_value_change(self._edit)
                self.notes = ui.input("Notas", value=draft.notes or "").classes("flex-1 min-w-[8rem]") \
                    .mark("row-notes")
                self.notes.on_value_change(self._edit)
            with ui.row().classes("items-center gap-2 px-1"):
                self.badge = ui.badge("Possível duplicado", color="orange").props("outline")
                self.badge_tip = self.badge.tooltip(draft.duplicate_reason or "")
                self.error = ui.label().classes("text-xs casa-negative")
        self._refresh_state()

    def _date(self) -> date:
        d = self.draft
        try:
            return date(d.year, d.month, d.day)
        except (TypeError, ValueError):
            return date.today()

    def _select(self, e) -> None:
        self.draft.selected = bool(e.value)

    def _edit(self, _=None) -> None:
        d = self.draft
        when = parse_date_input(self.date.value)
        d.day, d.month, d.year = (when.day, when.month, when.year) if when else (None, None, None)
        d.place = (self.place.value or "").strip()
        d.value = parse_money(self.value.value)
        d.category_name = self.category.value
        d.notes = (self.notes.value or "").strip() or None
        d.error = variable_expense_problem(d.expense_data())
        self._refresh_state()
        self.on_change()

    def _refresh_state(self) -> None:
        d = self.draft
        self.error.set_text(d.error or "")
        self.error.set_visibility(bool(d.error))
        self.badge.set_visibility(d.possible_duplicate)
        self.container.classes(add="casa-row-error" if d.error else "", remove="" if d.error else "casa-row-error")

    def set_selected(self, selected: bool) -> None:
        self.checkbox.set_value(selected)

    def delete(self) -> None:
        self.container.delete()


class Section:
    """The review card of one photo: title with count and total, and its rows."""

    def __init__(self, extraction: PhotoExtraction, categories: list[str], host, on_empty):
        self.extraction = extraction
        self.rows: list[DraftRow] = []
        self.on_empty = on_empty
        with host:
            self.card = ui.card().classes(card_classes("w-full p-3 gap-2")).mark("photo-section")
        with self.card:
            if extraction.error:
                self.card.classes("casa-row-error")
                ui.label(extraction.error).classes("casa-negative")
                return
            with ui.row().classes("w-full items-center justify-between gap-2"):
                self.title = ui.label().classes("font-bold")
                with ui.row().classes("gap-1"):
                    ui.button("Todos", on_click=lambda: self.select_all(True)).props("flat dense no-caps")
                    ui.button("Nenhum", on_click=lambda: self.select_all(False)).props("flat dense no-caps")
            if not extraction.rows:
                ui.label("Nenhum gasto encontrado nesta foto.").classes("casa-muted")
            for draft in extraction.rows:
                self.rows.append(DraftRow(draft, categories, self.refresh_title))
        self.refresh_title()

    def refresh_title(self) -> None:
        if self.extraction.error:
            return
        name = month_name(self.extraction.month) if self.extraction.month else self.extraction.filename
        total = sum(r.draft.value or 0 for r in self.rows)
        self.title.set_text(f"{name} · {len(self.rows)} gastos · {format_brl(total)}")

    def select_all(self, selected: bool) -> None:
        for row in self.rows:
            row.set_selected(selected)

    def remove_saved(self, saved: list[DraftExpense]) -> None:
        ids = {id(d) for d in saved}
        for row in [r for r in self.rows if id(r.draft) in ids]:
            row.delete()
            self.rows.remove(row)
        if self.rows:
            self.refresh_title()
        else:
            self.card.delete()
            self.on_empty(self)


def show_summary(summary) -> None:
    with ui.dialog() as dialog, ui.card().classes(card_classes("p-4 gap-2")):
        ui.label("Simulação: nada foi salvo").classes("text-lg font-bold")
        ui.label(f"{summary.count} gastos, total {format_brl(summary.total)}")
        if summary.duplicates:
            ui.label(f"{summary.duplicates} possíveis duplicados entre os selecionados").classes("casa-muted")
        ui.button("Fechar", on_click=dialog.close).props("flat no-caps")
    dialog.open()


def build_photo_import() -> None:
    config = llm_config()
    photos: list[tuple[str, bytes]] = []
    sections: list[Section] = []
    remembered = app.storage.user.get(MODEL_KEY)

    with page_container():
        ui.label("Importar foto").classes("casa-page-title text-2xl font-bold")

        with ui.card().classes(card_classes("w-full p-3 gap-2")):
            with ui.row().classes("items-center gap-3"):
                ui.label("Pago por").classes("text-sm casa-muted")
                paid_by = ui.toggle(PAYER_LABELS, value=None).props("no-caps unelevated").mark("paid_by")
            model = NativeSelect({config.model: config.model}, label="Modelo", value=config.model) \
                .classes("w-full").mark("model")
            dry_run = ui.switch("Simulação (não salva nada)", value=True).mark("dry_run")

            def rejected(_) -> None:
                ui.notify("Arquivo recusado (máx. 20 MB, só imagens).", type="warning")

            async def received(e) -> None:
                photos.append((e.file.name, await e.file.read()))

            upload = ui.upload(multiple=True, auto_upload=True, on_upload=received, on_rejected=rejected,
                               label="Fotos das páginas", max_file_size=MAX_PHOTO_BYTES) \
                .props('accept="image/*"').classes("w-full").mark("upload")
            read_button = ui.button("Ler fotos", icon="photo_camera").props("unelevated no-caps").mark("read")
            with ui.row().classes("items-center gap-2") as progress:
                ui.spinner(size="sm")
                progress_label = ui.label()
            progress.set_visibility(False)

        review = ui.column().classes("w-full gap-3")
        save_button = ui.button("Salvar selecionados", icon="save").props("unelevated no-caps size=lg") \
            .classes("w-full").mark("save")
        save_button.set_visibility(False)

        async def load_models() -> None:
            infos = await run.io_bound(available_models, config)
            options = {m.id: model_label(m) for m in infos}
            model.set_options(options, value=remembered if remembered in options else config.model)
            model.on_value_change(lambda e: app.storage.user.__setitem__(MODEL_KEY, e.value))

        ui.timer(0.1, load_models, once=True)

        def drop_section(section: Section) -> None:
            sections.remove(section)
            save_button.set_visibility(bool(sections))

        async def read_photos() -> None:
            if not paid_by.value:
                ui.notify("Selecione quem pagou.", type="warning")
                return
            if not photos:
                ui.notify("Envie pelo menos uma foto.", type="warning")
                return
            batch = list(photos)
            photos.clear()
            upload.reset()
            read_button.disable()
            progress.set_visibility(True)
            try:
                with get_session() as db:
                    ctx = load_context(db, paid_by.value)
                for i, (name, data) in enumerate(batch, start=1):
                    progress_label.set_text(f"Lendo foto {i} de {len(batch)}…")
                    extraction = await run.io_bound(extract_photo, data, name, ctx, model.value)
                    data = None
                    earlier = [r.draft for s in sections for r in s.rows]
                    with get_session() as db:
                        mark_duplicates(db, extraction.rows, earlier)
                    sections.append(Section(extraction, ctx.categories, review, drop_section))
                    save_button.set_visibility(True)
                    batch[i - 1] = (name, b"")
            finally:
                batch.clear()
                progress.set_visibility(False)
                read_button.enable()

        def save_selected() -> None:
            chosen = [(s, r.draft) for s in sections for r in s.rows if r.draft.selected]
            if not chosen:
                ui.notify("Nenhuma linha selecionada.", type="warning")
                return
            drafts = [d for _, d in chosen]
            try:
                with get_session() as db:
                    summary = save_drafts(db, drafts, dry_run=dry_run.value)
            except PhotoImportError as exc:
                ui.notify(str(exc), type="negative")
                return
            if not summary.saved:
                show_summary(summary)
                return
            ui.notify(f"{summary.count} gastos salvos.", type="positive")
            for section in list(sections):
                section.remove_saved(drafts)

        read_button.on_click(read_photos)
        save_button.on_click(save_selected)

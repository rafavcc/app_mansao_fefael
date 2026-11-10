from pathlib import Path

from nicegui import app as nicegui_app, ui

from app import crud
from app.database import get_session
from app.pages.balance import build_balance
from app.pages.home import build_home
from app.pages.income import build_income
from app.pages.settings import build_settings
from app.pages.payments import build_payments
from app.pages.regular import build_regular_expenses
from app.pages.variable import build_variable_expenses
from app.theme import apply_app_theme

STATIC_DIR = Path(__file__).parent / "static"

NAV_ITEMS = [
    ("home", "Início", "home", "/"),
    ("variable", "Variáveis", "receipt_long", "/variable"),
    ("regular", "Fixos", "event_repeat", "/regular"),
    ("balance", "Balanço", "account_balance_wallet", "/balance"),
    ("income", "Planejamento", "savings", "/income"),
    ("payments", "Pagamentos", "payments", "/payments"),
    ("settings", "Config.", "settings", "/settings"),
]


def layout(title: str, active: str) -> None:
    """Header (top nav on iPad/Mac) and bottom tab bar (iPhone), shared by every page."""
    apply_app_theme()
    # Idempotent; covers a server that keeps running into a new month.
    with get_session() as db:
        crud.autofill_current_month_regular_expenses(db)

    with ui.header(elevated=False).classes("casa-header items-center"):
        ui.label(title).classes("text-lg font-bold")
        ui.space()
        with ui.row().classes("casa-nav gap-1 items-center"):
            for key, label, icon, target in NAV_ITEMS:
                ui.button(label, icon=icon, on_click=lambda path=target: ui.navigate.to(path)) \
                    .props("flat dense no-caps") \
                    .classes("is-active" if key == active else "")
            ui.button(icon="dark_mode", on_click=lambda: ui.run_javascript("window.casaTheme.toggle()")) \
                .props("flat round dense") \
                .classes("ml-2") \
                .tooltip("Alternar tema")

    with ui.footer(elevated=False).classes("casa-tabbar"):
        for key, label, icon, target in NAV_ITEMS:
            ui.button(label, icon=icon, on_click=lambda path=target: ui.navigate.to(path)) \
                .props("flat stack no-caps") \
                .classes("is-active" if key == active else "")


def register_pages() -> None:
    nicegui_app.add_static_files("/static", STATIC_DIR)

    @ui.page("/", title="Mansão Fefael")
    def page_home():
        layout("Mansão Fefael", "home")
        build_home()

    @ui.page("/variable", title="Gastos Variáveis")
    def page_variable():
        layout("Gastos Variáveis", "variable")
        build_variable_expenses()

    @ui.page("/regular", title="Gastos Fixos")
    def page_regular():
        layout("Gastos Fixos", "regular")
        build_regular_expenses()

    @ui.page("/balance", title="Balanço")
    def page_balance():
        layout("Balanço", "balance")
        build_balance()

    @ui.page("/income", title="Planejamento")
    def page_income():
        layout("Planejamento", "income")
        build_income()

    @ui.page("/payments", title="Pagamentos")
    def page_payments():
        layout("Pagamentos", "payments")
        build_payments()

    @ui.page("/settings", title="Configurações")
    def page_settings():
        layout("Configurações", "settings")
        build_settings()

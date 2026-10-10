from datetime import date

from nicegui import events, ui

from app import crud
from app.balance import calculate_month_detail, calculate_year_months
from app.components import (
    COLORS,
    base_chart,
    category_axis,
    change_hint,
    kpi_card,
    money_input,
    person_split,
    settlement_banner,
    value_axis,
    year_select,
)
from app.database import get_session
from app.formatting import format_brl, format_number_br, format_pct, month_name, parse_money
from app.theme import card_classes, page_container


CHART_VIEWS = {
    "spending": "Gastos",
    "payers": "Quem pagou",
    "saldo": "Saldo",
    "categories": "Categorias",
}

CATEGORY_COLORS = (
    "#0ea5e9", "#8b5cf6", "#f59e0b", "#ef4444", "#10b981", "#ec4899",
    "#6366f1", "#84cc16", "#f97316", "#14b8a6", "#a855f7", "#eab308",
    "#06b6d4", "#d946ef", "#22c55e", "#fb7185", "#64748b", "#a3e635",
)

SALDO_TOOLTIP_JS = """(p) => {
    const v = p[0].value;
    const f = Math.abs(v).toLocaleString("pt-BR", {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const text = v > 0 ? `Fafa deve R$ ${f}` : v < 0 ? `Fafa pagou R$ ${f}` : "Contas iguais";
    return p[0].name + "<br>" + text;
}"""


def _labels(months: list[dict]) -> list[str]:
    return [month_name(month["month"], short=True) for month in months]


def spending_chart(months: list[dict]) -> dict:
    return base_chart(
        xAxis=category_axis(_labels(months)),
        yAxis=value_axis(),
        series=[
            {
                "name": "Variável",
                "type": "bar",
                "stack": "total",
                "data": [m["variable_total"] for m in months],
                "itemStyle": {"color": COLORS["variable"]},
            },
            {
                "name": "Fixo",
                "type": "bar",
                "stack": "total",
                "data": [m["regular_total"] for m in months],
                "itemStyle": {"color": COLORS["regular"]},
            },
        ],
    )


def payers_chart(months: list[dict]) -> dict:
    def should_line(name: str, key: str, color: str) -> dict:
        return {
            "name": name,
            "type": "line",
            "data": [m[key] for m in months],
            "lineStyle": {"type": "dashed", "color": color},
        }

    return base_chart(
        xAxis=category_axis(_labels(months)),
        yAxis=value_axis(),
        series=[
            {
                "name": "Fafa pagou",
                "type": "bar",
                "data": [m["fafa_paid"] for m in months],
                "itemStyle": {"color": COLORS["FAFA"]},
                "showLine": False,
            },
            {
                "name": "Fefe pagou",
                "type": "bar",
                "data": [m["fefe_paid"] for m in months],
                "itemStyle": {"color": COLORS["FEFE"]},
                "showLine": False,
            },
            should_line("Fafa deveria", "fafa_should_pay", COLORS["FAFA"]),
            should_line("Fefe deveria", "fefe_should_pay", COLORS["FEFE"]),
        ],
    )


def saldo_chart(months: list[dict]) -> dict:
    """Bars: Fefe owes Fafa. Negative bars: Fafa owes Fefe."""
    data = [
        {
            "value": m["balance"],
            "itemStyle": {
                "color": COLORS["FAFA"] if m["balance"] >= 0 else COLORS["FEFE"]
            },
        }
        for m in months
    ]

    return base_chart(
        tooltip={"trigger": "axis", "confine": True, ":formatter": SALDO_TOOLTIP_JS},
        grid={"left": 8, "right": 12, "top": 26, "bottom": 8, "containLabel": True},
        xAxis=category_axis(_labels(months)),
        yAxis=value_axis(),
        series=[
            {
                "name": "Saldo",
                "type": "bar",
                "data": data,
                "itemStyle": {"borderRadius": 4},
            }
        ],
    )


def category_chart(detail: dict) -> dict:
    items = [(c["name"], c, "variable") for c in detail["variable_categories"]]
    items += [(c["name"], c, "regular") for c in detail["regular_categories"]]

    # ECharts draws the first category at the bottom
    items.reverse()

    return {
        "grid": {
            "left": 8,
            "right": 16,
            "top": 8,
            "bottom": 32,
            "containLabel": True,
        },
        "tooltip": {"trigger": "axis", "confine": True},
        "xAxis": value_axis(),
        "yAxis": category_axis([name for name, _, _ in items]),
        "series": [
            {
                "name": "Este mês",
                "type": "bar",
                "data": [
                    {
                        "value": c["total"],
                        "itemStyle": {
                            "color": COLORS[kind],
                            "borderRadius": [0, 4, 4, 0],
                        },
                    }
                    for _, c, kind in items
                ],
                "itemStyle": {"color": COLORS["variable"]},
            },
            {
                "name": "Mês anterior",
                "type": "bar",
                "data": [
                    {
                        "value": c["previous_total"],
                        "itemStyle": {
                            "color": COLORS["previous"],
                            "opacity": 0.5,
                            "borderRadius": [0, 4, 4, 0],
                        },
                    }
                    for _, c, _ in items
                ],
            },
        ],
    }


def category_spending_chart(months: list[dict]) -> dict:
    values_by_category: dict[tuple[str, str], list[float]] = {}

    for month_index, month in enumerate(months):
        for kind, field in (
            ("variable", "variable_categories"),
            ("regular", "regular_categories"),
        ):
            for category in month[field]:
                key = (kind, category["name"])
                values_by_category.setdefault(key, [0.0] * len(months))[month_index] = category["total"]

    series = []
    for index, ((kind, name), values) in enumerate(sorted(values_by_category.items())):
        label = "Variável" if kind == "variable" else "Fixo"
        series.append({
            "name": f"{label}: {name}",
            "type": "bar",
            "stack": "total",
            "data": values,
            "itemStyle": {"color": CATEGORY_COLORS[index % len(CATEGORY_COLORS)]},
        })

    return base_chart(
        legend={"type": "scroll", "bottom": 0},
        xAxis=category_axis(_labels(months)),
        yAxis=value_axis(),
        series=series,
    )


CHART_BUILDERS = {
    "spending": spending_chart,
    "payers": payers_chart,
    "saldo": saldo_chart,
    "categories": category_spending_chart,
}


def build_balance() -> None:
    today = date.today()
    state: dict = {"months": {}, "view": "spending"}
    sections: dict[int, ui.element] = {}
    holders: dict[int, ui.column] = {}

    with page_container():
        ui.label("Balanço do mês").classes("casa-page-title text-2xl font-bold")

        with ui.row().classes("w-full gap-3 px-3"):
            year = year_select(today.year, on_change=lambda: load())
            ui.label("Ano").classes("text-xs casa-muted")

        with ui.row().classes("w-full gap-3"):
            with ui.card().classes(card_classes("w-full p-3 gap-2")) as chart_card:
                ui.toggle(
                    CHART_VIEWS,
                    value="spending",
                    on_change=lambda e: set_view(e.value),
                ).props("spread").classes("chart-view")

                chart_area = ui.column().classes("w-full")

                ui.label(
                    "Toque em um mês para ver os detalhes."
                ).classes("text-xs casa-muted")

        sections_column = ui.column().classes("w-full gap-3")

    def set_view(view: str) -> None:
        state["view"] = view
        render_chart()

    def ordered_months() -> list[int]:
        return [
            m for m in sorted(state["months"])
            if state["months"][m].get("month")
        ]

    def render_chart() -> None:
        chart_area.clear()
        month_numbers = ordered_months()

        chart_card.set_visibility(bool(month_numbers))

        if not month_numbers:
            return

        months = [state["months"][month] for month in month_numbers]
        with chart_area:
            ui.echart(
                CHART_BUILDERS[state["view"]](months),
                on_point_click=open_month,
            ).classes("w-full h-72")

    def open_month(e: events.EChartPointClickEventArguments) -> None:
        month = ordered_months()[e.data_index]
        section = sections.get(month)

        if section is None:
            return

        if isinstance(section, ui.expansion):
            section.value = True

        ui.run_javascript(
            f'getHtmlElement("{section.id}").scrollIntoView({{behavior: "smooth", block: "start"}})'
        )

    def reload_month(month: int) -> None:
        with get_session() as db:
            state["months"][month] = calculate_month_detail(
                db,
                month,
                int(year.value),
            )

        render_month(month, expanded=True)
        render_chart()

    def render_month(month: int, expanded: bool) -> None:
        detail = state["months"][month]
        holder = holders[month]

        holder.clear()

        with holder:
            if not detail:
                with ui.card().classes(card_classes("w-full p-3 casa-month")) as empty:
                    ui.label("Sem gastos").classes("text-sm casa-muted")

                sections[month] = empty
                return

            section = ui.expansion(
                value=expanded
            ).classes(card_classes("w-full casa-month")).mark(f"month-{month}")

            sections[month] = section

            with section:
                body = ui.column().classes("w-full")

            with section.add_slot("header"):
                with ui.row().classes("w-full justify-between no-wrap gap-2"):
                    with ui.column().classes("gap-0"):
                        ui.label(
                            f"{month_name(month)} {detail['year']}"
                        ).classes("font-bold")
                        ui.label(
                            settlement_banner(detail)
                        )

                    ui.label(
                        format_brl(detail["total_expenses"])
                    ).classes("font-bold text-lg")

            # Charts inside closed sections would render at zero size, so build
            # the body only when the section is opened.
            built = {"done": False}

            def build_body() -> None:
                if built["done"]:
                    return

                built["done"] = True
                with body:
                    month_body(detail, on_ratio_saved=reload_month)

            section.on_value_change(
                lambda e: build_body() if e.value else None
            )

            if expanded:
                build_body()

    def load() -> None:
        state["months"].clear()
        sections_column.clear()
        sections.clear()
        holders.clear()

        with get_session() as db:
            months = calculate_year_months(db, int(year.value))

        for detail in months:
            month = detail["month"]
            state["months"][month] = detail
            with sections_column:
                holders[month] = ui.column().classes("w-full")
            render_month(month, expanded=False)

        render_chart()


    load()


def month_body(detail: dict, on_ratio_saved) -> None:
    month, year = detail["month"], detail["year"]

    with ui.column().classes("w-full gap-3 px-3 pb-3"):
        hint, hint_classes = change_hint(detail)

        with ui.row().classes("w-full grid grid-cols-1 sm:grid-cols-3 gap-3 w-full"):
            kpi_card(
                "Total",
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

        n_categories = len(detail["variable_categories"]) + len(
            detail["regular_categories"]
        )

        with ui.card().classes(card_classes("w-full p-3 gap-1")):
            ui.label("Categorias").classes("font-bold")
            ui.echart(category_chart(detail)).classes("w-full").style(
                f"height: {max(160, 34 * n_categories + 60)}px"
            )

        with ui.card().classes(card_classes("w-full p-3 gap-2")):
            ui.label("Divisão do mês").classes("font-bold")

            with ui.row().classes("items-end gap-3"):
                fafa_pct = money_input(
                    "Fafa %",
                    format_number_br(detail["fafa_ratio"] * 100),
                ).classes("w-28").mark(f"fafa-pct-{month}")

                fefe_label = ui.label(
                    f"Fefe: {format_pct(detail['fefe_ratio'] * 100)}"
                ).classes("text-sm casa-muted mb-2")

            def update_fefe_label() -> None:
                value = parse_money(fafa_pct.value)
                fefe_label.set_text(
                    f"Fefe: {format_pct(100 - value)}"
                    if value is not None
                    else "Fefe: —"
                )

            fafa_pct.on_value_change(update_fefe_label)

            def save_ratio() -> None:
                value = parse_money(fafa_pct.value)

                if value is None or not 1 <= value <= 99:
                    ui.notify(
                        "Fafa deve estar entre 1 e 99.",
                        type="warning",
                    )
                    return

                with get_session() as db:
                    crud.set_month_ratio(db, month, year, value / 100)

                ui.notify("Divisão salva!", type="positive")
                on_ratio_saved(month)

            ui.button(
                "Salvar divisão",
                icon="save",
                on_click=save_ratio,
            ).props("unelevated no-caps").mark(f"save-ratio-{month}")

# Balance page uses the payments settlement (single source of truth)

## Problem

`/balance` (and the home page) show "Fefe deve R$ X para Fafa" from the raw month saldo
(`app/balance.py::build_month_balance`), ignoring payments. `/payments`
(`app/payments.py::calculate_payments`) allocates payments oldest-first and knows each
closed month is `paid`. The two pages disagree.

## Design

- `app/balance.py` stays pure month arithmetic (no change in behaviour, no import of payments).
- `app/payments.py` is the **only** place that decides settlement. It already imports
  `build_month_balance` from balance, so balance must NOT import payments (cycle).
- Pages compose: compute details with balance, then annotate them with payments.

### Statuses (per month)

| status        | when                                                         |
|---------------|--------------------------------------------------------------|
| `open`        | closed billed month, owed > 0, nothing covered               |
| `partial`     | closed billed month, owed > 0, partially covered             |
| `paid`        | closed billed month, owed > 0, fully covered                 |
| `settled`     | closed billed month, owed == 0                               |
| `credit`      | closed billed month, owed < 0 (Fafa owes Fefe)               |
| `prebilling`  | month before `FIRST_BILLED_MONTH` (already settled by rule)  |
| `in_progress` | current or future month (not billable yet; saldo provisional)|

The first five are exactly what `calculate_payments` produces today — unchanged.

## Steps (TDD: write the failing test first for each)

### 1. `app/payments.py`

- Extract the per-month allocation out of `calculate_payments` into
  `month_settlements(db, today=None, first=FIRST_BILLED_MONTH) -> list[dict]`
  returning the same month dicts (`month, year, owed, covered, remaining, status`)
  in chronological order. `calculate_payments` calls it and only aggregates
  (`billed_total`, `paid_total`, `debt`, `open_months`). Output of
  `calculate_payments` must be byte-for-byte identical (existing tests in
  `tests/test_payments.py` must pass untouched).
- Add `settlement_for(settlements_by_month: dict, year, month, balance, today, first) -> dict`
  (pure, no db):
  - `(year, month)` in map → that dict.
  - `(year, month) < first` → `{"status": "prebilling", "owed": balance, "covered": 0.0, "remaining": 0.0}`
  - otherwise → `{"status": "in_progress", "owed": balance, "covered": 0.0, "remaining": balance if balance > 0 else 0.0}`
- Add `attach_settlements(db, details: list[dict], today=None, first=FIRST_BILLED_MONTH) -> list[dict]`:
  calls `month_settlements` once, builds `{(year, month): m}`, sets
  `detail["settlement"] = settlement_for(..., detail["balance"], ...)` on each detail
  (skip falsy/empty details), returns the list. Single DB pass for the year.

### 2. `app/components.py`

- Replace `settlement_text(balance: float)` with `settlement_text(detail: dict) -> str`.
  Use `detail["settlement"]` when present; fall back to the raw `detail["balance"]`
  behaviour when absent (keeps it safe for any caller without settlement).
  Texts (pt-BR, use `format_brl`):
  - `open`        → `Fefe deve {owed} para Fafa`
  - `partial`     → `Fefe ainda deve {remaining} para Fafa`
  - `paid`        → `Quite · Fefe pagou {owed}`
  - `settled`     → `Contas iguais`
  - `credit`      → `Fafa deve {-owed} para Fefe`
  - `prebilling`  → `Quite`
  - `in_progress` → raw-balance text + ` · mês em andamento`
    (raw text: `Fefe deve X para Fafa` / `Fafa deve X para Fefe` / `Contas iguais`)
- Add `is_settled(detail) -> bool` (True for `paid`, `settled`, `prebilling`)
  and make `settlement_banner(detail)` use `check_circle` when settled, else `swap_horiz`.
  For `partial`, also show a small muted line `de {owed}` under the text.
- `person_split` stays on the raw saldo (it is the month's arithmetic).

### 3. Pages

- `app/pages/balance.py`:
  - `load()`: `months = attach_settlements(db, calculate_year_months(db, year), ...)` inside the same session.
  - `reload_month()`: wrap the single detail: `attach_settlements(db, [detail])[0]`.
  - Fix the header bug at the `ui.label(settlement_banner(detail))` line →
    `ui.label(settlement_text(detail)).classes("text-xs casa-muted")`.
  - Saldo chart stays on raw balance (unchanged).
- `app/pages/home.py`: annotate the single detail with `attach_settlements` before rendering.
- `app/pages/payments.py`: no behaviour change.
- `app/main.py` JSON endpoints: no change.

### 4. Tests

- `tests/test_payments.py` (existing must stay green, add):
  - `month_settlements` equals `calculate_payments(...)["months"]`.
  - `attach_settlements`: a paid closed month gets `paid`; month before `first`
    gets `prebilling`; current month gets `in_progress` with `owed == balance`.
  - Regression for the reported bug: Fafa paid July+August, a payment covering both →
    both details have status `paid` and `settlement_text` starts with `Quite`.
- New `tests/test_settlement_text.py` (pure, no UI): one case per status plus the
  no-settlement fallback.

### 5. Verify

- `python -m pytest -q` all green.
- Do NOT commit. The user will test manually first.

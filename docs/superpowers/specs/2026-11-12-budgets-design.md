# Budgets per period — design

## Why
The Planejamento page holds one plan (income, expenses, savings) with no dates. Life changes it: a
babysitter starts in Nov/2026, salaries changed over the past years. Past months must keep showing the plan
that was true for them. Rafa will also import past expenses and create budgets for past years, so the app
must hold many budgets, each assigned to periods of time.

## Goals
- Create as many **budgets** (orçamentos) as needed. A budget has **income items and expense items**.
- Assign each budget one or more **month ranges** ("Jan/2024 – Out/2026", "Nov/2026 →" open-ended).
- **A month belongs to at most one budget.** Overlaps are never stored.
- The Planejamento page edits one budget at a time and compares a chosen month's actual spending with the
  budget that covers that month.
- Every change can be reverted: code and data (see *Revert*).

## Non-goals
- Savings. The savings section, model, table and code are **removed**, not moved into budgets.
- Using budgets anywhere outside the Planejamento page (Balanço, home, API) in this iteration.
- Importing past expenses (a later feature; this one only makes past budgets possible).
- Per-month overrides inside a budget.

## Anti-goals
- A past month's numbers changing because a newer budget was created or edited.
- Losing any existing income or expense item in the migration.
- A rollback that throws away expenses, payments or ratios entered after the deploy.

## Approaches considered
- **A. Budget + ranges table (chosen by Rafa).** `budgets`, `budget_periods` (start, optional end), and a
  `budget_id` on each item. Matches how Rafa thinks about it; duplicating is cheap; open-ended ranges are
  natural. Overlap rules live in code, not in a DB constraint.
- B. One row per month (month → budget). The DB enforces uniqueness, but "Nov/2026 onward" can't be stored
  and long ranges become hundreds of rows. Rejected.
- C. No budget, dates on each item. Doesn't match named budgets for past years; "one month, one budget" loses
  meaning. Rejected.

## Data model
- `budgets`: `id`, `name` (unique, non-empty), `created_at`.
- `budget_periods`: `id`, `budget_id` (FK → budgets, ON DELETE CASCADE), `start_month`, `start_year`,
  `end_month`, `end_year` (both NULL = open-ended, or both set). CHECKs: months 1–12; end ≥ start.
- `income_items.budget_id` and `planned_expenses.budget_id`: NOT NULL, FK → budgets, ON DELETE CASCADE.
- `savings_items`: dropped.

Months are compared as an integer key `year * 12 + (month - 1)`; an open end is +∞.

## Rules
- **Overlap.** Saving a range (new or edited) that overlaps any other range, of any budget including the same
  one, is refused with a message naming the conflicting budget and range.
- **Closing an open range (Rafa's case).** If the only conflict is an *open-ended* range that starts *before*
  the new range, the app asks: "Encerrar 'X' em Out/2026?" (the month before the new start). Confirm → that
  range gets that end and the new range is saved in one transaction. Cancel → nothing changes.
- **Lookup.** `budget_for_month(month, year)` returns the one budget covering it, or none.
- **Delete budget** removes its items and ranges after a confirmation naming how many of each.
- **Duplicate** copies a budget's income and expense items under a new name; ranges are not copied.
- Category rename/delete keeps updating `planned_expenses` across all budgets (existing behaviour).

## Planejamento page
```
Planejamento
[ Orçamento: Babá 2026 ▾ ]  [Novo] [Renomear] [Excluir]
Períodos: Nov/2026 → (em aberto)   [editar] [x]     [+ Adicionar período]
Mês comparado: [ Nov/2026 ▾ ]
[ Saldo livre ]  [ Realizado em Nov/2026 vs orçamento ]
Renda mensal        (unchanged: gross / taxes / net)
Despesas mensais    (unchanged)
```
- Opens on the budget covering the current month; if none, the first budget by name; if there are no budgets,
  an empty state with "Criar orçamento".
- "Novo" asks for a name and *duplicate the selected budget* or *start empty*.
- Month picker lists the months covered by the selected budget, newest first; an open end stops at the current
  month. A budget with no ranges shows "Sem períodos" in the Realizado card.
- Free balance = net income − expenses (savings removed).
- `calculate_plan(db, budget_id, month, year)` replaces the current signature.

## Migration (startup, existing `init_db` pattern)
Runs once, detected by `budget_id` missing from `income_items`. Takes the existing pre-migration backup first.
In one transaction:
1. Create `budgets`, `budget_periods`.
2. If there are any income or expense items, create budget **"Orçamento atual"** with no ranges
   (Rafa then sets its range, e.g. up to Out/2026, and duplicates it for Nov/2026 →).
3. Rebuild `income_items` and `planned_expenses` with `budget_id` NOT NULL, copying every row into that budget.
4. Drop `savings_items`.
A failure rolls back the transaction and leaves the old schema; the app logs the error.

## Revert
Code and data are revertible independently of each other.
- **Code:** work on branch `feature/budgets`. Before merging, tag `main` as `pre-budgets`; after, tag
  `budgets-v1`. Revert = `git checkout pre-budgets` (or `git revert` the merge) and restart.
- **Data:** `scripts/rollback_budgets.py <pre-migration backup>`. It stops if the app is running, makes a
  fresh backup, then in one transaction drops `budgets` and `budget_periods` and restores **only**
  `income_items`, `planned_expenses` and `savings_items` from the given backup. Expenses, payments, ratios and
  categories entered after the deploy are kept. Budget edits made after the deploy are lost (stated in its
  output).
- The rollback script is tested: migrate → rollback → old schema and original plan rows are back.

## DevOps loop
- **Plan:** this document, then an implementation plan.
- **Code:** first commit the current uncommitted work on `main` (native select, theme). Then branch
  `feature/budgets`, tests first.
- **Build:** `pip install -r requirements.txt`, app starts against a copy of the real `casa.db`.
- **Test:** pytest locally and in CI (`.github/workflows/tests.yml`). New tests: overlap rules, open-range
  closing, month lookup, duplicate, delete cascade, plan totals per budget, migration on an old-schema DB,
  rollback round trip. Manual check on a copy of `casa.db`.
- **Release:** PR → merge to `main`, tags `pre-budgets` / `budgets-v1`.
- **Deploy:** before deploying, note the current Planejamento totals (income, expenses, free balance).
  Stop the server, pull, start: the migration runs with its backup.
- **Operate:** set up the real budgets: give "Orçamento atual" its range up to Out/2026, duplicate it as the
  babysitter budget for Nov/2026 →, add the babysitter.
- **Monitor:** check the startup log for the migration and backup lines, `/api/health`, and that
  "Orçamento atual" shows the totals noted before the deploy. Keep the pre-migration backup until the
  feature has been in use for a few weeks.

## Calls left to the builder
- Exact wording of messages, dialogs and button labels (Portuguese, matching the existing pages).
- Whether ranges are edited in a dialog or inline.
- Internal function names beyond `calculate_plan` and `budget_for_month`.

## Calls made by Claude (not discussed with Rafa)
- Migrated budget named "Orçamento atual" with **no** range, rather than guessing its start date.
- Duplicating copies items but not ranges.
- Delete budget cascades to its items and ranges.
- Month picker only offers months the budget covers; open ends stop at the current month.

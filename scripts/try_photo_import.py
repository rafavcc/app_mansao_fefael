"""Try the photo import against the real LLM server, without touching the database.

    venv/bin/python scripts/try_photo_import.py <photo> [--payer FEFE] [--model ID] [--no-downscale]

Loads .env, builds the context from the database at CASA_DB_PATH (read only), reads the photo with
extract_photo and prints the elapsed seconds and the rows as a table. Never writes to the database.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.env import load_env_file  # noqa: E402

load_env_file()  # before app.database, which reads CASA_DB_PATH at import time

from app import llm  # noqa: E402
from app.database import get_session  # noqa: E402
from app.photo_import import extract_photo, load_context  # noqa: E402

HEADERS = ("date", "place", "value", "group", "notes", "error")


def _cells(row) -> tuple:
    date_text = f"{row.day or '?'}/{row.month or '?'}/{row.year or '?'}"
    value = "" if row.value is None else f"{row.value:.2f}"
    return (date_text, row.place, value, row.category_name or "", row.notes or "", row.error or "")


def print_table(rows) -> None:
    table = [HEADERS] + [_cells(r) for r in rows]
    widths = [max(len(line[i]) for line in table) for i in range(len(HEADERS))]
    for line in table:
        print("  ".join(cell.ljust(w) for cell, w in zip(line, widths)).rstrip())


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read an expense page photo with the local LLM.")
    parser.add_argument("photo", type=Path)
    parser.add_argument("--payer", default="FEFE")
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-downscale", action="store_true")
    parser.add_argument("--show-prompt", action="store_true")
    args = parser.parse_args(argv)

    config = llm.llm_config()
    model = args.model or config.model
    data = args.photo.read_bytes()
    with get_session() as db:
        ctx = load_context(db, args.payer)
    if args.show_prompt:
        print(ctx.prompt)
    print(f"model={model} payer={args.payer} downscale={not args.no_downscale}")
    started = time.perf_counter()
    result = extract_photo(
        data, args.photo.name, ctx, model, config=config, downscale=not args.no_downscale
    )
    elapsed = time.perf_counter() - started
    print(f"elapsed: {elapsed:.1f} s")
    if result.error:
        print(f"error: {result.error}")
        return 1
    print(f"heading month: {result.month}")
    print_table(result.rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

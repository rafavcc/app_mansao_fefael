"""Importação de despesas variáveis a partir de fotos: helpers puros."""
import io
import json
import unicodedata
from datetime import date
from typing import Optional

from PIL import Image, ImageOps

from app.formatting import MONTHS_PT, parse_money
from app.schemas import DraftExpense, variable_expense_problem

MAX_LONG_SIDE = 1600
MAX_PHOTO_BYTES = 20 * 1024 * 1024
FALLBACK_CATEGORY = "Outros"

_SECTIONS = {"cartao": "Cartão", "card": "Cartão", "pix": "Pix"}


class PhotoImportError(ValueError):
    """Erro de importação de foto, com mensagem em português."""


def _fold(value: str) -> str:
    """Minúsculas, sem acentos e sem espaços nas pontas."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip().lower()


_MONTH_LOOKUP = {}
for _number, _name in enumerate(MONTHS_PT, start=1):
    _MONTH_LOOKUP[_fold(_name)] = _number
    _MONTH_LOOKUP[_fold(_name)[:3]] = _number


def prepare_image(data: bytes) -> tuple[bytes, str]:
    """Corrige rotação, reduz o lado maior a 1600 px e devolve JPEG."""
    try:
        with Image.open(io.BytesIO(data)) as source:
            img = ImageOps.exif_transpose(source).convert("RGB")
    except Exception as exc:
        raise PhotoImportError(
            "Arquivo não é uma imagem suportada (use JPG ou PNG)."
        ) from exc
    img.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue(), "image/jpeg"


def parse_reply(text: str) -> dict:
    """Extrai o objeto JSON da resposta da IA, tolerando cercas e texto extra."""
    invalid = PhotoImportError("A resposta da IA não é um JSON válido.")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise invalid
    try:
        parsed = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise invalid from exc
    if not isinstance(parsed, dict):
        raise invalid
    return parsed


def parse_month(value) -> Optional[int]:
    """Mês 1-12 a partir de número, texto numérico, nome ou abreviação."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 12 else None
    if not isinstance(value, str):
        return None
    key = _fold(value)
    if key.isdigit():
        return parse_month(int(key))
    return _MONTH_LOOKUP.get(key)


def infer_year(month: int, day: int, today: date) -> Optional[int]:
    """Ano mais recente cujo (mês, dia) não é posterior a hoje."""
    for year in range(today.year, today.year - 9, -1):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate <= today:
            return year
    return None


def build_notes(section: Optional[str], note: Optional[str]) -> Optional[str]:
    """Monta as notas: seção (Cartão/Pix) e a observação lida, se houver."""
    label = _SECTIONS.get(_fold(section)) if isinstance(section, str) else None
    text = note.strip() if isinstance(note, str) else ""
    if label and text:
        return f"{label} - {text}"
    return label or text or None


def match_category(name: Optional[str], categories: list[str]) -> Optional[str]:
    """Grupo do banco (ignorando caixa) ou 'Outros' se existir; senão None."""
    if isinstance(name, str):
        wanted = name.strip().lower()
        for category in categories:
            if category.lower() == wanted:
                return category
    return FALLBACK_CATEGORY if FALLBACK_CATEGORY in categories else None


def _number(value) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return parse_money(value) if isinstance(value, str) else None


def _day(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def rows_from_reply(
    reply: dict, paid_by: str, categories: list[str], today: date
) -> tuple[Optional[int], list[DraftExpense]]:
    """Mês do cabeçalho e linhas de rascunho validadas a partir da resposta da IA."""
    items = reply.get("items")
    if not isinstance(items, list):
        raise PhotoImportError("A IA não devolveu a lista de gastos.")
    heading_month = parse_month(reply.get("month"))
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        day = _day(item.get("day"))
        month = parse_month(item.get("month")) or heading_month
        place = item.get("place")
        row = DraftExpense(
            place=place.strip() if isinstance(place, str) else "",
            day=day,
            month=month,
            year=infer_year(month, day, today) if day and month else None,
            value=_number(item.get("value")),
            paid_by=paid_by,
            category_name=match_category(item.get("category_name"), categories),
            notes=build_notes(item.get("section"), item.get("note")),
        )
        row.error = variable_expense_problem(row.expense_data())
        row.selected = row.error is None
        rows.append(row)
    return heading_month, rows

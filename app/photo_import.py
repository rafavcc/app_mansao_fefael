"""Importação de despesas variáveis a partir de fotos: helpers puros."""
import io
import json
import logging
import math
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from PIL import Image, ImageOps
from sqlalchemy.exc import IntegrityError

from app import crud, llm
from app.formatting import MONTHS_PT, format_brl, month_name, parse_money
from app.llm import LLMConfig, LLMError
from app.models import VariableExpense
from app.schemas import DraftExpense, PhotoExtraction, variable_expense_problem

logger = logging.getLogger(__name__)

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
    if value.strip().isascii() and key.isdigit() and len(key) <= 2:
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
    if isinstance(value, str):
        value = parse_money(value)
    if not isinstance(value, (int, float)):
        return None
    try:
        result = float(value)
    except OverflowError:
        return None
    return result if math.isfinite(result) else None


def _day(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit() and len(value.strip()) <= 2:
        value = int(value.strip())
    elif isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and 1 <= value <= 31:
        return value
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


@dataclass(frozen=True)
class ImportContext:
    paid_by: str
    categories: list[str]
    prompt: str


def build_prompt(categories: list[str], examples: list[tuple[str, str]]) -> str:
    """Instruções em português para a IA ler a página de gastos manuscrita."""
    lines = [
        "Esta foto é uma página manuscrita de gastos do mês. Leia todos os gastos.",
        'Responda SOMENTE com JSON, sem texto extra, neste formato: '
        '{"month": <mês da página>, "items": [{"day": <dia>, "month": <mês>, '
        '"place": <local>, "note": <texto ou null>, "value": <valor>, '
        '"section": "cartao" ou "pix", "category_name": <grupo>}]}',
        '"section" é "cartao" para gastos no cartão e "pix" para gastos no Pix.',
        "A página tem duas colunas, Cartão e Pix: leia as duas, linha por linha.",
        "O mês está no título da página; cada linha começa com dia/mês.",
        'Os valores são escritos com vírgula e sempre têm dois decimais (ex.: 12,34). '
        'Escreva "value" como número com ponto decimal (ex.: 12.34), sem R$; '
        "não troque nem omita dígitos.",
        '"place" é o nome do estabelecimento, copiado como está escrito; '
        '"note" é a palavrinha pequena escrita acima ou ao lado do local; use null se não houver.',
        "Grupos disponíveis: " + ", ".join(categories) + ".",
        "O category_name deve ser exatamente um desses grupos.",
    ]
    if examples:
        lines.append("Exemplos de gastos anteriores (local → grupo):")
        lines.extend(f"{place} → {group}" for place, group in examples)
    return "\n".join(lines)


def load_context(db, paid_by: str) -> ImportContext:
    """Grupos e exemplos do histórico do pagador (ou de FAFA, se ele não tiver)."""
    categories = sorted(c.name for c in crud.get_variable_categories(db))
    examples = crud.get_place_category_pairs(db, paid_by) or crud.get_place_category_pairs(db, "FAFA")
    return ImportContext(paid_by=paid_by, categories=categories, prompt=build_prompt(categories, examples))


def _sniff_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    raise PhotoImportError("Arquivo não é uma imagem suportada (use JPG ou PNG).")


def extract_photo(
    data: bytes,
    filename: str,
    ctx: ImportContext,
    model: str,
    config: Optional[LLMConfig] = None,
    today: Optional[date] = None,
    downscale: bool = True,
) -> PhotoExtraction:
    """Lê uma foto com a IA e devolve rascunhos; nunca lança. Sem acesso ao banco."""
    try:
        if len(data) > MAX_PHOTO_BYTES:
            raise PhotoImportError("Foto muito grande (máx. 20 MB).")
        if downscale:
            image, mime = prepare_image(data)
        else:
            image, mime = data, _sniff_mime(data)
        text = llm.read_image(config or llm.llm_config(), model, ctx.prompt, image, mime)
        reply = parse_reply(text)
        month, rows = rows_from_reply(reply, ctx.paid_by, ctx.categories, today or date.today())
        return PhotoExtraction(filename=filename, month=month, rows=rows)
    except (PhotoImportError, LLMError) as exc:
        return PhotoExtraction(filename=filename, error=f"Foto '{filename}': {exc}")
    except Exception:
        logger.exception("Erro inesperado ao ler a foto %s", filename)
        return PhotoExtraction(
            filename=filename, error=f"Foto '{filename}': erro inesperado ao ler a foto."
        )


def _cents(value: float) -> int:
    return round(value * 100)


def mark_duplicates(db, rows: list[DraftExpense], earlier: Sequence[DraftExpense] = ()) -> None:
    """Flags rows that look already registered (database) or repeated in this import.

    Flagged rows start unchecked; nothing is blocked. Rows without month, year or value are skipped.
    """
    seen = {
        (r.day, r.month, r.year, _cents(r.value))
        for r in earlier
        if r.month is not None and r.year is not None and r.value is not None
    }
    for row in rows:
        if row.month is None or row.year is None or row.value is None:
            continue
        cents = _cents(row.value)
        key = (row.day, row.month, row.year, cents)
        reason = None
        for existing in db.query(VariableExpense).filter(
            VariableExpense.paid_by == row.paid_by,
            VariableExpense.month == row.month,
            VariableExpense.year == row.year,
        ):
            if _cents(existing.value) == cents:
                reason = (
                    f"Já existe {format_brl(row.value)} em "
                    f"{month_name(row.month, short=True)}/{row.year} ({existing.place})"
                )
                break
        if reason is None and key in seen:
            reason = "Repetido nesta importação"
        seen.add(key)
        if reason:
            row.possible_duplicate = True
            row.selected = False
            row.duplicate_reason = reason


@dataclass
class SaveSummary:
    count: int
    total: float
    duplicates: int
    saved: bool


def save_drafts(db, drafts: list[DraftExpense], dry_run: bool) -> SaveSummary:
    """Validates every draft, then saves all of them or none. With dry_run nothing is written."""
    items = []
    for i, draft in enumerate(drafts, start=1):
        data = draft.expense_data()
        problem = variable_expense_problem(data)
        if problem:
            raise PhotoImportError(f"Linha {i} ({draft.place or 'sem local'}): {problem}")
        items.append(data)
    summary = SaveSummary(
        count=len(items),
        total=sum(item["value"] for item in items),
        duplicates=sum(1 for d in drafts if d.possible_duplicate),
        saved=False,
    )
    if dry_run:
        return summary
    try:
        crud.create_variable_expenses(db, items)
    except IntegrityError as exc:
        raise PhotoImportError("Não foi possível salvar: grupo ou pessoa inexistente.") from exc
    summary.saved = True
    return summary

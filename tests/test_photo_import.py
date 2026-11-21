import io
from datetime import date

import pytest
from PIL import Image
from sqlalchemy import event

from app.photo_import import (
    PhotoImportError,
    build_notes,
    infer_year,
    match_category,
    parse_month,
    parse_reply,
    prepare_image,
    rows_from_reply,
)

TODAY = date(2026, 11, 21)


def make_image(w, h, fmt="PNG", mode="RGB", orientation=None) -> bytes:
    img = Image.new(mode, (w, h), "white")
    buf = io.BytesIO()
    if orientation is not None:
        exif = Image.Exif()
        exif[0x0112] = orientation
        img.save(buf, format="JPEG", exif=exif.tobytes())
    else:
        img.save(buf, format=fmt)
    return buf.getvalue()


def _size(data: bytes):
    with Image.open(io.BytesIO(data)) as img:
        return img.format, img.size


def test_prepare_image_downscales_long_side_to_1600():
    data, mime = prepare_image(make_image(4000, 3000))
    assert mime == "image/jpeg"
    assert _size(data) == ("JPEG", (1600, 1200))


def test_prepare_image_keeps_small_images():
    data, _ = prepare_image(make_image(800, 600))
    assert _size(data)[1] == (800, 600)


def test_prepare_image_handles_rgba_png():
    data, mime = prepare_image(make_image(100, 50, mode="RGBA"))
    assert mime == "image/jpeg"
    assert _size(data)[0] == "JPEG"


def test_prepare_image_applies_exif_rotation():
    data, _ = prepare_image(make_image(300, 100, orientation=6))
    assert _size(data)[1] == (100, 300)


def test_prepare_image_rejects_non_image():
    with pytest.raises(PhotoImportError, match="imagem"):
        prepare_image(b"not an image")


def test_parse_reply_tolerates_fences_and_prose():
    fenced = '```json\n{"month": "outubro", "items": []}\n```'
    assert parse_reply(fenced) == {"month": "outubro", "items": []}
    prose = 'Claro! {"items": []} Espero ter ajudado.'
    assert parse_reply(prose) == {"items": []}


@pytest.mark.parametrize("text", ["", "sem json", "{quebrado", "[1, 2]"])
def test_parse_reply_rejects_garbage(text):
    with pytest.raises(PhotoImportError, match="JSON"):
        parse_reply(text)


@pytest.mark.parametrize(
    "value, expected",
    [
        (10, 10), ("10", 10), ("outubro", 10), (" Outubro ", 10), ("out", 10),
        ("março", 3), ("marco", 3), (13, None), ("foo", None), (None, None),
    ],
)
def test_parse_month(value, expected):
    assert parse_month(value) == expected


@pytest.mark.parametrize(
    "month, day, expected",
    [(10, 6, 2026), (11, 21, 2026), (11, 22, 2025), (12, 1, 2025),
     (2, 29, 2024), (4, 31, None)],
)
def test_infer_year(month, day, expected):
    assert infer_year(month, day, TODAY) == expected


def test_infer_year_december_page_read_in_january():
    assert infer_year(12, 28, date(2027, 1, 3)) == 2026


@pytest.mark.parametrize(
    "section, note, expected",
    [
        ("cartao", "ventilador", "Cartão - ventilador"),
        ("Cartão", None, "Cartão"),
        ("pix", "  ", "Pix"),
        ("PIX", "meli", "Pix - meli"),
        ("x", "n", "n"),
        (None, None, None),
    ],
)
def test_build_notes(section, note, expected):
    assert build_notes(section, note) == expected


def test_match_category():
    cats = ["Comida", "Outros"]
    assert match_category("comida", cats) == "Comida"
    assert match_category("Mercado", cats) == "Outros"
    assert match_category(None, cats) == "Outros"
    assert match_category("Mercado", ["Comida"]) is None


CATS = ["Comida", "Lazer", "Outros"]


def good_item(**over) -> dict:
    item = {"day": 6, "month": 10, "place": "amazon", "value": 10.0, "section": "pix"}
    item.update(over)
    return item


def test_rows_from_reply_builds_rows():
    reply = {"month": "outubro", "items": [{
        "day": 6, "month": 10, "place": " amazon ", "note": "ventilador", "value": 45.67,
        "section": "cartao", "category_name": "lazer"}]}
    month, rows = rows_from_reply(reply, "FEFE", CATS, TODAY)
    assert month == 10
    row = rows[0]
    assert (row.place, row.day, row.month, row.year) == ("amazon", 6, 10, 2026)
    assert row.value == 45.67
    assert row.notes == "Cartão - ventilador"
    assert row.category_name == "Lazer"
    assert row.paid_by == "FEFE"
    assert row.error is None
    assert row.selected is True


def test_rows_from_reply_accepts_comma_values_and_heading_month():
    reply = {"month": "outubro", "items": [
        {"day": "7", "value": "45,67", "section": "pix", "place": "meli"}]}
    _, rows = rows_from_reply(reply, "FEFE", CATS, TODAY)
    row = rows[0]
    assert row.value == 45.67
    assert row.month == 10
    assert row.notes == "Pix"
    assert row.category_name == "Outros"


@pytest.mark.parametrize("over, message", [
    ({"value": None}, "Valor deve ser maior que zero."),
    ({"day": 31, "month": 4}, "Data inválida."),
    ({"place": ""}, "Preencha o local."),
])
def test_rows_from_reply_flags_invalid_rows_unchecked(over, message):
    _, rows = rows_from_reply({"items": [good_item(**over)]}, "FEFE", CATS, TODAY)
    assert rows[0].error == message
    assert rows[0].selected is False


def test_rows_from_reply_bad_fields_become_none_not_errors():
    items = [good_item(day="abc", value="xyz"), good_item(day=[1], value={"a": 1})]
    _, rows = rows_from_reply({"items": items}, "FEFE", CATS, TODAY)
    assert [r.day for r in rows] == [None, None]
    assert [r.value for r in rows] == [None, None]
    assert all(r.error and not r.selected for r in rows)


def test_rows_from_reply_skips_non_objects():
    _, rows = rows_from_reply({"items": ["lixo", good_item()]}, "FEFE", CATS, TODAY)
    assert len(rows) == 1


def test_rows_from_reply_requires_items_list():
    with pytest.raises(PhotoImportError):
        rows_from_reply({"month": "outubro"}, "FEFE", CATS, TODAY)


def test_rows_from_reply_huge_and_non_finite_numbers_become_none():
    items = [
        good_item(day=10**30, value=10**400),
        good_item(day="9" * 5000),
        good_item(day="²"),
        good_item(value="9" * 5000),
        good_item(value=float("inf")),
        good_item(value="1e999"),
        good_item(value=float("nan")),
    ]
    _, rows = rows_from_reply({"items": items}, "FEFE", CATS, TODAY)
    assert rows[0].day is None and rows[0].value is None and rows[1].day is None and rows[2].day is None
    assert [r.value for r in rows[3:]] == [None, None, None, None]
    assert all(r.error and not r.selected for r in rows)


def test_parse_month_superscript_digit_is_none():
    assert parse_month("²") is None


# ---- Task 5: prompt, contexto e extração por foto ----

from unittest.mock import MagicMock, patch

from app import crud
from app.llm import LLMError
from app.photo_import import (
    MAX_PHOTO_BYTES,
    ImportContext,
    SaveSummary,
    build_prompt,
    extract_photo,
    load_context,
    mark_duplicates,
    save_drafts,
)
from app.models import VariableExpense
from app.schemas import DraftExpense


def _add_expense(db, place, category, paid_by):
    crud.create_variable_expense(db, {
        "place": place, "day": 5, "month": 3, "year": 2025, "value": 10.0,
        "paid_by": paid_by, "category_name": category,
    })


def _seed(db, with_fefe_history=True):
    for name in ("FAFA", "FEFE"):
        crud.create_user(db, name)
    for cat in ("Comida", "Lazer", "Casa", "Taxi"):
        crud.create_variable_category(db, cat)
    for _ in range(3):
        _add_expense(db, "iFood", "Comida", "FAFA")
    _add_expense(db, "Amazon", "Lazer", "FAFA")
    for _ in range(2):
        _add_expense(db, "Amazon", "Casa", "FAFA")
    if with_fefe_history:
        _add_expense(db, "Uber", "Taxi", "FEFE")


def test_get_place_category_pairs_most_used_first_per_payer(db_session):
    _seed(db_session)
    assert crud.get_place_category_pairs(db_session, "FAFA") == [
        ("iFood", "Comida"), ("Amazon", "Casa"), ("Amazon", "Lazer"),
    ]
    assert len(crud.get_place_category_pairs(db_session, "FAFA", limit=1)) == 1
    assert crud.get_place_category_pairs(db_session, "FEFE") == [("Uber", "Taxi")]


def test_build_prompt_lists_groups_examples_and_keys():
    prompt = build_prompt(["Comida", "Lazer"], [("iFood", "Comida")])
    for text in ("Comida", "Lazer", "iFood → Comida", "cartao", "pix", "category_name", "JSON"):
        assert text in prompt
    assert "→" not in build_prompt(["Comida", "Lazer"], [])


def test_load_context_uses_fafa_history_when_payer_has_none(db_session):
    _seed(db_session, with_fefe_history=False)
    ctx = load_context(db_session, "FEFE")
    assert ctx.paid_by == "FEFE"
    assert ctx.categories == ["Casa", "Comida", "Lazer", "Taxi"]
    assert "iFood" in ctx.prompt


CTX = ImportContext(paid_by="FEFE", categories=["Comida", "Lazer"], prompt="PROMPT")
REPLY = """```json
{"month": "outubro", "items": [
 {"day": 3, "place": "iFood", "value": 25.5, "section": "cartao", "category_name": "Comida"},
 {"day": 4, "place": "Cinema", "value": "40.00", "section": "pix", "category_name": "Lazer"}]}
```"""


def test_extract_photo_returns_rows():
    with patch("app.llm.read_image", return_value=REPLY) as read:
        result = extract_photo(make_image(100, 100), "p1.png", CTX, "m", config=MagicMock(), today=TODAY)
    assert result.error is None
    assert len(result.rows) == 2
    assert result.month == 10
    args = read.call_args.args
    assert isinstance(args[3], bytes)
    assert args[2] == "PROMPT"
    assert args[4] == "image/jpeg"


def test_extract_photo_without_downscale_sniffs_mime():
    with patch("app.llm.read_image", return_value=REPLY) as read:
        result = extract_photo(make_image(10, 10), "p1.png", CTX, "m", config=MagicMock(),
                               today=TODAY, downscale=False)
    assert result.error is None
    assert read.call_args.args[4] == "image/png"


@pytest.mark.parametrize("data,side_effect,reply,expected", [
    (make_image(10, 10), LLMError("Servidor fora"), None, "Foto 'p1.png': Servidor fora"),
    (make_image(10, 10), None, "nada", "JSON"),
    (b"xx", None, REPLY, "imagem"),
    (make_image(10, 10), RuntimeError("boom"), None, "erro inesperado"),
])
def test_extract_photo_errors_name_the_photo(data, side_effect, reply, expected):
    with patch("app.llm.read_image", side_effect=side_effect, return_value=reply):
        result = extract_photo(data, "p1.png", CTX, "m", config=MagicMock(), today=TODAY)
    assert result.rows == []
    assert "p1.png" in result.error and expected in result.error
    if side_effect and isinstance(side_effect, LLMError):
        assert result.error == expected


def test_extract_photo_rejects_huge_files():
    with patch("app.llm.read_image") as read:
        result = extract_photo(b"0" * (MAX_PHOTO_BYTES + 1), "p1.png", CTX, "m", config=MagicMock())
    assert "20 MB" in result.error
    read.assert_not_called()


def _draft(place="Mercado", day=25, month=10, year=2026, value=45.67, paid_by="FAFA",
           category="Comida", **kw):
    return DraftExpense(place=place, day=day, month=month, year=year, value=value,
                        paid_by=paid_by, category_name=category, **kw)


def _seed_duplicate(db):
    for name in ("FAFA", "FEFE"):
        crud.create_user(db, name)
    crud.create_variable_category(db, "Comida")
    crud.create_variable_expense(db, {
        "place": "Padaria", "day": 10, "month": 10, "year": 2026, "value": 45.67,
        "paid_by": "FAFA", "category_name": "Comida",
    })


def test_mark_duplicates_flags_same_payer_month_year_and_cents_any_day(db_session):
    _seed_duplicate(db_session)
    dup = _draft()
    others = [_draft(value=45.68), _draft(paid_by="FEFE", day=26), _draft(month=11)]
    mark_duplicates(db_session, [dup, *others])
    assert dup.possible_duplicate and not dup.selected
    assert "R$ 45,67" in dup.duplicate_reason and "Out/2026" in dup.duplicate_reason
    assert "Padaria" in dup.duplicate_reason
    assert not any(r.possible_duplicate for r in others)
    assert all(r.selected for r in others)


def test_mark_duplicates_within_import_flags_only_later_rows(db_session):
    _seed_duplicate(db_session)
    first, second = _draft(day=6, value=45.0), _draft(day=6, value=45.0)
    mark_duplicates(db_session, [first, second])
    assert not first.possible_duplicate
    assert second.possible_duplicate and not second.selected
    assert second.duplicate_reason == "Repetido nesta importação"
    again = _draft(day=6, value=45.0)
    mark_duplicates(db_session, [again], earlier=[first])
    assert again.possible_duplicate
    assert again.duplicate_reason == "Repetido nesta importação"


def test_mark_duplicates_skips_incomplete_rows(db_session):
    _seed_duplicate(db_session)
    rows = [_draft(value=None), _draft(month=None), _draft(year=None)]
    mark_duplicates(db_session, rows)
    assert not any(r.possible_duplicate for r in rows)


def _count(db):
    return db.query(VariableExpense).count()


def test_save_drafts_dry_run_writes_nothing(db_session, monkeypatch):
    _seed_duplicate(db_session)

    def boom(*a, **k):
        raise AssertionError("dry run must not write")

    monkeypatch.setattr(crud, "create_variable_expenses", boom)
    drafts = [_draft(value=10.0), _draft(value=20.5), _draft(possible_duplicate=True)]
    summary = save_drafts(db_session, drafts, dry_run=True)
    assert summary == SaveSummary(count=3, total=pytest.approx(76.17), duplicates=1, saved=False)
    assert _count(db_session) == 1


def test_save_drafts_saves_all_rows(db_session):
    _seed_duplicate(db_session)
    summary = save_drafts(db_session, [_draft(place="A", value=10.0, notes="Pix"),
                                       _draft(place="B", value=20.0)], dry_run=False)
    assert summary.saved and summary.count == 2 and summary.total == pytest.approx(30.0)
    rows = db_session.query(VariableExpense).filter(VariableExpense.place.in_(["A", "B"])).all()
    assert {(r.place, r.value, r.paid_by, r.category_name, r.notes) for r in rows} == {
        ("A", 10.0, "FAFA", "Comida", "Pix"), ("B", 20.0, "FAFA", "Comida", None)}


def test_save_drafts_is_all_or_nothing(db_session):
    _seed_duplicate(db_session)
    with pytest.raises(PhotoImportError, match="Linha 2"):
        save_drafts(db_session, [_draft(), _draft(value=None)], dry_run=False)
    assert _count(db_session) == 1


def test_save_drafts_unknown_category_rolls_back(db_session):
    _seed_duplicate(db_session)
    # The shared test engine does not enforce foreign keys like the app's engine does.
    engine = db_session.get_bind()
    event.listen(engine, "connect", lambda conn, _rec: conn.execute("PRAGMA foreign_keys=ON"))
    db_session.close()
    engine.dispose()
    with pytest.raises(PhotoImportError):
        save_drafts(db_session, [_draft(), _draft(category="Inexistente")], dry_run=False)
    assert _count(db_session) == 1
    save_drafts(db_session, [_draft(place="Depois")], dry_run=False)
    assert _count(db_session) == 2


def test_number_rounds_to_two_decimals():
    from app.photo_import import _number

    assert _number(10.123456) == 10.12
    assert _number("3,456") == 3.46


def test_cents_never_raises_and_duplicates_skip_unconvertible_rows(db_session):
    from app.photo_import import _cents, mark_duplicates
    from app.schemas import DraftExpense

    assert _cents(1e308) is None
    row = DraftExpense(place="x", day=1, month=1, year=2020, value=1e308, paid_by="FAFA", category_name="Outros")
    mark_duplicates(db_session, [row], earlier=[row])
    assert row.possible_duplicate is False

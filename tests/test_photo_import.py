import io
from datetime import date

import pytest
from PIL import Image

from app.photo_import import (
    PhotoImportError,
    build_notes,
    infer_year,
    match_category,
    parse_month,
    parse_reply,
    prepare_image,
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
        ("cartao", "abafador", "Cartão - abafador"),
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


from app.photo_import import rows_from_reply

CATS = ["Comida", "Lazer", "Outros"]


def good_item(**over) -> dict:
    item = {"day": 6, "month": 10, "place": "amazon", "value": 10.0, "section": "pix"}
    item.update(over)
    return item


def test_rows_from_reply_builds_rows():
    reply = {"month": "outubro", "items": [{
        "day": 6, "month": 10, "place": " amazon ", "note": "abafador", "value": 102.9,
        "section": "cartao", "category_name": "lazer"}]}
    month, rows = rows_from_reply(reply, "FEFE", CATS, TODAY)
    assert month == 10
    row = rows[0]
    assert (row.place, row.day, row.month, row.year) == ("amazon", 6, 10, 2026)
    assert row.value == 102.9
    assert row.notes == "Cartão - abafador"
    assert row.category_name == "Lazer"
    assert row.paid_by == "FEFE"
    assert row.error is None
    assert row.selected is True


def test_rows_from_reply_accepts_comma_values_and_heading_month():
    reply = {"month": "outubro", "items": [
        {"day": "7", "value": "102,90", "section": "pix", "place": "meli"}]}
    _, rows = rows_from_reply(reply, "FEFE", CATS, TODAY)
    row = rows[0]
    assert row.value == 102.9
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

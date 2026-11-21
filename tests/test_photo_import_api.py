import io
from datetime import date

import pytest
from PIL import Image

from app import llm
from app.llm import LLMError
from app.photo_import import infer_year

YEAR = infer_year(1, 6, date.today())


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return buf.getvalue()


def _reply(*values):
    items = ",".join(
        f'{{"place": "Loja {i}", "day": 6, "month": 1, "value": {v}, "category_name": "Outros"}}'
        for i, v in enumerate(values)
    )
    return f'{{"month": 1, "items": [{items}]}}'


def _files(*names):
    return [("files", (n, _png(), "image/png")) for n in names]


def test_extract_returns_draft_rows_and_saves_nothing(client, monkeypatch):
    monkeypatch.setattr("app.llm.read_image", lambda *a, **k: _reply(10.5, 20))
    resp = client.post("/api/variable-expenses/extract", files=_files("a.png"), data={"paid_by": "FEFE"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1 and body[0]["filename"] == "a.png"
    assert len(body[0]["rows"]) == 2
    for row in body[0]["rows"]:
        assert row["paid_by"] == "FEFE"
        assert row["possible_duplicate"] is False
    assert client.get("/api/variable-expenses/").json() == []


def test_extract_flags_existing_duplicate(client, monkeypatch):
    saved = client.post("/api/variable-expense/", json={
        "place": "Padaria", "day": 2, "month": 1, "year": YEAR, "value": 10.5,
        "paid_by": "FEFE", "category_name": "Outros",
    })
    assert saved.status_code == 200
    monkeypatch.setattr("app.llm.read_image", lambda *a, **k: _reply(10.5))
    resp = client.post("/api/variable-expenses/extract", files=_files("a.png"), data={"paid_by": "FEFE"})
    row = resp.json()[0]["rows"][0]
    assert row["possible_duplicate"] is True
    assert row["selected"] is False


def test_extract_continues_after_a_failing_photo(client, monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise LLMError("fora do ar")
        return _reply(5)

    monkeypatch.setattr("app.llm.read_image", fake)
    resp = client.post(
        "/api/variable-expenses/extract", files=_files("um.png", "dois.png"), data={"paid_by": "FAFA"}
    )
    first, second = resp.json()
    assert "um.png" in first["error"]
    assert second["error"] is None and len(second["rows"]) == 1


def test_extract_passes_chosen_model(client, monkeypatch):
    models = []

    def fake(config, model, *args, **kwargs):
        models.append(model)
        return _reply(5)

    monkeypatch.setattr("app.llm.read_image", fake)
    client.post("/api/variable-expenses/extract", files=_files("a.png"), data={"paid_by": "FAFA", "model": "outro"})
    client.post("/api/variable-expenses/extract", files=_files("a.png"), data={"paid_by": "FAFA"})
    assert models == ["outro", llm.llm_config().model]


def test_extract_flags_repeats_across_photos(client, monkeypatch):
    monkeypatch.setattr("app.llm.read_image", lambda *a, **k: _reply(7))
    resp = client.post(
        "/api/variable-expenses/extract", files=_files("a.png", "b.png"), data={"paid_by": "FAFA"}
    )
    first, second = resp.json()
    assert first["rows"][0]["possible_duplicate"] is False
    assert second["rows"][0]["possible_duplicate"] is True


def test_extract_rejects_bad_payer_and_missing_files(client, monkeypatch):
    monkeypatch.setattr("app.llm.read_image", lambda *a, **k: pytest.fail("must not be called"))
    assert client.post("/api/variable-expenses/extract", files=_files("a.png"), data={"paid_by": "X"}).status_code == 422
    assert client.post("/api/variable-expenses/extract", data={"paid_by": "FAFA"}).status_code == 422

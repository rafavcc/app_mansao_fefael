import base64
import json
from urllib.error import HTTPError, URLError

import pytest

from app import llm
from app.llm import LLMConfig, LLMError, ModelInfo


class _Resp:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(payload_or_exc, calls):
    def _open(request, timeout):
        calls.append((request, timeout))
        if isinstance(payload_or_exc, BaseException):
            raise payload_or_exc
        return _Resp(json.dumps(payload_or_exc).encode())

    return _open


def cfg(key="k"):
    return LLMConfig(base_url="http://h:1/v1", api_key=key, model="m")


OK = {"choices": [{"message": {"content": "hello"}}]}


def test_llm_config_defaults_and_env(monkeypatch):
    for v in ("CASA_LLM_BASE_URL", "CASA_LLM_API_KEY", "CASA_LLM_MODEL"):
        monkeypatch.delenv(v, raising=False)
    c = llm.llm_config()
    assert c.base_url == llm.DEFAULT_BASE_URL
    assert c.model == llm.DEFAULT_MODEL
    assert c.api_key == ""
    monkeypatch.setenv("CASA_LLM_BASE_URL", "http://h:1/v1/")
    assert llm.llm_config().base_url == "http://h:1/v1"


def test_read_image_sends_openai_compatible_request(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "urlopen", fake_urlopen(OK, calls))
    img = b"\x01\x02img"
    assert llm.read_image(cfg(), "mod", "olá", img, "image/jpeg") == "hello"
    req, timeout = calls[0]
    assert req.full_url.endswith("/chat/completions")
    assert req.get_header("Authorization") == "Bearer k"
    body = json.loads(req.data)
    assert body["model"] == "mod"
    assert body["temperature"] == 0
    assert body["stream"] is False
    content = body["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "olá"}
    url = content[1]["image_url"]["url"]
    prefix = "data:image/jpeg;base64,"
    assert url.startswith(prefix)
    assert base64.b64decode(url[len(prefix):]) == img
    assert timeout == 600.0


def test_read_image_omits_authorization_without_key(monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "urlopen", fake_urlopen(OK, calls))
    llm.read_image(cfg(""), "m", "p", b"x", "image/png")
    assert calls[0][0].get_header("Authorization") is None


@pytest.mark.parametrize(
    "exc,expected",
    [
        (URLError("x"), "Não foi possível conectar"),
        (URLError(TimeoutError()), "não respondeu a tempo"),
        (TimeoutError(), "não respondeu a tempo"),
        (HTTPError("u", 401, "no", {}, None), "CASA_LLM_API_KEY"),
        (HTTPError("u", 500, "err", {}, __import__("io").BytesIO(b"boom")), "boom"),
        ({"x": 1}, "Resposta inesperada"),
    ],
)
def test_read_image_errors_are_portuguese(monkeypatch, exc, expected):
    monkeypatch.setattr(llm, "urlopen", fake_urlopen(exc, []))
    with pytest.raises(LLMError) as e:
        llm.read_image(cfg(), "m", "p", b"x", "image/jpeg")
    assert expected in str(e.value)


def test_http_500_message_has_code(monkeypatch):
    import io

    exc = HTTPError("u", 500, "err", {}, io.BytesIO(b"boom"))
    monkeypatch.setattr(llm, "urlopen", fake_urlopen(exc, []))
    with pytest.raises(LLMError, match="500"):
        llm.read_image(cfg(), "m", "p", b"x", "image/jpeg")


def test_list_models_reads_loaded_flag_and_status(monkeypatch):
    data = {"data": [
        {"id": "a", "loaded": True},
        {"id": "b", "status": {"value": "unloaded"}},
    ]}
    monkeypatch.setattr(llm, "urlopen", fake_urlopen(data, []))
    assert llm.list_models(cfg()) == [ModelInfo("a", True), ModelInfo("b", False)]


def test_available_models_puts_default_first_and_falls_back(monkeypatch):
    c = cfg()
    data = {"data": [{"id": "b"}, {"id": "m", "loaded": True}]}
    monkeypatch.setattr(llm, "urlopen", fake_urlopen(data, []))
    got = llm.available_models(c)
    assert [i.id for i in got] == ["m", "b"]
    monkeypatch.setattr(llm, "urlopen", fake_urlopen({"data": [{"id": "b"}]}, []))
    assert llm.available_models(c) == [ModelInfo("m", None), ModelInfo("b", None)]
    monkeypatch.setattr(llm, "urlopen", fake_urlopen(URLError("x"), []))
    assert llm.available_models(c) == [ModelInfo("m", None)]


def test_model_label():
    assert llm.model_label(ModelInfo("a", True)) == "a"
    assert llm.model_label(ModelInfo("b", False)) == "b (não carregado)"
    assert llm.model_label(ModelInfo("c", None)) == "c"

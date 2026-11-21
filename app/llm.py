"""Cliente do servidor de IA local (API compatível com OpenAI), só com stdlib."""
import base64
import json
import os
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://192.168.0.33:8889/v1"
DEFAULT_MODEL = "unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL"
REQUEST_TIMEOUT_S = 600.0
MODELS_TIMEOUT_S = 10.0


class LLMError(Exception):
    """Mensagem em português, exibida ao usuário como está."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = REQUEST_TIMEOUT_S


@dataclass(frozen=True)
class ModelInfo:
    id: str
    loaded: Optional[bool]  # None = desconhecido


def llm_config() -> LLMConfig:
    base_url = os.environ.get("CASA_LLM_BASE_URL") or DEFAULT_BASE_URL
    return LLMConfig(
        base_url=base_url.rstrip("/"),
        api_key=os.environ.get("CASA_LLM_API_KEY", ""),
        model=os.environ.get("CASA_LLM_MODEL") or DEFAULT_MODEL,
    )


def _request(config: LLMConfig, path: str, timeout: float, body: Optional[dict] = None) -> dict:
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    req = Request(config.base_url + path, data=data, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        if e.code in (401, 403):
            raise LLMError("Chave da API recusada pelo servidor de IA (CASA_LLM_API_KEY).") from e
        try:
            text = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            text = ""
        raise LLMError(f"O servidor de IA respondeu com erro {e.code}: {text}") from e
    except (TimeoutError, socket.timeout) as e:
        raise LLMError("O servidor de IA não respondeu a tempo.") from e
    except URLError as e:
        if isinstance(e.reason, (TimeoutError, socket.timeout)):
            raise LLMError("O servidor de IA não respondeu a tempo.") from e
        raise LLMError(f"Não foi possível conectar ao servidor de IA em {config.base_url}.") from e
    except json.JSONDecodeError as e:
        raise LLMError("Resposta inesperada do servidor de IA.") from e
    except OSError as e:
        raise LLMError(f"Não foi possível conectar ao servidor de IA em {config.base_url}.") from e


def list_models(config: LLMConfig) -> list[ModelInfo]:
    payload = _request(config, "/models", MODELS_TIMEOUT_S)
    try:
        items = payload["data"]
        models = []
        for item in items:
            loaded = item.get("loaded")
            if not isinstance(loaded, bool):
                status = item.get("status")
                loaded = status.get("value") == "loaded" if isinstance(status, dict) else None
            models.append(ModelInfo(str(item["id"]), loaded))
        return models
    except (KeyError, TypeError, AttributeError) as e:
        raise LLMError("Resposta inesperada do servidor de IA.") from e


def available_models(config: LLMConfig) -> list[ModelInfo]:
    try:
        listed = list_models(config)
    except LLMError:
        return [ModelInfo(config.model, None)]
    default = next((m for m in listed if m.id == config.model), ModelInfo(config.model, None))
    return [default] + [m for m in listed if m.id != config.model]


def model_label(info: ModelInfo) -> str:
    return info.id + (" (não carregado)" if info.loaded is False else "")


def read_image(config: LLMConfig, model: str, prompt: str, image: bytes, mime: str) -> str:
    data_url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
    body = {
        "model": model,
        "temperature": 0,
        "stream": False,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
    }
    payload = _request(config, "/chat/completions", config.timeout, body)
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError("Resposta inesperada do servidor de IA.") from e
    if not isinstance(content, str):
        raise LLMError("Resposta inesperada do servidor de IA.")
    return content

# Photo import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read handwritten monthly expense pages from photos with a local vision LLM, show the rows in an editable review table with duplicate warnings, and save the selected ones as variable expenses (with a dry-run mode), plus an HTTP endpoint that returns the draft rows without saving.

**Architecture:** `app/env.py` loads `.env`; `app/llm.py` is a tiny stdlib (`urllib`) client for the OpenAI-compatible Unsloth Studio server (list models, one chat call with one image). `app/photo_import.py` holds everything else that is not UI: image downscaling, prompt, tolerant reply parsing, year inference, notes, validation, duplicate check and the dry-run-aware save. The endpoint in `app/main.py` and the NiceGUI page `app/pages/photo_import.py` are thin layers over it.

**Tech Stack:** Python 3.10+, FastAPI, NiceGUI 3.x, SQLAlchemy, SQLite, Pillow (new), python-multipart (new), pytest.

**Spec:** `docs/superpowers/specs/2026-11-21-photo-import-design.md`

## Global Constraints

- LLM config from environment: `CASA_LLM_BASE_URL` (default `http://192.168.0.33:8889/v1`), `CASA_LLM_API_KEY` (default empty), `CASA_LLM_MODEL` (default `unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL`). `.env` at the repo root is loaded at startup; real environment variables win over `.env`.
- The API key never lands in git: not in code, tests, docs, `.env.example` (placeholder `sk-unsloth-...`) or commit messages. `.env` is already in `.gitignore`; do not create or edit `.env` (the orchestrator does that).
- No `openai` dependency, no `python-dotenv`: stdlib `urllib` for HTTP, a ~20-line loader for `.env`. New dependencies: `Pillow>=10.0` and `python-multipart>=0.0.9` in `requirements.txt` only (CI installs it).
- Chat requests: non-streaming, `temperature` 0, image sent as a `data:<mime>;base64,...` `image_url` content part after one `text` part. Timeout 600 s per photo; model list timeout 10 s.
- Photos are never stored: bytes live in memory only until read, then are dropped. The example photo in the session scratchpad is personal data: never copy it into the repo, tests or docs.
- Variable groups come from the database (`crud.get_variable_categories`); a group the LLM invents becomes `Outros`.
- Year rule: the latest year for which that (month, day) is not after today. Notas: `"Cartão"` or `"Pix"`, plus `" - <note>"` when a note was read. `paid_by` = the payer the user picked, for every row.
- Possible duplicate (DB): an existing variable expense with the same `paid_by`, month, year and value to the cent, any day. Possible duplicate (same import): same day, month, year and value as an earlier row of the same import (across photos); only the later rows are flagged. Flagged rows start unchecked; never block.
- Nothing is written to the database without the user pressing "Salvar selecionados"; with dry run on, nothing is written ever, enforced inside `save_drafts`, not only in the UI. Dry-run switch defaults to on.
- Automated tests never call the real LLM server (patch `app.llm.read_image` / `app.llm.urlopen`) and never touch the real `casa.db` (conftest sandbox). Run with `venv/bin/python -m pytest`.
- All UI and error text in Portuguese, matching existing pages; money with `format_brl`; months with `month_name`.
- Commit messages: conventional commits, ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Work on branch `feature/photo-import`; nothing is pushed or merged.

## Review Focus

- iPhone photos: EXIF-rotated JPEGs must reach the LLM upright; a format Pillow cannot open (HEIC, PDF, garbage) must give a per-photo message, not a crash. Tested in Task 3 (`test_prepare_image_applies_exif_rotation`, `test_prepare_image_rejects_non_image`) and on a phone in Task 9.
- Sloppy LLM replies: JSON inside fences or prose, values as strings with comma (`"102,90"`), missing row month, a group outside the list, a row that is not an object. Tested in Tasks 3 and 4.
- Server down, slow, wrong key, or model not loaded: a Portuguese message naming the photo, the other photos still processed, page stays usable. Tested in Tasks 2, 5 and 7; unloaded-model behaviour measured in Task 8.
- Year boundary and impossible dates: December page read in January → previous year; `29/2` → latest leap year; `31/4` → row flagged "Data inválida." and unchecked. Tested in Tasks 3 and 4.
- Saving twice or with one bad row: a save is all-or-nothing, dry run never writes, and the page clears the saved rows so a second click cannot duplicate them. Tested in Task 6; double click checked manually in Task 9.

---

### Task 1: Dependencies and `.env` loading

**Files:**
- Modify: `requirements.txt` (add `Pillow>=10.0`, `python-multipart>=0.0.9`)
- Create: `.env.example`
- Create: `app/env.py`
- Modify: `app/main.py` (call the loader before `from app.database import ...`)
- Test: `tests/test_env.py`

**Interfaces:**
- Produces: `app.env.load_env_file(path: Path = BASE_DIR / ".env") -> None` where `BASE_DIR` is the repo root (`Path(__file__).resolve().parent.parent`). Lines `KEY=VALUE`; blank lines and lines starting with `#` ignored; optional `export ` prefix; surrounding single or double quotes stripped from the value; whitespace around key and value stripped; uses `os.environ.setdefault` (real env wins); missing file is a no-op.

- [ ] **Step 1: Install the new dependencies.** Add the two lines to `requirements.txt`, then `venv/bin/pip install "Pillow>=10.0" "python-multipart>=0.0.9"`. Expected: `venv/bin/python -c "import PIL, multipart"` exits 0.
- [ ] **Step 2: Write `.env.example`** with exactly these keys and a comment line saying to copy it to `.env`:
  ```
  CASA_LLM_BASE_URL=http://192.168.0.33:8889/v1
  CASA_LLM_API_KEY=sk-unsloth-...
  CASA_LLM_MODEL=unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL
  ```
- [ ] **Step 3: Write failing tests in `tests/test_env.py`** (use `tmp_path` and `monkeypatch.delenv(..., raising=False)` for every key used):
  - `test_loads_values_ignoring_comments_and_blank_lines`: file with `# c`, blank line, `CASA_X=1`, `export CASA_Y = two ` → `os.environ["CASA_X"] == "1"`, `os.environ["CASA_Y"] == "two"`.
  - `test_strips_quotes`: `CASA_Q="a b"` and `CASA_R='c'` → `"a b"` and `"c"`.
  - `test_real_environment_wins`: `monkeypatch.setenv("CASA_X", "env")`, file `CASA_X=file` → stays `"env"`.
  - `test_missing_file_is_ignored`: `load_env_file(tmp_path / "nope")` does not raise.
  - `test_value_may_contain_equals`: `CASA_K=a=b` → `"a=b"`.
- [ ] **Step 4: Run** `venv/bin/python -m pytest tests/test_env.py -q`. Expected: FAIL (`No module named 'app.env'`).
- [ ] **Step 5: Implement `load_env_file`** in `app/env.py`, and in `app/main.py` add `from app.env import load_env_file` + `load_env_file()` above `from app.database import ...` (comment: so `.env` can also set `CASA_DB_PATH` / `CASA_STORAGE_SECRET`).
- [ ] **Step 6: Run** `venv/bin/python -m pytest tests -q`. Expected: all pass.
- [ ] **Step 7: Commit** `feat(photo-import): load .env at startup and add Pillow and python-multipart`. Check `git diff --cached` contains no `sk-unsloth-` followed by hex.

---

### Task 2: LLM client

**Files:**
- Create: `app/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (reads `os.environ` at call time).
- Produces in `app/llm.py` (module does `from urllib.request import Request, urlopen` so tests patch `app.llm.urlopen`):
  - `DEFAULT_BASE_URL = "http://192.168.0.33:8889/v1"`, `DEFAULT_MODEL = "unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL"`, `REQUEST_TIMEOUT_S = 600.0`, `MODELS_TIMEOUT_S = 10.0`
  - `class LLMError(Exception)` — message is Portuguese and shown to the user as is.
  - `@dataclass(frozen=True) class LLMConfig: base_url: str; api_key: str; model: str; timeout: float = REQUEST_TIMEOUT_S`
  - `llm_config() -> LLMConfig` (`base_url` with trailing `/` removed)
  - `@dataclass(frozen=True) class ModelInfo: id: str; loaded: Optional[bool]` (`None` = unknown)
  - `list_models(config: LLMConfig) -> list[ModelInfo]` — `GET {base_url}/models`; `loaded` = item's `loaded` if it is a bool, else `status.value == "loaded"`; raises `LLMError`.
  - `available_models(config: LLMConfig) -> list[ModelInfo]` — never raises: default model first (prepended as `ModelInfo(config.model, None)` if the server does not list it), the rest in server order; on `LLMError` returns `[ModelInfo(config.model, None)]`.
  - `model_label(info: ModelInfo) -> str` — `info.id`, plus `" (não carregado)"` when `loaded is False`.
  - `read_image(config: LLMConfig, model: str, prompt: str, image: bytes, mime: str) -> str` — `POST {base_url}/chat/completions`, returns `choices[0].message.content`.
- Error messages (exact): unreachable / `URLError` → `f"Não foi possível conectar ao servidor de IA em {base_url}."`; timeout (`TimeoutError`/`socket.timeout`) → `"O servidor de IA não respondeu a tempo."`; HTTP 401/403 → `"Chave da API recusada pelo servidor de IA (CASA_LLM_API_KEY)."`; other `HTTPError` → `f"O servidor de IA respondeu com erro {code}: {first 300 chars of body}"`; JSON without `choices[0].message.content` → `"Resposta inesperada do servidor de IA."`. Task 8 may append a hint about unloaded models to the HTTP-error message.

- [ ] **Step 1: Write failing tests in `tests/test_llm.py`.** A helper `fake_urlopen(payload_or_exc, calls: list)` returns a function `(request, timeout) -> context manager with .read()` that records `(request, timeout)`. Tests:
  - `test_llm_config_defaults_and_env`: with the three env vars deleted → defaults and `api_key == ""`; with `CASA_LLM_BASE_URL="http://h:1/v1/"` → `base_url == "http://h:1/v1"`.
  - `test_read_image_sends_openai_compatible_request`: config key `"k"`; returns `"hello"` from `{"choices":[{"message":{"content":"hello"}}]}`; recorded request: URL ends with `/chat/completions`, header `Authorization == "Bearer k"`, body `model` as passed, `temperature == 0`, `stream is False`, `messages[0].content[0] == {"type":"text","text":prompt}`, `content[1]["image_url"]["url"]` starts with `"data:image/jpeg;base64,"` and decodes back to the image bytes; timeout `== 600.0`.
  - `test_read_image_omits_authorization_without_key`.
  - `test_read_image_errors_are_portuguese` (parametrized): `URLError("x")` → message contains `"Não foi possível conectar"`; `TimeoutError()` → `"não respondeu a tempo"`; `HTTPError(..., 401, ...)` → `"CASA_LLM_API_KEY"`; `HTTPError` 500 with body `b"boom"` → contains `"500"` and `"boom"`; payload `{"x":1}` → `"Resposta inesperada"`. All raise `LLMError`.
  - `test_list_models_reads_loaded_flag_and_status`: data `[{"id":"a","loaded":True},{"id":"b","status":{"value":"unloaded"}}]` → `[ModelInfo("a", True), ModelInfo("b", False)]`.
  - `test_available_models_puts_default_first_and_falls_back`: server lists `b` then default → default first; server missing default → `ModelInfo(default, None)` prepended; `URLError` → `[ModelInfo(default, None)]`.
  - `test_model_label`: `"a"`, `"b (não carregado)"`, unknown `None` → plain id.
- [ ] **Step 2: Run** `venv/bin/python -m pytest tests/test_llm.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `app/llm.py` per the Interfaces block. Check `TimeoutError` before `URLError` (and unwrap `URLError.reason` that is a timeout).
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(photo-import): add local LLM client for model list and image reading`.

---

### Task 3: Pure helpers — image, reply parsing, dates, notes, groups

**Files:**
- Create: `app/photo_import.py`
- Test: `tests/test_photo_import.py`

**Interfaces:**
- Produces in `app/photo_import.py`:
  - `class PhotoImportError(ValueError)` (Portuguese message)
  - `MAX_LONG_SIDE = 1600`, `MAX_PHOTO_BYTES = 20 * 1024 * 1024`, `FALLBACK_CATEGORY = "Outros"`
  - `prepare_image(data: bytes) -> tuple[bytes, str]` — Pillow: open, `ImageOps.exif_transpose`, convert to RGB, `thumbnail((1600, 1600))` (never upscales), save JPEG quality 85 → `(bytes, "image/jpeg")`. Unopenable → `PhotoImportError("Arquivo não é uma imagem suportada (use JPG ou PNG).")`.
  - `parse_reply(text: str) -> dict` — strip ``` fences, take the substring from the first `{` to the last `}`, `json.loads`; anything else (no braces, invalid JSON, not a dict) → `PhotoImportError("A resposta da IA não é um JSON válido.")`.
  - `parse_month(value) -> Optional[int]` — int 1–12, digit string, or Portuguese month name / 3-letter abbreviation, case- and accent-insensitive (`"marco"` = `"março"`); otherwise `None`.
  - `infer_year(month: int, day: int, today: date) -> Optional[int]` — first year from `today.year` downward (look back at most 8 years) where `date(y, month, day)` exists and is `<= today`; `None` if none.
  - `build_notes(section: Optional[str], note: Optional[str]) -> Optional[str]` — section normalized case/accent-insensitively: `cartao`/`cartão`/`card` → `"Cartão"`, `pix` → `"Pix"`; blank note ignored; unknown section → the note alone, or `None`.
  - `match_category(name: Optional[str], categories: list[str]) -> Optional[str]` — case-insensitive exact match returns the DB spelling; otherwise `"Outros"` if it is in `categories`, else `None`.

- [ ] **Step 1: Write failing tests in `tests/test_photo_import.py`** (helper `make_image(w, h, fmt="PNG", mode="RGB", orientation=None) -> bytes` using Pillow; for `orientation`, set `exif[0x0112]` and save JPEG with `exif=exif.tobytes()`). `TODAY = date(2026, 11, 21)`.
  - `test_prepare_image_downscales_long_side_to_1600`: 4000×3000 PNG → JPEG bytes, mime `"image/jpeg"`, size `(1600, 1200)`.
  - `test_prepare_image_keeps_small_images` : 800×600 → `(800, 600)`.
  - `test_prepare_image_handles_rgba_png`: RGBA 100×50 → opens as JPEG, no error.
  - `test_prepare_image_applies_exif_rotation`: 300×100 JPEG with orientation 6 → result size `(100, 300)`.
  - `test_prepare_image_rejects_non_image`: `b"not an image"` → `PhotoImportError` with `"imagem"` in the message.
  - `test_parse_reply_tolerates_fences_and_prose`: ```` "```json\n{\"month\": \"outubro\", \"items\": []}\n```" ```` and `'Claro! {"items": []} Espero ter ajudado.'` parse to dicts.
  - `test_parse_reply_rejects_garbage` (parametrized): `""`, `"sem json"`, `"{quebrado"`, `"[1, 2]"`.
  - `test_parse_month` (parametrized): `10→10`, `"10"→10`, `"outubro"→10`, `" Outubro "→10`, `"out"→10`, `"março"→3`, `"marco"→3`, `13→None`, `"foo"→None`, `None→None`.
  - `test_infer_year` (parametrized, `TODAY`): `(10,6)→2026`, `(11,21)→2026`, `(11,22)→2025`, `(12,1)→2025`, `(2,29)→2024`, `(4,31)→None`.
  - `test_infer_year_december_page_read_in_january`: `infer_year(12, 28, date(2027, 1, 3)) == 2026`.
  - `test_build_notes` (parametrized): `("cartao","abafador")→"Cartão - abafador"`, `("Cartão",None)→"Cartão"`, `("pix","  ")→"Pix"`, `("PIX","meli")→"Pix - meli"`, `("x","n")→"n"`, `(None,None)→None`.
  - `test_match_category`: categories `["Comida","Outros"]`: `"comida"→"Comida"`, `"Mercado"→"Outros"`, `None→"Outros"`; categories `["Comida"]`: `"Mercado"→None`.
- [ ] **Step 2: Run** `venv/bin/python -m pytest tests/test_photo_import.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** the helpers. Accent folding with `unicodedata.normalize("NFKD", s)` dropping combining marks; month names from `app.formatting.MONTHS_PT`.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `feat(photo-import): image downscaling, tolerant reply parsing, year and notes rules`.

---

### Task 4: Draft rows and shared validation

**Files:**
- Modify: `app/schemas.py` (add `DraftExpense`, `PhotoExtraction`, `variable_expense_problem`)
- Modify: `app/pages/variable.py` (`ExpenseForm.read` uses `variable_expense_problem`)
- Modify: `app/photo_import.py` (add `rows_from_reply`)
- Test: `tests/test_photo_import.py`, `tests/test_schemas_problem.py`

**Interfaces:**
- Consumes: Task 3 helpers.
- Produces:
  - In `app/schemas.py`:
    - `class DraftExpense(BaseModel)`: `place: str = ""`, `day: Optional[int] = None`, `month: Optional[int] = None`, `year: Optional[int] = None`, `value: Optional[float] = None`, `paid_by: str`, `category_name: Optional[str] = None`, `notes: Optional[str] = None`, `error: Optional[str] = None`, `possible_duplicate: bool = False`, `duplicate_reason: Optional[str] = None`, `selected: bool = True`; method `expense_data(self) -> dict` with exactly the `VariableExpenseCreate` keys (`place` stripped, `notes` stripped or `None`).
    - `class PhotoExtraction(BaseModel)`: `filename: str`, `month: Optional[int] = None`, `rows: list[DraftExpense] = []`, `error: Optional[str] = None`.
    - `variable_expense_problem(data: dict) -> Optional[str]` — first problem, checked in this order with these exact messages: blank place `"Preencha o local."`; any of day/month/year missing or not a real date `"Data inválida."`; future `"A data não pode estar no futuro."`; value missing or `<= 0` `"Valor deve ser maior que zero."`; no category `"Selecione um grupo."`; `paid_by` not in `PAYERS` `"Selecione quem pagou."`; finally `VariableExpenseCreate(**data)` raising `ValidationError` → `"Dados inválidos."`.
  - In `app/photo_import.py`: `rows_from_reply(reply: dict, paid_by: str, categories: list[str], today: date) -> tuple[Optional[int], list[DraftExpense]]` — returns `(parse_month(reply.get("month")), rows)`. Per item (non-dict items skipped): `value` via float if number else `parse_money(str)`; `day` int (digit strings accepted); `month` = `parse_month(item month)` or the heading month; `year = infer_year(...)` when day and month are known; `place` stripped; `notes = build_notes(section, note)`; `category_name = match_category(...)`; `error = variable_expense_problem(row.expense_data())`; `selected = error is None`. `reply["items"]` missing or not a list → `PhotoImportError("A IA não devolveu a lista de gastos.")`.

- [ ] **Step 1: Write failing tests in `tests/test_schemas_problem.py`** (`variable_expense_problem`, today-relative dates built from `date.today()`): one valid dict → `None`; then one case per message above (place `"  "`, day 31 month 4, tomorrow, value 0 and `None`, category `None`, paid_by `"X"`, place of 301 chars → `"Dados inválidos."`).
- [ ] **Step 2: Write failing tests in `tests/test_photo_import.py`** (`TODAY`, `CATS = ["Comida","Lazer","Outros"]`):
  - `test_rows_from_reply_builds_rows`: reply `{"month":"outubro","items":[{"day":6,"month":10,"place":" amazon ","note":"abafador","value":102.9,"section":"cartao","category_name":"lazer"}]}` → month `10`; row `place="amazon"`, `day=6, month=10, year=2026`, `value=102.9`, `notes="Cartão - abafador"`, `category_name="Lazer"`, `paid_by="FEFE"`, `error is None`, `selected is True`.
  - `test_rows_from_reply_accepts_comma_values_and_heading_month`: item `{"day":"7","value":"102,90","section":"pix","place":"meli"}` with heading `"outubro"` → `value == 102.9`, `month == 10`, `notes == "Pix"`, group `"Outros"`.
  - `test_rows_from_reply_flags_invalid_rows_unchecked` (parametrized): value missing → `"Valor deve ser maior que zero."`; day 31 month 4 → `"Data inválida."`; place `""` → `"Preencha o local."`. Each: `selected is False`.
  - `test_rows_from_reply_skips_non_objects`: items `["lixo", {...valid...}]` → one row.
  - `test_rows_from_reply_requires_items_list`: `{"month": "outubro"}` → `PhotoImportError`.
- [ ] **Step 3: Run** `venv/bin/python -m pytest tests/test_schemas_problem.py tests/test_photo_import.py -q`. Expected: FAIL (names missing).
- [ ] **Step 4: Implement** the schemas, `variable_expense_problem`, and `rows_from_reply`. Then change `ExpenseForm.read` in `app/pages/variable.py`: keep the `when is None` → `"Data inválida."` check, build the dict as today, and replace the remaining if/elif chain with `variable_expense_problem(data)` (same messages, same notify).
- [ ] **Step 5: Run** `venv/bin/python -m pytest tests -q` and `TESTING=1 venv/bin/python -c "import app.pages.variable"`. Expected: all pass, import OK.
- [ ] **Step 6: Commit** `feat(photo-import): draft rows from the LLM reply with the manual form's validation`.

---

### Task 5: Prompt, examples and per-photo extraction

**Files:**
- Modify: `app/crud.py` (add `get_place_category_pairs`)
- Modify: `app/photo_import.py` (add `ImportContext`, `build_prompt`, `load_context`, `extract_photo`)
- Test: `tests/test_photo_import.py`

**Interfaces:**
- Consumes: Task 2 `llm.LLMConfig`, `llm.llm_config`, `llm.read_image`, `llm.LLMError`; Tasks 3–4 helpers and schemas.
- Produces:
  - `crud.get_place_category_pairs(db, paid_by: str, limit: int = 30) -> list[tuple[str, str]]` — distinct `(place, category_name)` of that payer's variable expenses, most used first, ties by most recent `id`.
  - `@dataclass(frozen=True) class ImportContext: paid_by: str; categories: list[str]; prompt: str`
  - `build_prompt(categories: list[str], examples: list[tuple[str, str]]) -> str` — Portuguese; asks for JSON only with shape `{"month": ..., "items": [{"day", "month", "place", "note", "value", "section", "category_name"}]}`, `section` `"cartao"` or `"pix"`, values as numbers with a dot, `note` = the small word above the place or `null`; lists every category and says the group must be one of them; when `examples` is non-empty, one line per pair as `"<place> → <group>"`. Exact wording is tuned in Task 8.
  - `load_context(db, paid_by: str) -> ImportContext` — categories sorted by name; examples = pairs for `paid_by`, or for `"FAFA"` when that payer has none.
  - `extract_photo(data: bytes, filename: str, ctx: ImportContext, model: str, config: Optional[LLMConfig] = None, today: Optional[date] = None, downscale: bool = True) -> PhotoExtraction` — no DB access (safe in a worker thread). Size > `MAX_PHOTO_BYTES` → error `"Foto muito grande (máx. 20 MB)."`; `prepare_image` (or the raw bytes with a mime sniffed from the PNG/JPEG magic when `downscale=False`); `llm.read_image(config or llm_config(), model, ctx.prompt, ...)` called as a module attribute (`from app import llm`) so tests patch `app.llm.read_image`; `parse_reply`; `rows_from_reply`. Any `PhotoImportError`/`LLMError` → `PhotoExtraction(filename=filename, error=f"Foto '{filename}': {message}")`; any other exception is logged with `logger.exception` and becomes `f"Foto '{filename}': erro inesperado ao ler a foto."`.

- [ ] **Step 1: Write failing tests** (DB tests use the `db_session` fixture and create users FAFA/FEFE and categories with `crud`):
  - `test_get_place_category_pairs_most_used_first_per_payer`: FAFA has iFood/Comida ×3, Amazon/Lazer ×1, Amazon/Casa ×2; FEFE has Uber/Taxi → FAFA pairs `[("iFood","Comida"),("Amazon","Casa"),("Amazon","Lazer")]`; `limit=1` → one pair.
  - `test_build_prompt_lists_groups_examples_and_keys`: contains every category, `"iFood → Comida"`, `"cartao"`, `"pix"`, `"category_name"`, `"JSON"`; with no examples the arrow does not appear.
  - `test_load_context_uses_fafa_history_when_payer_has_none`: only FAFA expenses → `load_context(db, "FEFE").prompt` contains FAFA's place.
  - `test_extract_photo_returns_rows` : patch `app.llm.read_image` to return a fenced JSON reply with two items; result `error is None`, two rows, `month == 10`; the patched function received `mime == "image/jpeg"` and the context prompt.
  - `test_extract_photo_errors_name_the_photo` (parametrized): `read_image` raising `LLMError("Servidor fora")` → `error == "Foto 'p1.png': Servidor fora"`; returning `"nada"` → error contains `"p1.png"` and `"JSON"`; data `b"xx"` → error contains `"imagem"`; `read_image` raising `RuntimeError` → `"erro inesperado"`.
  - `test_extract_photo_rejects_huge_files`: `b"0" * (MAX_PHOTO_BYTES + 1)` → error contains `"20 MB"`, `read_image` not called.
- [ ] **Step 2: Run** `venv/bin/python -m pytest tests/test_photo_import.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block.
- [ ] **Step 4: Run** `venv/bin/python -m pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(photo-import): prompt with groups and history, per-photo extraction`.

---

### Task 6: Duplicate warning and dry-run-aware save

**Files:**
- Modify: `app/crud.py` (add `create_variable_expenses`)
- Modify: `app/photo_import.py` (add `mark_duplicates`, `SaveSummary`, `save_drafts`)
- Test: `tests/test_photo_import.py`

**Interfaces:**
- Consumes: `DraftExpense`, `variable_expense_problem`, `PhotoImportError`.
- Produces:
  - `crud.create_variable_expenses(db, items: list[dict]) -> list[VariableExpense]` — `add_all`, one commit; on any exception `db.rollback()` and re-raise.
  - `mark_duplicates(db, rows: list[DraftExpense], earlier: Sequence[DraftExpense] = ()) -> None` — mutates rows per the Global Constraints duplicate rules (rows missing month, year or value are skipped; compare `round(value * 100)`). Sets `possible_duplicate=True`, `selected=False` and `duplicate_reason`: DB → `f"Já existe {format_brl(v)} em {month_name(m, short=True)}/{y} ({existing.place})"`; same import → `"Repetido nesta importação"`. `earlier` are rows of previous photos of the same import.
  - `@dataclass class SaveSummary: count: int; total: float; duplicates: int; saved: bool`
  - `save_drafts(db, drafts: list[DraftExpense], dry_run: bool) -> SaveSummary` — validates every draft's `expense_data()` with `variable_expense_problem` first; the first problem raises `PhotoImportError(f"Linha {i} ({place or 'sem local'}): {problem}")` (1-based) and nothing is written. `dry_run=True` returns the summary with `saved=False` without calling any write. Otherwise `crud.create_variable_expenses`; `IntegrityError` → `PhotoImportError("Não foi possível salvar: grupo ou pessoa inexistente.")`. `duplicates` counts drafts with `possible_duplicate`.

- [ ] **Step 1: Write failing tests:**
  - `test_mark_duplicates_flags_same_payer_month_year_and_cents_any_day`: existing FAFA expense 10/10/2026 R$ 102,90 → draft FAFA 25/10/2026 102.90 flagged, unchecked, reason contains `"R$ 102,90"` and `"Out/2026"`; drafts with 102.91, FEFE, or 11/2026 not flagged.
  - `test_mark_duplicates_within_import_flags_only_later_rows`: two drafts 6/10/2026 R$ 45,00 → first not flagged, second flagged `"Repetido nesta importação"`; a draft matching one in `earlier` is flagged.
  - `test_mark_duplicates_skips_incomplete_rows`: value `None` → not flagged, no exception.
  - `test_save_drafts_dry_run_writes_nothing`: monkeypatch `crud.create_variable_expenses` to raise `AssertionError`; `save_drafts(db, [two valid drafts, one duplicate], dry_run=True)` → `SaveSummary(count=3, total=..., duplicates=1, saved=False)`; `VariableExpense` count unchanged.
  - `test_save_drafts_saves_all_rows`: two valid drafts, `dry_run=False` → `saved=True`, two expenses with the drafts' fields.
  - `test_save_drafts_is_all_or_nothing`: second draft has value `None` → `PhotoImportError` with `"Linha 2"`; zero expenses saved.
  - `test_save_drafts_unknown_category_rolls_back`: category `"Inexistente"` → `PhotoImportError`; zero expenses; the session is still usable afterwards.
- [ ] **Step 2: Run** `venv/bin/python -m pytest tests/test_photo_import.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** per the Interfaces block (one query per draft is fine for 100 rows).
- [ ] **Step 4: Run** `venv/bin/python -m pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(photo-import): duplicate warning and all-or-nothing save with dry run`.

---

### Task 7: Extract endpoint

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_photo_import_api.py`

**Interfaces:**
- Consumes: `load_context`, `extract_photo`, `mark_duplicates`, `PhotoExtraction`, `llm.llm_config`.
- Produces: `POST /api/variable-expenses/extract` (sync `def`, so FastAPI runs it in the thread pool), multipart: `files: list[UploadFile] = File(...)`, `paid_by: str = Form(...)`, `model: Optional[str] = Form(None)` (default `llm_config().model`). `paid_by` not in `PAYERS` → 422. Photos read one after another; each result is passed to `mark_duplicates(db, rows, earlier=<rows of previous photos>)`. Response `list[PhotoExtraction]`, one per file, in upload order. Never saves.

- [ ] **Step 1: Write failing tests in `tests/test_photo_import_api.py`** using the `client` fixture (it already seeds FAFA, FEFE and the seed categories), a tiny PNG made with Pillow, and `monkeypatch.setattr("app.llm.read_image", fake)`. Items use day 6, month 1 so the expected year is `infer_year(1, 6, date.today())`.
  - `test_extract_returns_draft_rows_and_saves_nothing`: two items → 200, one entry with `filename`, two rows with `paid_by == "FEFE"`, `possible_duplicate is False`; `GET /api/variable-expenses/` is `[]`.
  - `test_extract_flags_existing_duplicate`: POST an expense first via `/api/variable-expense/` with the same payer, month, year and value → that row has `possible_duplicate is True` and `selected is False`.
  - `test_extract_continues_after_a_failing_photo`: fake raises `LLMError("fora do ar")` on the first call and returns rows on the second → two entries: first `error` contains the first filename, second has rows.
  - `test_extract_passes_chosen_model`: form `model="outro"` → fake received `"outro"`; without it, received `llm_config().model`.
  - `test_extract_rejects_bad_payer_and_missing_files`: `paid_by="X"` → 422; no files → 422.
- [ ] **Step 2: Run** `venv/bin/python -m pytest tests/test_photo_import_api.py -q`. Expected: FAIL (404).
- [ ] **Step 3: Implement** the endpoint in `app/main.py` next to the other variable-expense routes.
- [ ] **Step 4: Run** `venv/bin/python -m pytest tests -q`. Expected: all pass.
- [ ] **Step 5: Commit** `feat(photo-import): add POST /api/variable-expenses/extract`.

---

### Task 8: Try-out script, prompt tuning, downscaling and unloaded-model check (real server, manual)

**Files:**
- Create: `scripts/try_photo_import.py`
- Modify: `app/photo_import.py` (prompt wording; keep or drop downscaling by default per measurement)
- Modify: `app/llm.py` (unloaded-model hint, only if the check shows it is needed)
- Modify: `docs/GUIA_DO_CODIGO.md` (new section "Importar gastos de fotos" with the findings)

**Interfaces:**
- Consumes: `load_env_file`, `llm_config`, `available_models`, `load_context`, `extract_photo`, `get_session`.
- Produces: CLI `venv/bin/python scripts/try_photo_import.py <photo> [--payer FEFE] [--model ID] [--no-downscale]` — loads `.env`, builds the context from the database pointed to by `CASA_DB_PATH` (read only), runs `extract_photo`, prints elapsed seconds and the rows as a table (date, place, value, group, notes, error). Never writes to the database.

Requires the real `.env` (created by the orchestrator) and the LAN server. The example photo stays at `/tmp/claude-1000/-home-rafavcc-app-mansao-fefael/9bd315ef-b76e-4943-a2f3-b6deeca3f623/images/1.png`; never copy it. Use a copy of `casa.db` in the scratchpad as `CASA_DB_PATH` so FAFA's history feeds the examples. If the server is unreachable, stop and report; do not guess results.

Known ground truth for the example (from the design session): all dates and card/Pix sections right; 8 values, one misread (`102,90` read as `102,00`); places/notes misread such as `meli-tapete` and `abafador`.

- [ ] **Step 1: Write the script** (`argparse`, `time.perf_counter`). Check: `venv/bin/python scripts/try_photo_import.py --help` exits 0.
- [ ] **Step 2: Baseline.** Run with `--no-downscale`, then without. Record per run: seconds, rows read, dates/sections right, values right, groups that look plausible. Expected: both finish under 5 min.
- [ ] **Step 3: Decide downscaling.** Keep `downscale=True` as default if accuracy is equal or better; otherwise make the default `False` (change `extract_photo` default and Task 3 tests' expectations stay valid since `prepare_image` still exists). Note the numbers.
- [ ] **Step 4: Tune `build_prompt`** (at most ~3 iterations): e.g. say values use a comma and have two decimals, the small word above the place is the note, read both columns. Keep the Task 5 test substrings true. Run `venv/bin/python -m pytest tests -q` after each change.
- [ ] **Step 5: Unloaded model.** `curl -s -H "Authorization: Bearer $CASA_LLM_API_KEY" $CASA_LLM_BASE_URL/models` (after `set -a; . ./.env; set +a`) to pick a model with `loaded: false`; run the script with `--model <it>` once. Record what happens (auto-load and how long, or HTTP error and its body). If it fails, append to the other-HTTP-error message in `app/llm.py`: `" (o modelo escolhido pode não estar carregado no Unsloth Studio)"`, with a test in `tests/test_llm.py`. Do not leave an extra model loaded if the Studio UI allows unloading; mention it in the report otherwise.
- [ ] **Step 6: Document** in `docs/GUIA_DO_CODIGO.md`: flow (upload → `extract_photo` → review → `save_drafts`), `.env` keys (placeholder key only), measured timings and accuracy, downscaling decision, unloaded-model behaviour, how to run the script.
- [ ] **Step 7: Commit** `feat(photo-import): try-out script and prompt tuned on a real page`. Check `git diff --cached` has no API key and no image file.

---

### Task 9: "Importar foto" page

**Files:**
- Create: `app/pages/photo_import.py`
- Modify: `app/ui.py` (nav item and route)
- Modify: `app/theme.py` only for a small row-highlight style if needed
- Modify: `README.md` (feature list and `.env` setup lines)

**Interfaces:**
- Consumes: `llm.llm_config`, `llm.available_models`, `llm.model_label`, `load_context`, `extract_photo`, `mark_duplicates`, `save_drafts`, `SaveSummary`, `PhotoImportError`, `DraftExpense`, `variable_expense_problem`, `NativeSelect`, `money_input`, `date_input`, `parse_date_input`, `parse_money`, `format_brl`, `format_number_br`, `month_name`, `PAYER_LABELS`, `page_container`, `card_classes`.
- Produces: `build_photo_import() -> None`; route `/import` titled `"Importar foto"`; `NAV_ITEMS` entry `("import", "Importar", "photo_camera", "/import")` placed after `"variable"`; storage key `MODEL_KEY = "photo_import_model"`.

Behaviour:
- Header "Importar foto". Controls card: "Pago por" toggle (`PAYER_LABELS`, no default; mark `paid_by`); "Modelo" `NativeSelect` (mark `model`) whose options load after render (`ui.timer(0.1, ..., once=True)` + `await run.io_bound(available_models, config)`), labels from `model_label`, value = remembered `app.storage.user[MODEL_KEY]` if still listed, else the default; changing it stores the choice. Switch "Simulação (não salva nada)" on by default (mark `dry_run`). `ui.upload(multiple=True, auto_upload=True)` with `accept="image/*"` and `max_file_size=MAX_PHOTO_BYTES`, collecting `(name, await e.file.read())` in memory (mark `upload`); "Ler fotos" button (mark `read`).
- "Ler fotos": requires payer and at least one photo (`ui.notify` warning otherwise). Disables itself, shows `"Lendo foto i de n…"` with a spinner, builds `load_context` once, and for each photo `await run.io_bound(extract_photo, data, name, ctx, model)`, then `mark_duplicates` (in a short `get_session()`) with the rows of earlier photos, and renders that photo's section immediately. Drops the photo bytes after reading. Re-enables at the end.
- One section card per photo: title `"<Mês> · <n> gastos · <total>"` (month from the extraction, else filename) with "Todos" / "Nenhum" buttons; an extraction error shows as a red card with the message. Each row: checkbox, date (`date_input`, max today), place, value (`money_input`), group (`NativeSelect` of the context categories), notes; edits write back to the `DraftExpense` and re-run `variable_expense_problem` to update its error text. Rows with `error` get a highlighted border and the message; rows with `possible_duplicate` get a "Possível duplicado" badge with `duplicate_reason` as tooltip. Section count/total update when values change.
- "Salvar selecionados" (mark `save`): collects checked rows; none → warning. Calls `save_drafts(db, rows, dry_run=switch.value)`. `PhotoImportError` → negative notify with its message. Dry run → dialog "Simulação: nada foi salvo" with count, `format_brl(total)` and duplicates. Real save → positive notify `"<n> gastos salvos."` and removes the saved rows from the review (sections left empty are removed), so a second click cannot save them again.
- Phone width (~390 px): rows wrap into two lines, no horizontal scroll.

- [ ] **Step 1: Implement** the page and nav per the behaviour above, in small local functions like `app/pages/variable.py`.
- [ ] **Step 2: Import check.** `TESTING=1 venv/bin/python -c "import app.main"` exits 0; `venv/bin/python -m pytest tests -q` passes.
- [ ] **Step 3: Manual verification** (use the `run` skill) with `CASA_DB_PATH` pointing at a scratchpad copy of `casa.db` and the real `.env`, dry run on:
  1. Nav shows "Importar"; the model selector lists the server's models with "(não carregado)" marks; with the server stopped or a wrong `CASA_LLM_BASE_URL` it shows only the default and the page still works.
  2. Upload the example photo as FEFE; progress text appears; the section shows month, count and total; compare rows with the photo.
  3. Edit a value and a group; uncheck a row; "Salvar selecionados" in dry run shows the summary and `sqlite3 <copy> "select count(*) from variable_expenses"` is unchanged.
  4. Upload the same photo twice in one import: the second section's rows are flagged "Repetido nesta importação" and unchecked.
  5. Dry run off: save; count increases by exactly the checked rows; the saved rows disappear; clicking save again warns that nothing is selected. Re-import the photo: rows now flagged as existing duplicates.
  6. A non-image file and a stopped server each give a per-photo red card naming the file while other photos still load.
  7. Phone width ≈390 px: no horizontal scroll. If an iPhone is available, upload a photo straight from the camera roll (EXIF rotation, HEIC conversion by Safari).
  The real `casa.db` is never used in this step.
- [ ] **Step 4: Update `README.md`:** feature "Importar gastos de fotos (IA local)" and the `cp .env.example .env` setup line.
- [ ] **Step 5: Commit** `feat(photo-import): Importar foto page with review table and dry run`.

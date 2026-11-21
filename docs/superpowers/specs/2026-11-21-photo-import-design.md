# Import variable expenses from photos — design

## Why
Fefe keeps her card and Pix expenses in a handwritten notebook, one page per month, filled in after the
month is over. Typing a whole page into "Gastos Variáveis" by hand is slow. Rafa wants to photograph the
page and have a local LLM read it into variable expenses, review them, and save them in one go.

## Goals
- A new page "Importar foto" where the user uploads one or more photos, picks who paid (FAFA or FEFE), and
  gets an editable review table of the expenses read from the photos.
- A new endpoint that does the same reading over HTTP and returns draft rows without saving.
- The LLM reads place, day, month, value, the small note and the section (card or Pix) from the page, and
  infers the group (category).
- Possible duplicates are flagged before saving.
- A dry-run switch so the feature can be tested without writing to the database.

## Non-goals
- AGENT.md / SKILL.md files (Rafa decided to skip them).
- Storing the photos. They are discarded after reading.
- A payment-method field on expenses (card/Pix goes into Notas).
- Detecting re-uploads of the same page beyond the duplicate warning below.
- Moving the app to React (discussed and deferred, separate project).

## Anti-goals
- Nothing is written to the database without the user confirming in the review table.
- In dry-run mode, nothing is written to the database, ever.
- The API key never lands in git.

## What the photos look like
One photo = one month. Example: a notebook page headed with the month name ("outubro"), no year. Two
sections side by side: card purchases (data | despesa | valor) and "Pix" (same columns). Rows look like
`6/10 | amazon (abafador) | 102,90`; the word in small letters above the place is a note. Values use a
comma as decimal separator. There is at most one page per month and it is only uploaded after the month
is over.

## Approaches
1. **One LLM call per photo reads the page and picks the group** (chosen). The prompt carries the group
   list and the payer's past place → group pairs as examples. Simple, one wait per photo.
2. LLM only reads; the app picks the group from history, with a second text-only LLM call for unknown
   places. More predictable as history grows, but more code and a second wait; history is ambiguous
   anyway (Mercado Livre already maps to three groups). Rejected.
3. Bigger model (Qwen3.8-27B). Not a design: covered by the model selector.

## Decisions

### LLM server
- Unsloth Studio, OpenAI-compatible API at `http://192.168.0.33:8889/v1` (LAN, not the Cloudflare tunnel).
- Config in a `.env` file at the repo root (already git-ignored): `CASA_LLM_BASE_URL`, `CASA_LLM_API_KEY`,
  `CASA_LLM_MODEL` (default `unsloth/gemma-4-12b-it-GGUF:UD-Q4_K_XL`). The app loads `.env` at startup;
  real environment variables win over `.env`. Add a `.env.example` with placeholder values (committed).
- Measured: one photo (1600×900 PNG) takes ~50 s with gemma-4-12b. Output is clean JSON. Accuracy on the
  example: all dates and Pix/card right, 7 of 8 values right (102,90 read as 102,00), some places and
  notes misread ("meli-tapete" → "meli - taru", "abafador" → "albatro"). The review table is therefore
  essential.
- Images are sent as base64 `image_url` content parts, `temperature` 0. Photos are downscaled (long side
  ~1600 px, JPEG) before sending; builder measures whether it helps and keeps it if it does not hurt
  accuracy.
- Timeout generous (≥ 5 min per photo). Server unreachable / error / unparseable answer → a clear message
  in Portuguese naming the photo; other photos still proceed; the page stays usable.

### Model selection
- The page fetches `GET {base_url}/models` and shows a selector. Default: `CASA_LLM_MODEL` (gemma-4-12b).
- The server lists both loaded and unloaded models (`status.value`, `loaded`). Unloaded ones are shown
  marked as such ("não carregado"). Builder tests what happens when an unloaded model is requested and
  documents it; if it fails, the error message says so.
- The choice is remembered per browser (NiceGUI `app.storage.user`, like `last_variable_category`).
- If the model list cannot be fetched, the selector falls back to the default model alone.

### Extraction
- One LLM call per photo, photos processed one after another (single local GPU). Progress shown per photo
  ("Lendo foto 2 de 3…"), and the review table fills as each finishes.
- Prompt (Portuguese) asks for JSON only: month name/number from the heading and per row `day`, `month`,
  `place`, `note`, `value`, `section` (`cartao`/`pix`), `category_name`. It includes the exact list of
  variable groups and up to ~30 past place → group pairs for the chosen payer; if that payer has no
  history (FEFE today), use FAFA's. Group must be one of the list; anything else becomes `Outros`.
- Parsing is tolerant: strip ```json fences, take the outermost JSON object.
- **Year**: the latest year for which that (month, day) is not in the future (relative to today).
- **Notas**: `"Cartão"` or `"Pix"`, plus `" - <note>"` when a note was read.
- `paid_by` = the payer chosen by the user, for every row.
- Rows that fail validation (missing value, impossible date) are still shown, highlighted, unchecked.

### Duplicate warning
- A draft row is a possible duplicate when an existing variable expense has the same `paid_by`, same
  month and year, and the same value (to the cent), any day. Also flag duplicates within the same import
  (two identical rows on the page are legitimate, e.g. two iFood orders, so only warn, never block).
- Flagged rows show a badge and start unchecked; the user can check them.

### Review table
- Built for many rows (20–40 per month, 100+ across photos).
- One section per photo/month with its count and total, so the user can compare with the page.
- Every cell editable: date, place, value, group, notes. Checkbox per row; select all/none per section.
- One "Salvar selecionados" button. Validation uses the same rules as the manual form
  (`VariableExpenseCreate`).

### Dry run
- A switch on the page, **on by default** during testing. In dry run, "Salvar selecionados" shows a
  summary of exactly what would be saved (count, total, duplicates) and writes nothing.
- The save path checks dry run on the server side too, not only in the UI.

### Endpoint
- `POST /api/variable-expenses/extract`, multipart: `files` (one or more images), `paid_by`
  (FAFA|FEFE), optional `model`. Returns one entry per photo: draft rows (with `possible_duplicate`) or an
  error. Never saves. Saving over HTTP uses the existing `POST /api/variable-expense/`.
- Requires adding `python-multipart` to requirements.

### Code layout (builder may refine)
- `app/llm.py`: config, list models, call chat completions with images (stdlib `urllib` or `httpx`, no
  `openai` dependency needed).
- `app/photo_import.py`: prompt building, response parsing, year inference, notes, duplicate check
  (pure, no UI).
- `app/pages/photo_import.py` + nav entry "Importar" in `app/ui.py`.
- Tests mock the LLM; no test calls the real server. Tests never touch the real `casa.db`.

## Left to the builder
- Exact prompt wording, tuned against the example photo.
- Downscaling size/format.
- Visual details of the review table, within the existing theme.

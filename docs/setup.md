# Setup

## Requirements
- Python 3.11+
- Node.js 22+
- No local GPU required

## First run
```bash
python scripts/setup.py
npm run dev
```

Frontend: `http://localhost:8080`  
Backend: `http://127.0.0.1:8000/docs`

## Live mode
Copy `.env.example` to `.env` and set `IML_MODE=live`, `IML_API_BASE_URL`, `IML_API_KEY`, `IML_CHEAP_MODEL` and `IML_STRONG_MODEL`. Leave these blank for demo mode.

## Checks
```bash
.venv\Scripts\python.exe -m pytest backend/tests -q
npm run check
.venv\Scripts\python.exe scripts/check_pipeline.py
```

Setup reuses committed router artifacts. Use `python scripts/setup.py --retrain-router`
only when deliberately regenerating them. An incomplete virtual environment with
missing pip is repaired using `ensurepip`.

## Alternate local ports

When another app occupies the defaults, use PowerShell:

```powershell
$env:IML_DEV_WEB_PORT = '8081'
$env:IML_DEV_API_PORT = '8001'
npm run dev
```

Open http://127.0.0.1:8081. Vite forwards API traffic to the selected backend port.
These variables configure the combined developer launcher; `IML_HOST`/`IML_PORT`
alone do not change the launcher's explicit command-line arguments.

`IML_DATABASE_PATH` optionally selects a separate SQLite file. Test runs and the
offline rehearsal use isolated disposable databases. Development state otherwise
lives under ignored `backend/data/runtime/`.

The reference tokenizer may download its vocabulary once. To warm it before an
offline presentation:

```powershell
.venv\Scripts\python.exe -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
```

No answer model is downloaded. If the vocabulary is unavailable, the application
labels the imported whitespace fallback. Only `cl100k_base` is supported by the
current imported token counter; do not interpret `IML_ENCODING` as multi-tokenizer
support.

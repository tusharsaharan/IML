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
```
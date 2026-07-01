
# DocSelector Phase 1 backend

## Spuštění ve Windows CMD / PowerShell

```bat
cd ...path
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs

Backend ukládá stav do `backend/data/docselector_store.json`.

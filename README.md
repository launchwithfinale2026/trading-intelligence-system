# Trading Intelligence System

Personal, human-in-the-loop trading assistant. Watches a curated asset universe, finds
high-probability setups, calculates risk/reward, and sends Telegram alerts for a human to
accept (OPEN) or dismiss (IGNORE). No automated execution.

## Status

Phase 1 (Foundation) complete: backend boots, `/health` endpoint live, DB connection wired,
tests passing. See project task list for remaining phases.

## Backend setup (local dev)

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/health` — expect `{"status":"online"}`.

## Tests

```bash
source backend/venv/bin/activate
pytest
```

## Project structure

```
backend/app/
  main.py            FastAPI entrypoint
  api/                 route modules (auth, users, dashboard, signals)
  core/                config, security, scheduler
  database/            SQLAlchemy engine/session + models
  market/               market data provider interface
  strategies/           signal-generating strategies
  analysis/             scoring / technical analysis
  risk/                 position sizing
  portfolio/             position tracking
  telegram/             bot + command handlers
  feedback/              decision/outcome tracking
frontend/                Next.js dashboard (Phase 12)
tests/                    backend test suite
```

# Trading Intelligence System

Personal, human-in-the-loop trading assistant. Watches a curated asset universe, finds
high-probability setups, calculates risk/reward, and sends Telegram alerts for a human to
accept (OPEN) or dismiss (IGNORE). No automated execution.

## Status

Phases 1–12 complete (foundation through the web dashboard) — backend, Telegram bot,
market scanner, strategy engine, risk engine, position tracking, feedback/performance
tracking, and the Next.js dashboard are all built and tested (136 backend tests, 5
frontend unit tests, full production builds passing). Phase 13 (online deployment) has
its configuration built (Docker, CI, `docs/DEPLOYMENT.md`) but actually deploying
requires human steps — hosting accounts, payment, and creating the Telegram bot via
BotFather. See `docs/ROADMAP.md` for the full phase-by-phase history and
`docs/DECISIONS.md` for why things are built the way they are.

## Backend setup (local dev)

```bash
cd backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
cp ../.env.example ../.env
alembic upgrade head
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/health` — expect `{"status":"online"}`. Interactive API
docs at `http://127.0.0.1:8000/docs`.

To run the Telegram bot (needs `TELEGRAM_BOT_TOKEN` set in `.env` — see
`docs/DEPLOYMENT.md`): `python -m app.telegram.bot`

## Frontend setup (local dev)

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000`. See `frontend/README.md`.

## Tests

```bash
source backend/venv/bin/activate && pytest        # backend
cd frontend && npm run lint && npx tsc --noEmit && npm run test && npm run build  # frontend
```

## Docker (local full-stack)

```bash
docker compose up            # Postgres + backend + frontend
docker compose --profile bot up  # + the Telegram bot process
```

Not verified with an actual `docker build` in this environment (Docker isn't installed
here) — see Decision 18 in `docs/DECISIONS.md`.

## Deploying

See `docs/DEPLOYMENT.md` for the human checklist (hosting providers, env vars, Telegram
bot creation, verification steps).

## Docs

- `docs/ARCHITECTURE.md` — full system architecture, data flow, directory map
- `docs/ROADMAP.md` — every phase, what's built, what's verified
- `docs/DECISIONS.md` — architectural decision log
- `docs/DEPLOYMENT.md` — deployment checklist

## Project structure

```
backend/app/
  main.py              FastAPI entrypoint
  api/                 route modules (auth, users, signals, feedback, portfolio, market)
  core/                config, security, exceptions, scheduler
  database/             models/ (User, Profile, Signal, Decision, Position, TradeResult)
  repositories/, services/   data access + business logic, per entity
  market/               provider interface, yfinance adapter, scanner, universe
  strategies/            momentum, breakout
  analysis/               technical indicators, scoring
  risk/                    position sizing
  telegram/                bot, handlers, alert formatting
  engine/                   scan/alert and position-monitor pipelines
frontend/                 Next.js (App Router) dashboard
tests/                     backend test suite (pytest)
```

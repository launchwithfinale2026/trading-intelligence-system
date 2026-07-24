# Local Development

Everything below was verified by actually running it during the Phase 1
audit (2026-07-24) — not just described. If a step doesn't work as written,
that's a real regression, not a docs gap.

## Quick start (once set up)

```
Terminal 1:
cd backend && venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Terminal 2:
cd frontend && npm run dev

Terminal 3 (optional — only if you want live Telegram alerts):
cd backend && venv/bin/python -m app.telegram.bot
```

Then open http://localhost:3000.

---

## 1. Requirements

- **Python 3.12** (matches `backend/Dockerfile`'s `python:3.12-slim` and CI)
- **Node 22** (matches `frontend/Dockerfile`'s `node:22-slim` and CI)
- No database server to install for local dev — SQLite ships with Python.
  Postgres is only needed for production-parity testing (see
  `docs/DEPLOYMENT_READY_CHECKLIST.md`).

## 2. Installation

From the repo root:

```bash
# Backend
python3.12 -m venv backend/venv
backend/venv/bin/pip install -r requirements.txt   # requirements.txt lives at repo root

# Frontend
cd frontend
npm install
cd ..
```

(A `backend/venv` already exists in this checkout with everything
installed — this step is only needed on a fresh clone or if the venv is
deleted.)

## 3. Environment setup

Two separate `.env` files, one per app half:

```bash
cp .env.example .env                                 # backend, repo root
cp frontend/.env.local.example frontend/.env.local    # frontend
```

Both ship with working local-dev defaults — the app runs with zero edits
to either file. The only variable you'd realistically add by hand is
`TELEGRAM_BOT_TOKEN` in `.env` (optional — see §6 below), obtained from
[@BotFather](https://t.me/BotFather) on Telegram.

**Where `.env` is read from matters less than it used to.** `Settings`
resolves `.env` to an absolute path (repo root) rather than a path relative
to whatever directory a command happens to be run from — so `.env` loads
correctly whether you run backend commands from the repo root or from
`backend/` (the convention this doc uses throughout, matching
`alembic.ini` and `backend/Dockerfile`).

Full variable reference: `.env.example` (has a comment on every line).

## 4. Database initialization

SQLite, zero setup — the database file is created by running migrations,
not by installing anything:

```bash
cd backend
venv/bin/python -m alembic upgrade head
```

This creates `backend/trading.db` and applies all 8 migrations (users,
profiles, signals, decisions, positions, trade_results, telegram_contacts,
telegram_events, risk_policies + seed data, watchlist_symbols). Safe to
re-run — Alembic tracks which migrations already applied.

**Important**: always run this (and every other backend command) with
`backend/` as your working directory. `DATABASE_URL`'s default
(`sqlite:///./trading.db`) is relative to the current directory — running
from the repo root instead would create/look for a *different*, unmigrated
`trading.db` one level up, and you'd hit `no such table: users` the moment
anything touches the database. This bit us once during this audit; see
Troubleshooting below.

## 5. Running migrations (ongoing)

Same command, any time models change:

```bash
cd backend && venv/bin/python -m alembic upgrade head
```

To see migration history: `venv/bin/python -m alembic history`.

## 6. Backend startup

```bash
cd backend
venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"online"}`.

**Telegram bot** (separate long-running process, optional for local dev —
the backend API runs fine without it):

```bash
cd backend
venv/bin/python -m app.telegram.bot
```

Requires `TELEGRAM_BOT_TOKEN` in `.env`; exits immediately with a clear
`RuntimeError` if it's unset, and with `telegram.error.InvalidToken` if the
token is set but wrong/revoked (see Troubleshooting). Without it, the rest
of the app — registration, login, dashboard, watchlist, risk engine — works
normally; you just won't get Telegram alerts or be able to link an account
via `/start`.

## 7. Frontend startup

```bash
cd frontend
npm run dev
```

Opens on http://localhost:3000. Reads `NEXT_PUBLIC_API_URL` from
`frontend/.env.local` (defaults to `http://localhost:8000`, matching §6).

## 8. Testing

**Backend** — run from the **repo root** (not `backend/`) — `pytest.ini`
lives there and points `pythonpath` at `backend/`:

```bash
backend/venv/bin/python -m pytest
```

217 tests as of this audit, all passing, in ~20–25s. For a specific file:
`backend/venv/bin/python -m pytest tests/test_watchlist_api.py -v`.

**Frontend** — run from `frontend/`:

```bash
npm run test        # vitest
npx tsc --noEmit     # typecheck
npm run lint         # eslint
npm run build        # production build
```

## 9. Common troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `sqlalchemy.exc.OperationalError: no such table: users` | Backend command run from the repo root instead of `backend/` — `DATABASE_URL`'s relative sqlite path pointed at a different, unmigrated `trading.db` | `cd backend` before running any backend command (uvicorn, alembic, the bot) |
| `RuntimeError: TELEGRAM_BOT_TOKEN is not set` | `.env` has no token, or you're running the bot process (not just the API) | Only the bot process (`python -m app.telegram.bot`) needs this — the API server doesn't. Get a token from @BotFather and set it in `.env` if you want the bot. |
| `telegram.error.InvalidToken: ... was rejected by the server` | The token in `.env` is malformed, expired, or was revoked/regenerated in @BotFather since you last set it | Message @BotFather → `/mybots` → your bot → API Token, copy it fresh, paste it directly into `.env` (avoid retyping it by hand — a single mistyped character produces exactly this error) |
| Dashboard loads but shows no data / network errors in console | Backend isn't running, or `NEXT_PUBLIC_API_URL` (`frontend/.env.local`) doesn't match the backend's actual host/port | Confirm `curl http://localhost:8000/health` works, confirm the URL matches |
| CORS error in browser console | Frontend origin isn't in the backend's `CORS_ALLOWED_ORIGINS` (`.env`) | Default already includes `http://localhost:3000`; only relevant if you changed the frontend's port |
| `RuntimeError: SECRET_KEY is still the insecure development default while ENVIRONMENT=production` | You set `ENVIRONMENT=production` locally without also setting a real `SECRET_KEY` | This is a deliberate safety check (see `docs/DEPLOYMENT_READY_CHECKLIST.md`) — for local dev, leave `ENVIRONMENT=development` (the default) |
| `alembic.util.exc.CommandError` about multiple heads | Two migrations were created independently without one declaring `down_revision` on the other | Shouldn't happen from normal use — if it does, check `backend/alembic/versions/` for the actual chain with `alembic history` |
| Port 8000 or 3000 already in use | A previous run is still alive | `lsof -ti:8000 \| xargs kill` (or `:3000`) |

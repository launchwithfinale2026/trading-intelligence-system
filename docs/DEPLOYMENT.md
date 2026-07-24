# Deployment

This document is the human checklist for taking the system from "runs on
my laptop" to "accessible remotely," per Phase 13. Nothing in this file was
executed by the autonomous build — creating accounts, spending money, and
issuing credentials are explicitly out of scope for it (see
docs/DECISIONS.md and the end-of-mission report). What *is* done: the
Docker images, `docker-compose.yml`, and CI workflows this file references
all exist in the repo and are ready to use once you've made the choices
below.

Note: Docker itself isn't installed in the environment this was built in,
so the Dockerfiles below are written to standard multi-stage best practice
and reviewed carefully, but **not verified with an actual `docker build`**.
Treat the first real build as the verification step.

---

## 1. Choose hosting (free-tier friendly)

You need three things: backend hosting, frontend hosting, and a Postgres
database. Any combination works since everything is containerized /
standard, but reasonable free-tier-friendly defaults:

| Component | Suggested provider | Why |
|---|---|---|
| Backend (FastAPI, Docker) | Railway, Render, or Fly.io | All have a free/cheap tier, deploy straight from a Dockerfile, and support background workers (for the Telegram bot process) |
| Database (Postgres) | Same provider's managed Postgres (Railway/Render both offer one), or Neon/Supabase free tier | Avoids running your own Postgres; get a `DATABASE_URL` connection string directly |
| Frontend (Next.js) | Vercel | Built by the Next.js team, zero-config for this app, generous free tier |

This is a recommendation, not a requirement — the app has no
provider-specific code (Decision 8's replaceable-provider philosophy
applies to hosting too, informally).

## 2. Provision the database (Supabase)

This app's backend and Telegram bot are **persistent, long-running
processes** (uvicorn + a long-polling bot), not serverless/edge functions —
that fact determines which of Supabase's three connection strings to use.

1. Create a project at [supabase.com](https://supabase.com) (a human,
   credentialed step — account creation is explicitly out of scope for
   automation, see "What's explicitly not automated here" below).
2. In the dashboard: **Project Settings → Database → Connection string**.
   Supabase offers three variants — pick based on your backend host's
   network:

   | Variant | Port | Use when |
   |---|---|---|
   | **Session pooler** (recommended default) | `5432` | Your host has **IPv4-only** egress — true for most free/cheap tiers on Railway, Render, and Fly.io, the hosts this doc recommends in step 1. Supports persistent connections and DDL (so Alembic migrations work through it), unlike the transaction pooler. |
   | Direct connection | `5432` | Your host has **IPv6** egress, or you've paid for Supabase's IPv4 add-on. No pooler overhead. |
   | Transaction pooler | `6543` | Serverless/edge functions with many short-lived connections — **not this app's shape**, and Alembic's DDL/locking can misbehave under transaction-mode pooling. Don't use this one here. |

   If unsure whether your host has IPv6 egress, default to the **session
   pooler** — it works everywhere.

3. Copy the connection string and set it as `DATABASE_URL`. Supabase gives
   you a bare `postgresql://...` (or, from some older flows/other tools,
   `postgres://...`) URL — either works as-is:
   - `postgresql://...` is accepted directly (SQLAlchemy defaults to the
     `psycopg2` driver, which is installed — see `requirements.txt`).
   - A bare `postgres://...` scheme is automatically rewritten to
     `postgresql+psycopg2://...` at startup (`Settings._normalize_postgres_scheme`
     in `backend/app/core/config.py`) — SQLAlchemy 2.x doesn't recognize the
     unprefixed `postgres://` scheme on its own and would otherwise crash
     at `create_engine()` time. You don't need to edit the string by hand
     either way.

   Example (session pooler):
   ```
   DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```
   Example (direct connection, IPv6/IPv4-add-on hosts only):
   ```
   DATABASE_URL=postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres
   ```

4. Migrations run the same way regardless of which variant you picked —
   `alembic upgrade head` (already wired into the Dockerfile's `CMD`, see
   step 4 below) creates all tables from a completely empty database. No
   manual schema setup in the Supabase SQL editor is needed or expected.

## 3. Create the Telegram bot (if not already done)

1. Message [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`,
   follow the prompts.
2. Save the token it gives you — this is `TELEGRAM_BOT_TOKEN`.

## 4. Set backend environment variables

On your backend host, set (see `.env.example` for the full list):

```
DATABASE_URL=postgresql+psycopg2://...          # from step 2
SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(64))">
TELEGRAM_BOT_TOKEN=<from step 3>
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.vercel.app
ENVIRONMENT=production
ENABLE_SCHEDULED_SCANNING=false   # flip to true only when you're ready — see Decision 16
```

Deploy `backend/Dockerfile` (build context = repo root). The container's
`CMD` runs `alembic upgrade head` before starting `uvicorn`, so schema
migrations apply automatically on every deploy — no separate migration
step needed.

## 5. Deploy the Telegram bot process

The bot (`python -m app.telegram.bot`) is a separate long-running process
from the API server (see Decision — bot.py's own docstring). Deploy it as
a second service/worker from the same image, with the same env vars, and
command overridden to:

```
python -m app.telegram.bot
```

`docker-compose.yml` shows this as the `telegram-bot` service (run with
`docker compose --profile bot up`) — most hosting providers let you define
a second service/process from the same Dockerfile with a different start
command.

## 6. Deploy the frontend

On Vercel (or similar): point it at `frontend/` as the project root, set:

```
NEXT_PUBLIC_API_URL=https://your-backend-domain.example.com
```

This is a **build-time** variable (Next.js inlines `NEXT_PUBLIC_*` vars
into the client bundle) — set it before the build runs, not after.

## 7. Verify

1. `GET https://your-backend-domain/health` → `{"status": "online"}`
2. Visit the frontend URL → register an account → confirm the dashboard
   loads.
3. In Telegram, message your bot: `/start <your-username>` → confirm it
   links and `/profile` shows your data.
4. Only once all of the above works: decide whether to set
   `ENABLE_SCHEDULED_SCANNING=true` (Decision 16 — this is the point where
   the system starts proactively messaging linked users).

## 8. CI

`.github/workflows/backend.yml` and `.github/workflows/frontend.yml` run
the full test suite / lint / typecheck / build on every push and PR
touching their respective directories — no setup required, they run as
soon as this repo is on GitHub with Actions enabled (already the case).

## Since this was written (2026-07-24 Telegram/risk-policy/watchlist session)

Three new migrations landed after Phase 13: `telegram_contacts` +
`telegram_events` (chat-ID auto-capture, outbound message log), `risk_policies`
(data-driven risk curves — see `app/risk/policy.py` and
`app/services/risk_policy_service.py`), and `watchlist_symbols` (per-user
symbol lists, unioned into the scan universe — see
`app/repositories/watchlist_repository.py`). All three ship seed/backward-
compatible: an unseeded or pre-migration deploy still works via the fixed
`RISK_PERCENT_BY_PREFERENCE` fallback and the system default universe. Step
4's `alembic upgrade head` picks these up automatically — no extra action
needed beyond what this doc already says.

The Telegram bot token has been live-verified against `https://api.telegram.org/bot<token>/getMe`
this session (bot: `@Freetrade26bot`) and the full local stack (backend,
bot, frontend) was run and manually exercised — see the verification log
in this session's conversation for the exact checks run.

## Since this was written (2026-07-24 Supabase-prep session)

Step 2 above was rewritten with concrete Supabase connection-string guidance
(session pooler vs. direct vs. transaction pooler, and why this app — a
persistent server, not serverless — should default to the session pooler).
Also fixed since the previous addendum: a bare `postgres://` DATABASE_URL
(which some tools/older Supabase flows still hand out) no longer crashes
the app at startup — see `docs/DEPLOYMENT_READY_CHECKLIST.md` for the full
list of deployment-readiness fixes made this week. See that same file for
the current status of live (not just SQLite + offline-dialect) Postgres
migration verification.

## What's explicitly not automated here

- Creating the hosting accounts themselves
- Entering payment details for any paid tier
- Creating the Telegram bot (BotFather requires a human Telegram account)
- Deciding to turn on `ENABLE_SCHEDULED_SCANNING`
- Buying a custom domain (optional; every provider above gives a free
  subdomain)

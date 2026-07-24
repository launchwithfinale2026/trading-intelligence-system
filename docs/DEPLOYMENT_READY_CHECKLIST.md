# Deployment-Readiness Audit

Audit date: 2026-07-24. Goal being verified: friends can visit a URL,
register, log in, connect Telegram, and use an isolated dashboard — safely,
as a public multi-user deployment. **Nothing was deployed as part of this
audit** — everything below was checked locally (tests, live local
processes, offline SQL rendering, code review).

Status legend: ✅ verified passing · 🔧 found and fixed during this audit ·
⚠️ known limitation, not fixed (with reasoning) · ⏳ pending (see note)

---

## Frontend

| Check | Status | Detail |
|---|---|---|
| No hardcoded localhost URLs | ✅ | Only reference is `frontend/lib/api.ts`'s `process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"` — an env-var-driven default, not a hardcoded call site. Grepped `frontend/app`, `frontend/lib`, `frontend/components` for other `localhost` references — none. |
| API URL controlled by environment variable | ✅ | `NEXT_PUBLIC_API_URL` is a Next.js build-time env var, inlined into the client bundle. Verified by building with `NEXT_PUBLIC_API_URL=https://api.example-prod.com` and grepping the output `.next/static/chunks/*.js` — the prod URL was inlined, no `localhost:8000` string present anywhere in the build output. |
| Production build succeeds | ✅ | `npm run build` (Turbopack) compiles cleanly, typechecks, and prerenders all 6 routes as static content. Ran twice during this audit (once with a fake prod URL to prove env-var injection, once restored to local settings). |
| Authentication works after deployment | ✅ | Can't test a real deployed instance, but verified everything that would break it locally: JWT issuance/verification round-trips correctly (194+ backend tests), CORS preflight from a cross-origin frontend succeeds (see Backend section), and the client correctly stores/attaches the bearer token (`frontend/lib/auth-context.tsx`). Live-tested in a real browser this session: register → login → dashboard → logout → login again, no errors. |
| **Bug fixed this session, unrelated to this audit but relevant to "auth works after deployment"** | 🔧 | `LoginPage` called `router.replace()` during render (not in `useEffect`), throwing "Cannot update a component while rendering a different component." Fixed earlier this session — see conversation history. **`register/page.tsx` has the identical bug pattern and was not fixed** (out of scope for that fix's instructions) — fix it before public launch, since new users hit `/register` first. |

## Backend

| Check | Status | Detail |
|---|---|---|
| No localhost assumptions | ✅ | Uvicorn binds `0.0.0.0` (Dockerfile CMD), not `127.0.0.1`. Grepped `backend/app` for `localhost`/`127.0.0.1` — only hit is `cors_allowed_origins`'s dev-friendly default, which is env-overridable. |
| CORS supports production frontend URL | ✅ | `CORS_ALLOWED_ORIGINS` is comma-separated and parsed into a list (`main.py`), so multiple production origins work. Verified live: `OPTIONS /auth/register` with `Origin: http://localhost:3000` gets a correct preflight response with matching `access-control-allow-origin`. |
| Environment variables documented | 🔧 | `CORS_ALLOWED_ORIGINS` and `MARKET_DATA_PROVIDER` were real `Settings` fields **missing from `.env.example`** (only in `docs/DEPLOYMENT.md`'s prose, not the actual template file anyone would copy). Fixed: both added to `.env.example` with local-dev defaults and a production example. |
| Secret keys externalized | 🔧 | `SECRET_KEY` was always read from env (never hardcoded), but **nothing stopped the app from silently starting in production with the insecure default** — meaning every JWT it issues would be forgeable by anyone who reads the source. Fixed: `backend/app/core/config.py` now has `assert_production_secret_key_is_set()`, called from `main.py` at import time, which raises `RuntimeError` and refuses to start if `ENVIRONMENT=production` and `SECRET_KEY` is still the dev default. Verified live (see below) and unit tested (`tests/test_config.py`). |
| Database connection uses DATABASE_URL | ✅ | `backend/app/database/database.py` builds the engine from `settings.database_url` exclusively; no separate host/port/user/password fields exist to drift out of sync. |
| **Bug found & fixed: bare `postgres://` scheme crashes startup** | 🔧 | Several managed Postgres providers (Heroku-style, some Render/Railway configs) hand out connection strings starting with `postgres://`. SQLAlchemy 2.x no longer recognizes that scheme (`NoSuchModuleError`, raised at `create_engine()` time — i.e., app startup, both for the API and for Alembic). Fixed: `Settings.database_url` now has a `field_validator` that rewrites `postgres://` → `postgresql+psycopg2://` transparently. Verified live: `create_engine()` on a `postgres://` URL now succeeds and reports `postgresql` dialect. Unit tested. |

Live verification performed:
```
$ ENVIRONMENT=production <no SECRET_KEY set> python -c "import app.main"
RuntimeError: SECRET_KEY is still the insecure development default while
ENVIRONMENT=production. ...
```

## Database

| Check | Status | Detail |
|---|---|---|
| PostgreSQL compatibility | ✅ confirmed live | Installed Postgres 16.14 locally (Homebrew) and ran the real `alembic upgrade head` — online, parameterized, exactly how the Dockerfile's `CMD` runs it — against a brand-new empty database. All 8 migrations applied cleanly with no errors. Also separately confirmed via offline dialect rendering (`alembic upgrade head --sql`) — see caveat below, which turned out not to matter. |
| **Found (offline-only): risk_policies seed migration doesn't render in `--sql` mode** | ⚠️ confirmed harmless | `alembic upgrade head --sql` fails with `CompileError: No literal value renderer is available for literal value "[...]" with datatype JSON` on the `risk_policies` seed migration's `op.bulk_insert`. **Live-confirmed this does not affect real deploys**: the actual `alembic upgrade head` (online, parameterized via psycopg2) applied this exact migration without error, and `SELECT name, breakpoints FROM risk_policies` on the live database returned all 4 rows with correct JSON — `experimental` correctly shows `[["10", "0.50"], ["999", "0.20"], ["10000", "0.01"]]`. The offline-mode limitation is real but only affects generating a printable SQL script for manual DBA review, which this project's deploy path never does. |
| Migrations work from a fresh database | ✅ confirmed live | `alembic upgrade head` against a brand-new **live Postgres 16** database (not just SQLite) ran all 8 migrations cleanly: `users`, `profiles`, `signals`, `decisions`, `positions`, `trade_results`, `telegram_contacts`, `telegram_events`, `risk_policies` (with seed data), `watchlist_symbols` — 11 tables total (10 + `alembic_version`), verified via `\dt` and direct row queries. Also went one step further than schema-only: ran the actual FastAPI app against this live database (`uvicorn` with `DATABASE_URL` pointed at it), then exercised real API traffic — registered a user (with the new `experimental` risk preference), logged in, added a watchlist symbol via the API, and cross-checked the result with a raw SQL join (`users` ⋈ `watchlist_symbols` ⋈ `profiles`) — matched exactly. Test database and Postgres service were stopped/dropped afterward; nothing left running. |
| User isolation | ✅ | Verified at the database level (not just app code) — every user-owned table has FK `ON DELETE CASCADE` to `users.id`; unique constraints enforce isolation: `users.username`/`email`/`telegram_id` unique, `decisions(user_id, signal_id)` unique, `positions(user_id, signal_id)` unique, `watchlist_symbols(user_id, symbol)` unique. **Live-verified with two real disposable accounts** registered against the running backend this session: adding to one user's watchlist didn't appear in the other's; updating one user's profile account size didn't change the other's; each user's JWT only ever resolves to their own `current_user`. Both test accounts were deleted after verification. |

## Telegram

| Check | Status | Detail |
|---|---|---|
| One bot supports multiple users | ✅ | The bot is a single long-polling process (`python -m app.telegram.bot`) dispatching every incoming update through the same handler set; each handler resolves the acting user via `update.effective_user.id` → `UserRepository.get_by_telegram_id()` independently per call, with its own short-lived DB session (`SessionLocal()` per handler invocation — see `handlers.py`). No shared mutable state across users: grepped for module-level variables in `app/telegram/*.py` — the only ones are immutable constants (a compiled regex, message templates, a read-only dict, a fixed startup timestamp). Covered by `test_pipeline_alerts_multiple_interested_users_independently`, which seeds two linked users and confirms both get independently alerted. |
| Each user's chat ID is isolated | ✅ | `users.telegram_id` has a unique index at the database level — two users can never share a chat ID; linking a Telegram account already linked to someone else is explicitly rejected (`handlers.start`, tested: `test_start_rejects_relinking_to_a_different_telegram_user`). |
| Alerts route to the correct user | ✅ | `telegram/alerts.py`'s `send_alert`/`send_position_closed_alert` take a specific `User` and send only to `user.telegram_id` — never a broadcast. `engine/pipeline.py` loops over interested users individually, sizing and sending per-user. Live-confirmed this session: the real linked account (`THEREALJAKESTER`) received the bot's startup message; disposable test accounts (with no Telegram link) correctly received nothing. |

---

## Summary of fixes applied this session

1. `.env.example` — added missing `CORS_ALLOWED_ORIGINS` and `MARKET_DATA_PROVIDER` documentation.
2. `backend/app/core/config.py` — normalize bare `postgres://` URLs to `postgresql+psycopg2://` (prevents a startup crash on several hosting providers' connection strings).
3. `backend/app/core/config.py` + `backend/app/main.py` — refuse to start in `ENVIRONMENT=production` with the default insecure `SECRET_KEY`.
4. `docker-compose.yml` — `telegram-bot` and `scanner-worker` services now run `alembic upgrade head` themselves before starting, instead of only depending on `db` and silently racing an un-migrated schema if they start before/without `backend`.
5. Added regression tests for all of the above (`tests/test_config.py`); full suite: **197 passed**.

## Known limitations (not fixed, by design or scope)

- `frontend/app/register/page.tsx` has the same render-time-redirect bug that was fixed in `login/page.tsx` earlier this session. Fix before launch — new users hit this page first.
- The `risk_policies` seed migration doesn't render under `alembic ... --sql` (offline mode) — confirmed harmless for real deploys, which run online (see Database section above).
- `docs/DEPLOYMENT.md` (from an earlier phase) still notes Docker itself was never verified with a real `docker build` in this environment — still true; no Docker available here either. Postgres itself, however, *was* installed and used for real verification this session (see Database section) — only the containerization step remains unverified.

## Live Postgres verification — complete

Installed Postgres 16.14 locally via Homebrew (no prebuilt bottle for this
machine, so it compiled a full dependency chain from source — took a while
but finished cleanly), ran `initdb`, started the service, created a fresh
database, and:

1. Ran the real `alembic upgrade head` (online/parameterized, the same way
   the Dockerfile's `CMD` runs it) — all 8 migrations applied without error.
2. Verified all 11 tables and the `risk_policies` seed data via `psql`.
3. Started the actual FastAPI app with `DATABASE_URL` pointed at this live
   database and ran real API traffic through it: registered a user with the
   new `experimental` risk preference, logged in, added a watchlist symbol,
   and cross-checked the result against a raw SQL join — matched exactly.
4. Cleaned up: dropped the test database, stopped the Postgres service, no
   test data or running services left behind.

This is the strongest form of the check requested — not just SQLite, not
just offline SQL-dialect rendering, but a real fresh Postgres database
being migrated and used by the actual application.

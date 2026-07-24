# Roadmap

Every planned phase for the Trading Intelligence System, in build order. This
file is updated the moment a phase is completed — status, date, and the
"current capability" line all change in the same commit that finishes the
phase. See [ARCHITECTURE.md](ARCHITECTURE.md) for subsystem detail and
[DECISIONS.md](DECISIONS.md) for why things are built this way.

Rule for this file: **a phase is only marked Complete when its success
criteria are met and its tests pass.** Partial work stays In Progress.

**Note on ordering:** phases are numbered by the original spec, but are not
always *built* strictly in numeric order — where two phases have no
dependency on each other, they're built in whichever order the dependency
graph allows soonest. Phase 5 (Market Data Engine) was built before Phase 4
(Telegram) because the scanner/strategy/portfolio phases downstream all need
a data provider, while nothing downstream of Phase 4 was ready to build yet.
See DECISIONS.md if a reordering needs justifying beyond "no dependency
either way."

---

## Status legend

- ✅ Complete
- 🔜 Next up
- ⏳ Planned
- 🚫 Blocked (see note)

---

## Phase 1 — Foundation ✅

**Completed:** 2026-07-23

**Goal:** A working backend that boots and responds.

**Built:**
- Project structure (`backend/`, `frontend/`, `tests/`, `docs/`)
- Environment-based config (`.env` / `.env.example`)
- Structured logging
- SQLAlchemy database connection (SQLite for dev, Postgres-ready via `DATABASE_URL`)
- FastAPI app with lifespan startup
- `pytest` test framework wired in

**Success criteria:** `GET /health` returns `{"status": "online"}`. ✅ Verified via
`pytest` and a live `uvicorn` run.

**Dependencies:** none (first phase).

---

## Phase 2 — User Profile System ✅

**Completed:** 2026-07-23

**Goal:** Create user profiles with isolated data.

**Built:**
- `users` and `profiles` tables, migrated via Alembic (not `create_all`)
- `TimestampMixin`, `RiskPreference`/`TradingStyle`/`AlertPreference` enums shared
  between the DB and API layers
- Repository layer (`UserRepository`, `ProfileRepository`) + service layer
  (`UserService`) enforcing per-user isolation
- Domain exceptions (`NotFoundError`, `ConflictError`, `ForbiddenError`)

**Success criteria:** ✅ Verified — `UserService.get_profile` /
`update_profile` require `requesting_user_id == target_user_id` and raise
`ForbiddenError` otherwise; covered by 9 unit tests including two-user
isolation and duplicate username/email rejection.

**Dependencies:** Phase 1 (database connection).

---

## Phase 3 — Authentication ✅

**Completed:** 2026-07-23

**Goal:** Users can securely register, log in, and log out; dashboard routes
are protected.

**Built:**
- `POST /auth/register`, `POST /auth/login` (OAuth2 password flow, JWT), `POST /auth/logout`
- Password hashing via `bcrypt` (never plaintext, never reversible)
- Stateless JWT bearer tokens (`core/security.py`), `get_current_user` dependency
- `GET /users/me`, `PATCH /users/me/profile` protected and isolation-tested
- Domain-exception → HTTP-status translation (`core/exception_handlers.py`)

**Success criteria:** ✅ Verified — unauthenticated requests to `/users/me`
return 401; wrong password returns 401; a logged-in user can only read/update
their own profile (19 automated tests + a live end-to-end `curl` smoke test).

**Dependencies:** Phase 2 (users must exist to authenticate).

---

## Phase 4 — Telegram System 🔜

**Goal:** A Telegram bot that can identify which user is messaging and route
commands accordingly.

**Will build:**
- Bot bootstrap (`telegram/bot.py`)
- Commands: `/start`, `/profile`, `/status`, `/open`, `/ignore`, `/positions`
- User resolution: incoming Telegram user → system user → profile

**Success criteria:** Each command responds correctly for a known user, and
an unrecognized Telegram user is handled gracefully (no crash, no data
leak).

**Dependencies:** Phase 2 (users), Phase 3 (identity model, even if Telegram
auth itself is separate from web session auth).

---

## Phase 5 — Market Data Engine ✅

**Completed:** 2026-07-23 (built ahead of Phase 4 — see ordering note above)

**Goal:** A replaceable market data abstraction, backed first by `yfinance`.

**Built:**
- `MarketDataProvider` ABC: `get_price`, `get_history`, `get_volume`,
  `get_market_status`, returning vendor-neutral `PricePoint`/`MarketStatus`
  dataclasses (never a raw yfinance/pandas object)
- `YFinanceProvider` implementation; raises `MarketDataError` instead of
  ever returning fabricated/placeholder data when a symbol is invalid or a
  fetch fails
- `market/factory.py` — provider selection via `MARKET_DATA_PROVIDER` config
- Scheduler skeleton (`core/scheduler.py`, APScheduler-backed), started/stopped
  in the app lifespan with zero jobs registered yet

**Success criteria:** ✅ Verified — all four methods tested against mocked
yfinance responses (9 tests) plus a live manual run against real Yahoo
Finance data for `AAPL` (price, volume, 5-day history, market status all
returned correctly).

**Dependencies:** Phase 1 (config for provider selection).

---

## Phase 6 — Quality Filter Scanner ⏳

**Goal:** Narrow a broad universe down to a small, high-quality candidate
list — not scan every random stock.

**Will build:**
- Liquidity filter (acceptable volume)
- Quality filter (market cap threshold)
- Technical filter (positive trend)
- Momentum filter (unusual strength)
- Ranked output: `[{symbol, score}, ...]`

**Success criteria:** Given a fixed test universe, the scanner returns a
ranked, deduplicated candidate list and excludes assets that fail any
filter — verified with fixture data, not live fetches, so tests are
deterministic.

**Dependencies:** Phase 5 (needs the data provider).

---

## Phase 7 — Strategy Engine ⏳

**Goal:** First two strategies producing structured signals.

**Will build:**
- `strategies/base.py` — Strategy interface + `Signal` contract
- `strategies/momentum.py` — trend strength, volume increase, positive momentum
- `strategies/breakout.py` — structure break, volume confirmation
- `signals` table + `api/signals.py`

**Success criteria:** Each strategy returns a well-formed `Signal` object
(`symbol, direction, entry, stop_loss, target, confidence, reasoning`) for
known fixture data, including correctly returning "no signal" when
conditions aren't met.

**Dependencies:** Phase 6 (strategies run against scanner output).

---

## Phase 8 — Risk Engine ⏳

**Goal:** Every signal gets a position size derived from the user's account
and risk preference.

**Will build:**
- `risk/calculator.py` — sizing from entry/stop distance + risk %
- Aggressive (2% risk) / conservative (0.5% risk) presets, configurable per
  profile

**Success criteria:** Given a known account size, risk %, entry, and stop,
the calculator returns the exact expected position size — covered by unit
tests with hand-computed expected values.

**Dependencies:** Phase 2 (user risk preference), Phase 7 (signals to size).

---

## Phase 9 — Telegram Alerts ⏳

**Goal:** Signals reach users as formatted, actionable Telegram messages.

**Will build:**
- Alert formatting (symbol, strategy, entry, position, stop, target,
  confidence, reasoning)
- `OPEN` / `IGNORE` reply handling wired to the signal that triggered the alert

**Success criteria:** A generated signal produces a correctly formatted
Telegram message, and a reply of `OPEN` or `IGNORE` is correctly attributed
to the right user and signal.

**Dependencies:** Phase 4 (bot), Phase 7 (signals), Phase 8 (sized signals).

---

## Phase 10 — Position Tracking ⏳

**Goal:** Track positions opened from accepted signals through to close.

**Will build:**
- `positions` table + `portfolio/positions.py`
- Monitoring loop: stop hit, target hit, thesis failure
- `STOP LOSS ALERT` / `TAKE PROFIT ALERT` Telegram messages

**Success criteria:** Opening a position via `OPEN` creates a tracked
position; simulated price movement through stop/target correctly closes it
and sends the right alert.

**Dependencies:** Phase 9 (positions originate from an OPEN reply), Phase 5
(price monitoring).

---

## Phase 11 — Feedback System ⏳

**Goal:** The system's track record becomes measurable data.

**Will build:**
- `decisions` and `trade_results` tables
- `feedback/tracker.py` — records signal → decision → result → performance
- Aggregate stats: accepted vs. ignored signals, win rate by strategy

**Success criteria:** After a handful of simulated signals/decisions/results,
the tracker produces correct aggregate stats (accept rate, per-strategy
win rate) verified against hand-computed expected values.

**Dependencies:** Phase 9 (decisions), Phase 10 (results).

---

## Phase 12 — Web Dashboard ⏳

**Goal:** A dashboard for login, profile management, and reviewing history —
not a duplicate of Telegram's real-time alerting.

**Will build:**
- Login page
- Profile page (account size, risk level, strategy preferences, alert
  settings)
- Dashboard home (market status, active positions, recent signals,
  performance)
- History page (past signals, decisions, results)

**Success criteria:** A logged-in user sees only their own data across all
four pages; an unauthenticated visitor is redirected to login.

**Dependencies:** Phase 3 (auth), Phase 11 (feedback data to display).

---

## Phase 13 — Online Deployment ⏳

**Goal:** The system is accessible remotely, on free-tier hosting.

**Will build:**
- Frontend hosting
- Backend hosting
- Managed database hosting
- Secrets management for production environment variables

**Success criteria:** The dashboard is reachable over the public internet by
Jake and friends, backed by the deployed backend and database, with no
secrets committed to the repo.

**Dependencies:** All prior phases functionally complete.

---

## Future features (explicitly not in v1 scope)

Tracked here so they aren't silently designed around, but not built or
scheduled until a deliberate decision is made to start them:

- AI reasoning layer
- News sentiment analysis
- Broker connection
- Automatic trade execution
- Mobile app
- Advanced analytics
- Subscription system

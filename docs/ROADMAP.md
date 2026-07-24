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

## Phase 4 — Telegram System ✅

**Completed:** 2026-07-23 (built after Phases 5-8 — see ordering note above)

**Goal:** A Telegram bot that can identify which user is messaging and route
commands accordingly.

**Built:**
- `telegram/bot.py` — bootstrap (`python -m app.telegram.bot`), a separate
  process from the API server since a long-polling bot has a "run forever"
  lifecycle and shouldn't block the API from starting when no token is set
- `telegram/handlers.py` — `/start <username>` (links a Telegram account to
  an existing dashboard user), `/profile`, `/status`, `/positions`,
  `/open <signal_id>`, `/ignore <signal_id>`, every handler resolving
  Telegram user → system user via `User.telegram_id`
- **Pulled the `decisions` table forward from Phase 11**: `/open` and
  `/ignore` need somewhere real to record a decision, or they're not
  functional commands — see the ordering note above and Decision 15. One
  decision per (user, signal), enforced by a unique constraint.
- `/positions` currently always replies "no active positions" — that's
  literally true today (Position tracking doesn't exist until Phase 10), not
  a placeholder pretending to work.

**Success criteria:** ✅ Verified — 17 tests: linking flow (including
rejecting a relink to a different Telegram account), every command against
both a linked and an unlinked user (graceful, no crash, no data leak),
OPEN/IGNORE recording real Decision rows and rejecting a duplicate decision
on the same signal, invalid signal id (unknown and non-numeric) handled
cleanly. Also verified `build_application()` correctly raises with a clear
error when `TELEGRAM_BOT_TOKEN` is unset — creating the actual bot via
BotFather is the human step this phase stops at.

**Dependencies:** Phase 2 (users), Phase 3 (identity model, even if Telegram
auth itself is separate from web session auth), Phase 7 (signals to decide on).

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

## Phase 6 — Quality Filter Scanner ✅

**Completed:** 2026-07-23

**Goal:** Narrow a broad universe down to a small, high-quality candidate
list — not scan every random stock.

**Built:**
- `analysis/technical.py` — pure indicators: SMA, average volume, percent
  change, uptrend check
- `analysis/scoring.py` — `evaluate_filters` (liquidity, market cap, trend,
  momentum-surge thresholds) and `score_candidate` (0-100 heuristic)
- `market/scanner.py` — `Scanner.scan(universe)` orchestrates fetching via
  `MarketDataProvider`, applies filters, scores, ranks, dedupes; skips (logs)
  symbols with unavailable data instead of crashing the whole scan
- Extended `MarketDataProvider` with `get_market_cap()` (not in the original
  four-method list — needed once the quality filter required it)

**Success criteria:** ✅ Verified — 34 tests across technical indicators,
filter/score logic, and scanner orchestration, all against fixture data
(deterministic, no live fetches in the suite). A separate live run against
real Yahoo Finance data for AAPL/MSFT/NVDA/TSLA completed without error and
correctly returned zero candidates (none currently show a real volume surge)
— confirms the filter is actually selective rather than rubber-stamping.

**Dependencies:** Phase 5 (needs the data provider).

---

## Phase 7 — Strategy Engine ✅

**Completed:** 2026-07-23

**Goal:** First two strategies producing structured signals.

**Built:**
- `strategies/base.py` — `Signal` dataclass contract + `Strategy` ABC
  (pure: same history in, same signal-or-None out)
- `strategies/momentum.py` — requires price above its 50-day MA, a >=5%
  gain over the last 10 trading days, and volume >=1.3x its 20-day average;
  stop at -5%, target at 2R
- `strategies/breakout.py` — requires a close above the prior 20-day high on
  >=1.5x average volume; stop at the broken resistance level (now support),
  target at 2R
- `signals` table (Alembic-migrated) + `repositories/signal_repository.py` +
  `services/signal_service.py` + `GET /signals` (authenticated, not
  user-isolated — signals aren't user-owned data)
- New `SignalDirection` enum (long/short) in `domain/enums.py`

**Success criteria:** ✅ Verified — 9 strategy tests against fixture price
histories (both strategies firing correctly and correctly returning `None`
for insufficient history, no momentum, no volume confirmation, and
below-trend cases), plus 5 persistence/API tests. Found and fixed a real
ordering bug along the way: SQLite's `CURRENT_TIMESTAMP` has 1-second
resolution, so signals inserted within the same second need `id DESC` as an
explicit tiebreaker for "most recent first" to be correct. Live integration
smoke test against real NVDA history (124 bars) ran both strategies without
error. 76/76 suite passing.

**Dependencies:** Phase 6 (strategies run against scanner output).

---

## Phase 8 — Risk Engine ✅

**Completed:** 2026-07-23 (built ahead of Phase 7 — the calculator only needs
account size + entry/stop, not an actual Signal object; see ordering note above)

**Goal:** Every signal gets a position size derived from the user's account
and risk preference.

**Built:**
- `risk/calculator.py` — `calculate_position_size()`: whole-share sizing
  from entry/stop distance + risk %, works for both long and short signals
- Aggressive (2%) / moderate (1%, this project's own interpolation — see
  Decision 14) / conservative (0.5%) presets keyed by `RiskPreference`
- Explicit `ValueError`s for non-positive account/entry or a zero-distance
  stop, rather than silently returning a nonsensical size

**Success criteria:** ✅ Verified — 8 unit tests with hand-computed expected
values (aggressive/moderate/conservative, long/short, the zero-affordable-
shares edge case, and all three invalid-input cases).

**Dependencies:** Phase 2 (user risk preference). Wiring sized signals into
an actual alert still depends on Phase 7 (signals to size) and happens in
Phase 9.

---

## Phase 9 — Telegram Alerts ✅

**Completed:** 2026-07-23

**Goal:** Signals reach users as formatted, actionable Telegram messages.

**Built:**
- `telegram/alerts.py` — `format_alert()` (symbol, strategy, direction,
  entry, sized position, stop, target, confidence, reasoning, plus an
  embedded `Signal ID:` footer) and `send_alert()` (per-user send that logs
  and continues rather than aborting the batch on one user's failure)
- Plain-text `OPEN`/`IGNORE` reply handling (`handlers.handle_text_reply`),
  in addition to the `/open`/`/ignore` commands from Phase 4 — this is what
  actually delivers "reply OPEN or IGNORE to the alert," matching the
  original spec's example UX. Both paths share one `_record_decision_and_reply`
  function so there's exactly one place decision-recording logic lives.
- `engine/pipeline.py` — `run_scan_cycle()`: scans the curated universe
  (`market/universe.py`), evaluates both strategies, persists any signal,
  and alerts every linked user whose `alert_preference` allows it, sized to
  their own account/risk (skipping users a zero-share position would result
  in). Registered with the Phase 5 scheduler **only** if
  `ENABLE_SCHEDULED_SCANNING=true` — off by default; see Decision 16.

**Success criteria:** ✅ Verified — 3 formatting tests (including an
extract/format round-trip), 5 additional reply-handler tests (case
insensitivity, ignoring unrelated text, ignoring non-alert replies), and 7
pipeline tests covering: alerting a wired-up user, skipping an unlinked
user, skipping an opted-out user, alerting a high-confidence-only user for
a qualifying signal, skipping a user whose risk budget affords zero shares,
alerting multiple users independently, and returning 0 when nothing
qualifies. 108/108 suite passing.

**Dependencies:** Phase 4 (bot), Phase 7 (signals), Phase 8 (sized signals).

---

## Phase 10 — Position Tracking ✅

**Completed:** 2026-07-23

**Goal:** Track positions opened from accepted signals through to close.

**Built:**
- `positions` table (Alembic-migrated) + `repositories/position_repository.py`
  + `services/position_service.py` — positions live in the same
  repository/service pattern as every other entity rather than a one-off
  `portfolio/positions.py` module, for architectural consistency (Decision 7)
- `PositionService.open_position()`: wired to a successful `/open` (or
  text-reply OPEN) decision — sizing is **recomputed at open time** from
  the user's current profile, not reused from whenever the alert was
  originally sent, since account size can change between alert and decision
- `PositionService.check_and_close_open_positions()`: fetches one price per
  distinct symbol (not per position — multiple users can hold the same
  symbol), closes on stop or target for both long and short, leaves
  positions open otherwise, skips symbols with unavailable data
- `engine/pipeline.py` gains `run_position_monitor_cycle()`, registered
  with the scheduler alongside the scan cycle (same
  `ENABLE_SCHEDULED_SCANNING` gate, its own interval —
  `POSITION_MONITOR_INTERVAL_SECONDS`, default 300s)
- `telegram/alerts.py` gains `format_position_closed_alert()` (🛑 STOP LOSS
  ALERT / ✅ TAKE PROFIT ALERT with P/L) and `send_position_closed_alert()`
- `/positions` now reports real open positions instead of the Phase 4
  placeholder

**Success criteria:** ✅ Verified — 8 `PositionService` unit tests (sizing,
duplicate rejection, zero-share risk rejection, stop/target close for long
*and* short, leaving positions open in between, skipping unavailable
prices), 4 end-to-end monitor-cycle tests (close + alert on stop, close +
alert on target, no-op in between, DB state actually updated), plus new
Telegram-handler tests confirming `/open` creates a real `Position` visible
via `/positions` and `/ignore` does not. 122/122 suite passing.

**Dependencies:** Phase 9 (positions originate from an OPEN reply), Phase 5
(price monitoring).

---

## Phase 11 — Feedback System ✅

**Completed:** 2026-07-23

**Goal:** The system's track record becomes measurable data.

**Built:**
- `trade_results` table (Alembic-migrated) — one row per closed position,
  computed once at close time (win/loss, R-multiple, P/L) rather than
  re-derived from `positions` on every read
- `repositories/trade_result_repository.py` + `services/feedback_service.py`
  — same repository/service pattern as everything else, superseding the
  originally-planned `feedback/tracker.py` (consistent with the Phase 10
  `portfolio/` decision)
- `FeedbackService.record_trade_result()` — wired into
  `run_position_monitor_cycle()` immediately after a position closes, so a
  closed position without a recorded result is structurally impossible on
  the one code path that closes positions
- `FeedbackService.get_performance_by_strategy()` — per-strategy signals
  generated, accepted/ignored counts, trades closed, wins, win rate,
  average R-multiple
- `GET /feedback/performance` (authenticated)

**Success criteria:** ✅ Verified — 6 `FeedbackService` tests including a
fully hand-computed multi-strategy, multi-user scenario (3 momentum
signals: one win at +2.00R, one loss at -1.00R, one ignored; one breakout
signal with no decisions) asserting exact `accepted=2`, `ignored=1`,
`win_rate=50.0`, `average_r_multiple=0.50` for momentum and all-zero/`None`
for breakout. Plus 3 API tests and a monitor-cycle integration test
confirming a real `TradeResult` row appears after a stop-loss close.
132/132 suite passing.

**Dependencies:** Phase 4 (decisions), Phase 10 (results).

---

## Phase 12 — Web Dashboard ✅

**Completed:** 2026-07-23

**Goal:** A dashboard for login, profile management, and reviewing history —
not a duplicate of Telegram's real-time alerting.

**Built:**
- Next.js 16 (App Router) + TypeScript + Tailwind CSS 4, scaffolded via
  `create-next-app` — see `frontend/AGENTS.md`'s own note that this Next.js
  version postdates training data; verified current conventions (async
  params, Server/Client Components, `NEXT_PUBLIC_` env vars) against
  `node_modules/next/dist/docs/` before writing pages
- `/login`, `/register` — auth forms; register includes the full profile
  (account size, risk preference, trading style, alert preference)
- `/` (dashboard home) — market status, active positions, recent signals,
  performance by strategy
- `/profile` — view/edit profile fields, persisted via `PATCH /users/me/profile`
- `/history` — past decisions joined against signals and positions client-side
  (symbol, strategy, decision, result, close price)
- `lib/api.ts` — typed fetch client, `lib/auth-context.tsx` — token in
  `localStorage`, `components/ProtectedRoute.tsx` — redirects to `/login`
  when unauthenticated
- **New backend endpoints added to support the dashboard** (weren't needed
  before — only existed as Telegram-handler-internal calls): `GET
  /portfolio/positions`, `GET /portfolio/decisions` (both isolated to the
  requesting user), `GET /market/status`. Backend also gained CORS
  middleware (`CORS_ALLOWED_ORIGINS`, defaults to the Next.js dev origin)
- `pages/` directory from the original spec's structure is unused — the App
  Router (`app/`) supersedes the older Pages Router; keeping an empty
  `pages/` would just be confusing

**Success criteria:** ✅ Verified — `npx tsc --noEmit`, `npm run lint`, and
`npm run build` all pass clean; 5 Vitest unit tests cover the API client's
request/error handling. **Not verified interactively in a browser** — the
Claude-in-Chrome extension wasn't connected in this environment. Instead:
booted both the backend and `npm run dev`, confirmed every route returns
200 with the expected server-rendered content via `curl`, and drove the
actual cross-origin request flow (register → login → authenticated
`/users/me` and `/market/status`, with `Origin: http://localhost:3000`)
confirming correct CORS headers and response shapes matching the
TypeScript types. Isolation (a logged-in user sees only their own
positions/decisions) is verified at the API layer (Phase 2/3 pattern,
re-tested here for the two new endpoints) rather than by clicking through
two browser sessions. **A human should still click through this once in a
real browser before relying on it** — see the end-of-mission report.

**Dependencies:** Phase 3 (auth), Phase 11 (feedback data to display).

---

## Phase 13 — Online Deployment 🚫 blocked on human action

**Goal:** The system is accessible remotely, on free-tier hosting.

**Built (everything that doesn't require creating an account or spending
money):**
- `backend/Dockerfile` — multi-stage, runs `alembic upgrade head` before
  `uvicorn` on every start (never `create_all` in production — Decision 12)
- `frontend/Dockerfile` — multi-stage, uses Next.js's `output: "standalone"`
  for a minimal runtime image
- `docker-compose.yml` — full local stack (Postgres + backend + optional
  Telegram bot process + frontend), for sanity-checking everything together
  before deploying anywhere
- `.github/workflows/backend.yml`, `.github/workflows/frontend.yml` — CI:
  full test suite / lint / typecheck / build on every push and PR
- `docs/DEPLOYMENT.md` — the exact human checklist: provider suggestions,
  required env vars, migration behavior, bot deployment, verification steps

**Not built — genuinely requires a human:**
- Creating hosting accounts (backend + frontend + database)
- Entering payment details for any paid tier
- Creating the Telegram bot via @BotFather (requires a human Telegram account)
- Buying a domain (optional)
- Deciding when to flip `ENABLE_SCHEDULED_SCANNING=true` (Decision 16)

**Success criteria:** Everything above the "genuinely requires a human"
line is done and verified as far as it can be without those accounts —
Docker/CI configs reviewed carefully, but **not run** (Docker isn't
installed in the environment this was built in). Full success (dashboard
reachable over the public internet) is blocked on the human steps in
`docs/DEPLOYMENT.md`.

**Dependencies:** All prior phases functionally complete.

---

## Phase 14 — Market Observation Layer Upgrade ✅

**Completed:** 2026-07-24

**Goal:** Requested as a standalone upgrade to make the autonomous market
observation loop (Market Data Provider → Market Universe → Quality Filter →
Technical Analysis → Strategy Engine → Opportunity Ranking → Risk
Calculation → Telegram Alert) more complete and explicit. Most of this
pipeline already existed from Phases 5–9; this phase is the delta between
what was requested and what was already built, not a rebuild.

**Already satisfied by prior phases (verified, not rebuilt):**
- Market Data Provider abstraction + yfinance implementation — Phase 5
- Strategy framework (base + momentum + breakout, deterministic/testable/
  explainable) — Phase 7
- Telegram alert pipeline requiring no credentials to format/test — Phase 9

**Built new this phase:**
- `market/universe.py` — updated `DEFAULT_UNIVERSE` to the exact requested
  list (SPY, QQQ, NVDA, MSFT, AAPL, GOOG, AMZN, META, AMD, TSLA), replacing
  the broader 15-symbol list from Phase 9
- `analysis/technical.py` — added `rsi()`, `historical_volatility()`
  (stdev of daily returns), `trend_direction()` (MA-crossover up/down/flat)
- `analysis/filtering.py` (new module) — the explicit five-criteria
  Quality Filter (liquidity, volatility, trend, volume, price movement),
  each with human-readable pass/fail reasoning. Wired into `Scanner.scan()`
  as an **additional** gate alongside the existing `evaluate_filters` — a
  candidate must clear both; proven with a test where a symbol passes the
  original filter but is correctly rejected by the new one for being too
  erratic
- `market/scanner.py` — `RankedCandidate` now carries a `reasons: list[str]`
  field (the Quality Filter's positive reasons), satisfying "store
  reasoning" for the Opportunity Ranking stage
- `strategies/momentum_breakout.py` (new) — the flagship combined strategy:
  structure break + momentum + volume confirmation + an RSI-overbought
  guard the simpler momentum/breakout strategies don't have. Added
  alongside (not replacing) the existing two strategies in
  `engine/pipeline.py`'s `DEFAULT_STRATEGIES`
- `engine/worker.py` (new) — standalone, credential-free Scanner Worker
  process (`python -m app.engine.worker`): loops scan + position-monitor
  cycles continuously, catches and logs per-cycle failures without dying,
  runs on `SCAN_INTERVAL_SECONDS`. Independent of (not a replacement for)
  the existing API-embedded scheduler from Phase 5/9 — two ways to run the
  same cycles, added as its own `docker-compose.yml` service
  (`--profile worker`)
- `telegram/alerts.py` — renamed the `Strategy:` alert field to `Setup:` to
  match the requested message format exactly (Symbol/Setup/Entry/Stop/
  Target/Confidence/Reasoning)

**Success criteria:** ✅ Verified — 28 new tests: 10 for the three new
indicators (all hand-computed, including an engineered ±10%/±10% return
sequence giving an exact stdev of 10), 6 for the quality filter (clean
pass-all case plus one isolated failure per criterion), 6 for the momentum
breakout strategy (fires + 5 distinct no-signal cases, including an
overbought-RSI rejection), 2 additional scanner tests (reasoning present;
an erratic symbol rejected by the new gate despite passing the old one), 4
for the worker (correct cycle count, survives an exception mid-loop,
doesn't oversleep, `max_iterations=0` runs nothing). Live-smoke-tested the
worker for one real cycle with no Telegram token set — logs a clean no-op
rather than crashing. 164/164 full suite passing.

**Dependencies:** Phases 5, 6, 7, 9 (the pipeline stages this extends).

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

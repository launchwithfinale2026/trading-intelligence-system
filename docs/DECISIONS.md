# Decisions

A log of architectural decisions for the Trading Intelligence System, in the
style of an ADR (Architecture Decision Record) log. Every decision that
shapes the system's structure, boundaries, or non-negotiable behavior goes
here — not implementation details that can be inferred from the code.

Each entry has: **Date**, **Decision**, **Reasoning**, **Alternatives
considered**, **Status** (Proposed / Accepted / Deprecated).

New entries are appended at the bottom. Never edit history to make a past
decision look like something it wasn't — if a decision changes, add a new
entry and mark the old one Deprecated, with a pointer to the entry that
replaces it.

---

## 1. Trading Intelligence System is permanently separate from Veronica

- **Date:** 2026-07-23
- **Decision:** This project (`trading-intelligence-system`) is a fully
  standalone system. It does not import from, depend on, share a database
  with, or otherwise integrate with the Veronica project. Veronica files are
  never referenced or modified from this codebase.
- **Reasoning:** The two systems serve different purposes and were explicitly
  scoped as separate by the user. Keeping a hard boundary avoids accidental
  coupling that would make either system harder to reason about, deploy, or
  hand to someone else independently.
- **Alternatives considered:** Sharing infrastructure (auth, database, or
  hosting) with Veronica to reduce setup work. Rejected — the coupling risk
  outweighs the setup savings, and the user was explicit about separation.
- **Status:** Accepted.

---

## 2. Human approval required before any trade execution

- **Date:** 2026-07-23
- **Decision:** No code path in this system places, modifies, or cancels a
  real order. Every signal terminates in a Telegram alert requiring an
  explicit human `OPEN` or `IGNORE` reply. There is no "auto-trade" mode.
- **Reasoning:** This is a decision-support tool, not an execution system.
  Automatic execution introduces financial risk, regulatory complexity, and
  failure modes (bad data, bad fills, runaway loops) that are out of scope
  for a personal project used by a small group of friends.
- **Alternatives considered:** Optional auto-execution behind a feature flag
  for advanced users. Rejected for v1 — even as an opt-in, it changes the
  system's risk profile and testing burden significantly, and it's listed as
  a future/possible feature, not a v1 goal.
- **Status:** Accepted.

---

## 3. Build → Test → Verify → Commit → Push workflow

- **Date:** 2026-07-23
- **Decision:** Every phase follows the same loop: build the smallest working
  slice, run tests, verify behavior (including live/manual verification where
  applicable, not just unit tests), commit, then push. No phase is started
  before the previous phase's tests pass.
- **Reasoning:** This is a system handling trading decisions for real people;
  silently broken foundations compound into hard-to-diagnose failures later
  (e.g. a broken risk calculator surfacing as a bad position size months in).
  A strict build/verify loop keeps every phase independently trustworthy.
- **Alternatives considered:** Building multiple phases ahead before testing,
  to move faster. Rejected — matches the user's explicit instruction to
  "never move forward with broken foundations."
- **Status:** Accepted.

---

## 4. Multi-user architecture from the beginning

- **Date:** 2026-07-23
- **Decision:** Users and profiles are modeled from Phase 2 onward, even
  though the initial user base is just Jake and a small group of friends.
  Every user-owned table carries a `user_id` and every query is scoped to the
  authenticated user.
- **Reasoning:** Retrofitting multi-tenancy after building as a single-user
  system is expensive and risky (it's easy to miss a query that should have
  been scoped). Building it in from the start, while keeping the user count
  small, is cheap by comparison.
- **Alternatives considered:** Single-user v1 with multi-user added later.
  Rejected — the spec requires isolated per-user data (risk preference,
  account size, alerts) from day one, and Jake + friends are using it
  concurrently, not sequentially.
- **Status:** Accepted.

---

## 5. Telegram is the notification interface

- **Date:** 2026-07-23
- **Decision:** Telegram Bot API is the channel for real-time alerts and the
  `OPEN`/`IGNORE` decision loop.
- **Reasoning:** Telegram has a free, well-documented Bot API, supports fast
  structured replies well-suited to `OPEN`/`IGNORE`, and requires no app
  store review or push-notification infrastructure of our own.
- **Alternatives considered:** Email — too slow and low-signal for real-time
  alerts. SMS — costs money per message and has no free bot API. Push
  notifications via a custom mobile app — a mobile app is explicitly out of
  scope for v1.
- **Status:** Accepted.

---

## 6. Dashboard is the control interface

- **Date:** 2026-07-23
- **Decision:** The web dashboard (Next.js) is where users manage profile
  settings and review history/performance. It is not used for real-time
  alerting — that's Telegram's job.
- **Reasoning:** Splitting responsibilities this way keeps each interface
  doing what it's good at: Telegram for low-latency push notifications and
  quick replies, the dashboard for structured configuration and browsing
  history that doesn't fit in a chat message.
- **Alternatives considered:** A single interface (dashboard-only, with
  in-app notifications instead of Telegram). Rejected — polling or web-push
  notifications are less reliable and slower to reach a user than a Telegram
  push, and the spec explicitly calls for both.
- **Status:** Accepted.

---

## 7. Modular architecture only

- **Date:** 2026-07-23
- **Decision:** Each subsystem (scanner, strategy engine, risk engine,
  portfolio tracker, feedback system, Telegram bot, market data provider)
  lives in its own module with a clear interface, and modules communicate
  through well-defined data contracts (e.g. the `Signal` object), not shared
  mutable state.
- **Reasoning:** Strategies, providers, and filters are all expected to
  change or multiply over time (new strategies, new data providers). Modular
  boundaries mean adding a strategy or swapping a data provider doesn't
  require touching unrelated code.
- **Alternatives considered:** A single monolithic scanning/trading module
  for faster initial development. Rejected — the spec explicitly calls for
  modular components, and the planned growth (multiple strategies, multiple
  providers) makes a monolith a near-term liability, not a long-term one.
- **Status:** Accepted.

---

## 8. Replaceable market data provider

- **Date:** 2026-07-23
- **Decision:** All market data access goes through a `MarketDataProvider`
  interface (`get_price`, `get_history`, `get_volume`, `get_market_status`).
  The first implementation wraps `yfinance`; Alpaca, Polygon, and Interactive
  Brokers are designed-for but not built.
- **Reasoning:** `yfinance` is free and has no API key requirement, making it
  the fastest way to get a working system. But it's not reliable enough for
  anything beyond personal/dev use (rate limits, occasional breakage), so the
  system must be able to swap providers without rewriting callers.
- **Alternatives considered:** Building directly against `yfinance` calls
  throughout the codebase. Rejected — the spec explicitly requires the system
  not be "tied permanently to one provider."
- **Status:** Accepted.

---

## 9. No hardcoded secrets

- **Date:** 2026-07-23
- **Decision:** No API keys, tokens, passwords, or connection strings are
  ever committed to the repository. All secrets are read from environment
  variables (`.env`, git-ignored), with `.env.example` documenting required
  variables without real values.
- **Reasoning:** This is a baseline security requirement for any system
  handling authentication and third-party API access (Telegram bot token,
  future broker/data provider keys), and it's explicitly called out as a
  core principle.
- **Alternatives considered:** Storing secrets in a checked-in config file
  restricted by `.gitignore` only for production values. Rejected in favor
  of environment variables — simpler, standard, and works uniformly across
  local dev and any hosting provider used in Phase 13.
- **Status:** Accepted.

---

## 10. No fake market data

- **Date:** 2026-07-23
- **Decision:** The system never fabricates prices, volume, or other market
  data. Missing or unavailable data is surfaced as missing (error/null), not
  papered over with placeholder values. Test fixtures use realistic,
  clearly-labeled sample data — never presented as live data.
- **Reasoning:** A trading assistant that silently fabricates data when a
  provider fails is worse than one that visibly fails — it erodes trust and
  can lead to real financial decisions based on invented numbers. This is a
  core, non-negotiable principle for the project.
- **Alternatives considered:** Falling back to cached/stale data with a
  timestamp when live data is unavailable, presented as current. Rejected as
  written — if this is needed later, it must be explicit (clearly labeled as
  stale) and would get its own decision entry, not silent fallback.
- **Status:** Accepted.

---

## 11. No automatic execution in V1

- **Date:** 2026-07-23
- **Decision:** V1 has no broker integration and no order-placing code path
  of any kind. This is distinct from (and reinforces) Decision 2 — this entry
  specifically scopes it to "v1," acknowledging that broker connection is a
  possible future feature but explicitly not attempted now.
- **Reasoning:** Matches the project's explicit non-goals list. Building
  toward execution prematurely would pull design decisions (order types,
  broker error handling, partial fills) into a system that isn't ready for
  them and doesn't need them yet.
- **Alternatives considered:** Building a "paper trading" auto-execution mode
  against a simulated broker in V1. Rejected — out of scope per the build
  spec's explicit "Future Features — Do Not Build Now" list.
- **Status:** Accepted.

---

## 12. Schema managed by Alembic migrations, not `create_all`

- **Date:** 2026-07-23
- **Decision:** Starting with Phase 2's `users`/`profiles` tables, all schema
  changes are Alembic migrations committed to the repo. The FastAPI app no
  longer calls `Base.metadata.create_all()` on startup. Test fixtures still
  use `create_all` against a throwaway in-memory SQLite database, for speed —
  that's a test-only convenience, not how the real database is managed.
- **Reasoning:** `create_all` cannot alter existing tables or express "how do
  I get from schema version N to N+1," which is exactly what's needed once
  Postgres is used in production (Decision-adjacent: the spec prefers
  Postgres). Deciding this in Phase 2, while there are only two tables, is
  far cheaper than retrofitting migrations after several phases of ad hoc
  schema changes.
- **Alternatives considered:** Keep `create_all` for as long as possible and
  add Alembic only before Phase 13 deployment. Rejected — every phase from
  here adds tables/columns, so deferring migrations just means writing the
  same schema history retroactively, with more risk of it not matching
  reality.
- **Status:** Accepted.

---

## 13. Stateless JWT auth with bcrypt password hashing

- **Date:** 2026-07-23
- **Decision:** Authentication uses bcrypt for password hashing (via the
  `bcrypt` package directly) and short-lived, stateless JWT bearer tokens
  (via `PyJWT`) for session handling. There is no server-side session store;
  "logout" is a client-side token discard.
- **Reasoning:** bcrypt is a proven, purpose-built password hashing algorithm
  with no configuration footguns. Using the `bcrypt` package directly (rather
  than `passlib`) avoids a real, current compatibility break between recent
  `passlib` releases and `bcrypt`>=4.1. Stateless JWTs need no session table
  and no shared cache, which fits a small, low-traffic personal system —
  the tradeoff (can't force-revoke a single token before it expires) is
  acceptable at this scale and is mitigated by short expiry.
- **Alternatives considered:** `passlib[bcrypt]` — rejected due to the
  compatibility issue above. Server-side sessions (DB- or Redis-backed) —
  rejected as unnecessary infrastructure for a handful of users; would be
  revisited if immediate token revocation becomes a real requirement.
- **Status:** Accepted.

---

## 14. Moderate risk preference = 1% of account per trade

- **Date:** 2026-07-23
- **Decision:** The build spec explicitly defines aggressive = 2% risk and
  conservative = 0.5% risk per trade, but doesn't define "moderate" (which
  exists as a `RiskPreference` value alongside the other two). This project
  sets moderate = 1%.
- **Reasoning:** 1% sits at a natural midpoint and is also the single most
  common default risk-per-trade figure in general trading education, so it's
  a reasonable value to ship rather than leaving the enum member undefined
  or blocking on a human decision for one number.
- **Alternatives considered:** Omitting "moderate" until a human specifies
  it. Rejected — the enum already existed from Phase 2 and leaving it
  partially implemented would make `RiskPreference.MODERATE` a landmine
  (accepted by the API, then failing or behaving oddly in the risk engine).
  This is exactly the kind of small, low-stakes, easily-revisited numeric
  choice the autonomous build mission calls out as not requiring a human.
- **Status:** Accepted — trivially revisable; change the one constant in
  `risk/calculator.py` if a different value is preferred.

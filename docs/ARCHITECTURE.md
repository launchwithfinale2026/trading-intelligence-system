# Architecture

This document is the single source of truth for the architecture of the Trading
Intelligence System. It describes every major subsystem, why it exists, how data
flows through the system, and which parts are built today versus planned for
later phases. If code and this document disagree, this document should be
updated in the same change that changes the code.

Related: [ROADMAP.md](ROADMAP.md) for phase sequencing, [DECISIONS.md](DECISIONS.md)
for the reasoning behind specific architectural choices.

---

## 1. What this system is

A personal, human-in-the-loop trading assistant for a small group of users
(Jake + friends). It watches a curated universe of assets, finds
high-probability setups, calculates risk/reward, and sends Telegram alerts.
A human decides whether to act (`OPEN`) or skip (`IGNORE`). The system tracks
that decision and its eventual outcome so strategy performance can be measured
over time.

It is explicitly **not**:
- A SaaS platform (no public signup, no billing)
- An automated execution system (no orders are ever placed by the system)
- A high-frequency trading bot
- Connected to, or dependent on, the separate "Veronica" project

See [DECISIONS.md](DECISIONS.md) for the standing decisions that enforce these
boundaries.

---

## 2. System overview (target end-state)

```
                         +---------------------------+
                         |      ONLINE DASHBOARD      |
                         |   (Next.js + Tailwind)     |
                         |                             |
                         |   Login  ->  Profile        |
                         |         ->  Dashboard Home  |
                         |         ->  History         |
                         +--------------+--------------+
                                        |
                                 HTTPS (REST, JWT)
                                        |
                         +--------------v--------------+
                         |      TRADING BACKEND         |
                         |         (FastAPI)            |
                         |                               |
                         |  api/        auth, users,     |
                         |              dashboard,       |
                         |              signals          |
                         |  core/       config,          |
                         |              security,        |
                         |              scheduler         |
                         +----+------+------+------+-----+
                              |      |      |      |
              +---------------+  +--+--+ +-+----+ +-+-----------+
              |                  |     | |      | |             |
      +-------v------+  +--------v--+ +v------v+ +v-----------+ +v-----------+
      | Market        |  | Strategy  | | Risk   | | Portfolio  | | Feedback   |
      | Scanner        |  | Engine    | | Engine | | Tracker    | | System     |
      +-------+--------+  +-----+-----+ +---+----+ +-----+------+ +-----+------+
              |                 |            |            |             |
              +--------+--------+------------+------------+-------------+
                       |
               +-------v--------+
               |    Database     |
               | (Postgres /     |
               |  SQLite dev)    |
               +-------+---------+
                       |
               +-------v---------+
               |    Telegram      |
               |  Notifications   |
               +------------------+
```

Every box above maps to a directory under `backend/app/` (see
[Section 5](#5-directory-map)). Boxes drawn but not yet implemented are marked
"planned" in that section — the diagram shows the target, not necessarily
today's state.

---

## 3. Why each subsystem exists

| Subsystem | Why it exists |
|---|---|
| **Market Scanner** | Without a scanner, someone has to manually decide what to look at. The scanner narrows a large universe down to a small, high-quality candidate list so the strategy engine only spends effort on things worth evaluating. |
| **Strategy Engine** | Encodes the actual trading logic (momentum, breakout, ...) as discrete, testable units. Keeping strategies separate from the scanner means new strategies can be added without touching filtering logic, and vice versa. |
| **Risk Engine** | Every signal is useless without a position size and a defined loss. Centralizing sizing logic means every strategy automatically respects a user's account size and risk preference instead of each strategy re-implementing sizing. |
| **Portfolio Tracker** | Once a user opens a position, something has to watch it against the stop/target and know its current status. This is intentionally separate from "did we recommend this" (Strategy Engine) — one produces ideas, the other tracks commitments. |
| **Feedback System** | The system is only trustworthy if its track record is measurable. This subsystem is what turns "we sent 40 alerts" into "our momentum strategy has a 61% acceptance rate and a 1.8R average outcome." |
| **Telegram Bot** | The chosen notification and response channel. Telegram was picked over email/SMS because it supports fast structured replies (`OPEN`/`IGNORE`) and has a free, well-documented Bot API. See [DECISIONS.md](DECISIONS.md). |
| **Dashboard** | The control and review surface. Telegram is for real-time alerts; the dashboard is for profile configuration, reviewing history, and seeing the full account/portfolio picture that doesn't fit in a chat message. |
| **Market Data Provider interface** | Data providers change (rate limits, pricing, reliability). Wrapping `yfinance` behind an interface (`get_price`, `get_history`, `get_volume`, `get_market_status`) means swapping to Alpaca/Polygon/IBKR later touches one adapter, not every caller. |
| **Auth** | Multiple users share one deployment. Auth is what makes "isolated user data" (a core principle) enforceable rather than aspirational. |
| **Scheduler** | Scanning, strategy evaluation, and position monitoring need to run on a cadence without a human triggering them. The scheduler is the thing that turns this from a script you run by hand into a system that runs continuously. |

---

## 4. Data flow

### 4.1 Signal generation → alert → decision (primary loop)

```
 Scheduler tick
      |
      v
 Market Scanner --------> Market Data Provider (yfinance today)
      |  (liquidity, quality,        |
      |   trend, momentum filters)   v
      |                        raw price/volume/history data
      v
 Ranked candidate list  [{symbol, score}, ...]
      |
      v
 Strategy Engine (momentum, breakout, ...)
      |  evaluates each candidate against strategy conditions
      v
 Signal {symbol, direction, entry, stop_loss, target, confidence, reasoning}
      |
      v
 Risk Engine  <---- user profile (account_size, risk preference)
      |  computes position size from entry/stop distance + risk %
      v
 Sized Signal {..., position_size}
      |
      v
 Telegram Bot ----> sends formatted alert to the relevant user(s)
      |
      v
 User replies OPEN or IGNORE
      |
      v
 Telegram handler resolves: which user sent this, which profile,
 which signal is being replied to
      |
      +--> IGNORE: Feedback System records decision, no position created
      |
      +--> OPEN: Portfolio Tracker creates an active position
                        |
                        v
                  Feedback System records decision
```

### 4.2 Position monitoring (secondary loop)

```
 Scheduler tick (position monitor)
      |
      v
 Portfolio Tracker: for each open position, fetch current price
      |
      v
 Market Data Provider.get_price(symbol)
      |
      +--> price <= stop_loss  --> STOP LOSS ALERT (Telegram) + close position
      |
      +--> price >= target     --> TAKE PROFIT ALERT (Telegram) + close position
      |
      +--> thesis invalidated  --> alert user, mark for review
      |
      v
 On close: Feedback System records trade result (win/loss, R-multiple)
```

### 4.3 Dashboard read path

```
 Browser --HTTPS/JWT--> api/dashboard.py --> SQLAlchemy models --> Database
                                                                       |
                              <-- market status, active positions, ---+
                                  recent signals, performance stats
```

The dashboard never talks to the Market Data Provider, Strategy Engine, or
Telegram Bot directly — it only reads what the backend has already persisted.
This keeps the dashboard a pure read/config surface and keeps all
decision-making logic in one place (the backend).

---

## 5. Directory map

Maps every planned subsystem to its location in the codebase and current
build status.

```
backend/app/
  main.py                 FastAPI entrypoint, startup/shutdown         [BUILT — Phase 1]
  api/
    auth.py                 register / login / logout / session        [BUILT — Phase 3]
    users.py                 user + profile CRUD, isolation             [BUILT — Phase 2/3]
    dashboard.py              dashboard read endpoints                  [planned — Phase 12]
    signals.py                 signal history endpoint (GET /signals)   [BUILT — Phase 7]
    dependencies.py             get_current_user, shared deps           [BUILT — Phase 3]
  core/
    config.py                 env-based settings                       [BUILT — Phase 1]
    security.py                password hashing, token handling        [BUILT — Phase 3]
    exceptions.py               domain error types                     [BUILT — Phase 2]
    exception_handlers.py        domain error -> HTTP translation        [BUILT — Phase 3]
    scheduler.py               recurring job runner                    [BUILT — Phase 5]
  database/
    database.py                engine/session/Base                     [BUILT — Phase 1]
    models/                     SQLAlchemy models (User, Profile, ...)   [BUILT — Phase 2, grows every phase]
  repositories/                 thin per-model data access                [BUILT — Phase 2]
  services/                      isolation-enforcing business logic         [BUILT — Phase 2]
  schemas/                        Pydantic request/response models           [BUILT — Phase 2/3]
  market/
    provider.py                 MarketDataProvider interface (vendor-neutral) [BUILT — Phase 5]
    yfinance_provider.py          YFinanceProvider implementation              [BUILT — Phase 5]
    factory.py                     provider selection via config                [BUILT — Phase 5]
    scanner.py                    quality filters, ranking               [BUILT — Phase 6]
  strategies/
    base.py                       Strategy base class / Signal contract  [BUILT — Phase 7]
    momentum.py                     momentum strategy                    [BUILT — Phase 7]
    breakout.py                      breakout strategy                    [BUILT — Phase 7]
  analysis/
    scoring.py                        candidate scoring                    [BUILT — Phase 6]
    technical.py                        indicators (trend, volume, etc.)    [BUILT — Phase 6, extended Phase 7]
  risk/
    calculator.py                       position sizing                     [BUILT — Phase 8]
  portfolio/
    positions.py                        active position tracking              [planned — Phase 10]
  telegram/
    bot.py                                bot bootstrap                       [planned — Phase 4]
    handlers.py                            command + reply handlers            [planned — Phase 4/9]
  feedback/
    tracker.py                             decision + outcome tracking          [planned — Phase 11]

frontend/                                 Next.js dashboard                    [planned — Phase 12]
  app/, components/, pages/, dashboard/

tests/                                    backend test suite                  [BUILT — Phase 1, grows every phase]
```

---

## 6. Data model (current + planned)

Only `Base` (the SQLAlchemy declarative base) exists today. The model set
below is the planned shape as later phases land; this table is updated as
each phase adds tables.

| Table | Phase | Purpose | Key relationships |
|---|---|---|---|
| `users` ✅ | 2 | Login identity (username, email, password hash, telegram_id) | 1:1 with `profiles` |
| `profiles` ✅ | 2 | Per-user trading config (account_size, risk preference, style, alert preference) | belongs to `users` |
| `signals` ✅ | 7 | Every signal a strategy produced, regardless of user decision | belongs to a strategy run |
| `decisions` | 11 | A user's OPEN/IGNORE response to a signal | belongs to `users` + `signals` |
| `positions` | 10 | Active/closed positions opened from an accepted signal | belongs to `users` + `signals` |
| `trade_results` | 11 | Outcome of a closed position (win/loss, R-multiple) | belongs to `positions` |

Every user-owned table carries a `user_id` foreign key and every query is
scoped by the authenticated user — this is the mechanism behind the "every
user has isolated data" principle in [DECISIONS.md](DECISIONS.md).

---

## 7. Market Data Provider abstraction

```
                +---------------------------+
                |   MarketDataProvider       |   <-- interface (market/provider.py)
                |                             |
                |  get_price(symbol)          |
                |  get_history(symbol, range)  |
                |  get_volume(symbol)           |
                |  get_market_cap(symbol)         |
                |  get_market_status()             |
                +---------------------------+
                         ^
                         | implements
        +----------------+----------------+-----------------+
        |                |                 |                 |
+-------+------+  +-------+------+  +-------+------+  +-------+------+
| YFinance      |  | Alpaca        |  | Polygon       |  | Interactive  |
| Provider      |  | Provider       |  | Provider       |  | Brokers      |
| [BUILT first  |  | [future]        |  | [future]        |  | Provider     |
|  — Phase 5]   |  |                  |  |                  |  | [future]      |
+---------------+  +-----------------+  +-----------------+  +---------------+
```

Every caller (Scanner, Strategy Engine, Portfolio Tracker) depends only on the
`MarketDataProvider` interface, never on `yfinance` directly. Swapping
providers later is a config change plus a new adapter class, not a rewrite of
calling code.

---

## 8. Deployment topology (planned — Phase 13)

```
   Users (Telegram app)         Users (browser)
          |                            |
          v                            v
   Telegram Bot API           Frontend hosting (free tier)
          |                            |
          +-------------+--------------+
                         v
              Backend hosting (free tier)
                         |
                         v
              Managed Postgres (free tier)
```

V1 targets free-tier hosting for all three components (frontend, backend,
database) since this is a personal system for a small group, not a commercial
product. See [DECISIONS.md](DECISIONS.md) for the reasoning against
over-provisioning infrastructure this early.

---

## 9. Explicit non-goals (v1)

These are architected against, not just deprioritized — none of the current
interfaces assume they'll be added later without a deliberate decision:

- No automatic order execution (no broker "place order" call exists anywhere)
- No AI reasoning layer
- No news/sentiment ingestion
- No mobile app
- No subscription/billing system

If any of these are added later, they get their own entry in
[DECISIONS.md](DECISIONS.md) and an update to this document.

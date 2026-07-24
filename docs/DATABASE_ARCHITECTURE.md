# Database Architecture

Audit date: 2026-07-24. 10 tables across 8 migrations, verified this
session against **live Postgres 16** (not just SQLite) — `alembic upgrade
head` against a brand-new empty database applied all 8 migrations cleanly;
see `docs/DEPLOYMENT_READY_CHECKLIST.md` for that verification's full
detail. SQLite is the local-dev default (`DATABASE_URL=sqlite:///./trading.db`);
Postgres is the production target. Both are exercised — this is not an
assumption.

## Tables

| Table | Purpose | Owned by a user? |
|---|---|---|
| `users` | Login identity: username, email, bcrypt password hash, linked Telegram chat id | — (this *is* the user) |
| `profiles` | One user's trading configuration: account size, risk preference, trading style, alert preference | Yes (1:1) |
| `signals` | A trade idea a strategy produced — a market-level fact, exists independent of any user | **No** (see "Why `signals` isn't user-owned" below) |
| `decisions` | One user's OPEN/IGNORE response to one signal | Yes |
| `positions` | An active/closed position opened from an accepted signal, sized at open time | Yes |
| `trade_results` | The computed outcome (win/loss, R-multiple, P/L) of one closed position | Yes |
| `telegram_contacts` | Anyone who has ever messaged the bot, captured automatically — independent of whether they have or ever link a `users` account | No (keyed by `telegram_id`, no FK to `users`) |
| `telegram_events` | Log of outbound bot messages (alerts, startup/shutdown, position-closed) — powers `/status`'s "alerts sent today" | No (`chat_id` is a plain column, not an FK — a send can target a chat before/without a linked user) |
| `risk_policies` | Named, data-driven risk curves (`conservative`/`moderate`/`aggressive`/`experimental`) — see `app/risk/policy.py` | No — global reference/config data |
| `watchlist_symbols` | One user's custom symbol list, unioned into the scanner's universe | Yes |

## Relationships

```
users (1) ──── (1) profiles
users (1) ──── (*) decisions ──── (*) signals   [decisions.signal_id -> signals.id]
users (1) ──── (*) positions ──── (*) signals   [positions.signal_id -> signals.id]
positions (1) ──── (0/1) trade_results
users (1) ──── (*) trade_results
users (1) ──── (*) watchlist_symbols

users.telegram_id  (unique, nullable)  — the ONLY link to Telegram identity
telegram_contacts.telegram_id (unique) — independent capture, not FK'd to users
telegram_events.chat_id                — independent log, not FK'd to users
risk_policies.name (unique)            — looked up by RiskPolicyService using
                                          a user's profile.risk_preference value
                                          as the join key (a string match, not
                                          a formal FK)
```

### Why `signals` isn't user-owned

A signal ("NVDA broke out, momentum strategy, 82% confidence") is an
objective fact about the market, produced once per scan cycle regardless of
who's watching. Multiple users can each independently OPEN or IGNORE the
*same* signal — that's what `decisions` and `positions` are for. Making
`signals` user-owned would mean duplicating the same market fact once per
user, which is both wasteful and wrong (two users who both see NVDA's
breakout are looking at the same event, not two different ones). This is a
deliberate design choice carried over from earlier phases, re-verified as
still correct and still followed by all newer tables added this session
(`risk_policies`, `watchlist_symbols` didn't reintroduce the same mistake
in the other direction — they're correctly user- or system-scoped, not
signal-scoped).

## Constraints enforcing isolation (verified at the database level, not just app code)

| Table | Constraint |
|---|---|
| `users` | Unique index on `username`, `email`, `telegram_id` |
| `decisions` | Unique `(user_id, signal_id)` — one decision per user per signal |
| `positions` | Unique `(user_id, signal_id)` — one position per user per signal |
| `trade_results` | Unique `position_id` — one result per position |
| `watchlist_symbols` | Unique `(user_id, symbol)` — no duplicate entries |
| `telegram_contacts` | Unique `telegram_id` |
| Every user-owned table | `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` — deleting a user cleans up everything they own |

Confirmed by direct `psql`/`sqlite3` schema inspection this session (both
locally against SQLite throughout development, and against a live Postgres
16 database specifically for this audit), not just by reading the model
source.

## Indexes

`signals.symbol`, `signals.strategy_name`, `trade_results.strategy_name`,
`telegram_events.kind` — all indexed for the query patterns that actually
use them (scanning recent signals by symbol/strategy, computing
per-strategy performance, counting events by kind for `/status`). Every
unique constraint above is backed by a unique index (a side effect of how
SQLAlchemy/Alembic declare them, not a separate manual step).

## Data flow

**1. Market scan → signal → alert** (see `engine/pipeline.py`):
```
Scanner (universe = default symbols + every user's watchlist_symbols, unioned)
  -> per symbol: Strategy.evaluate(history) -> StrategySignal | None
  -> SignalService.record_signal() persists to `signals`
  -> for each linked user whose alert_preference and watchlist allow it:
       RiskPolicyService looks up `risk_policies` by name, sizes the position
       -> Telegram alert sent
       -> TelegramEventRepository logs the send to `telegram_events`
```

**2. User responds** (Telegram `/open`, `/ignore`, or a text reply — see
`telegram/handlers.py`):
```
DecisionService.record_decision() -> `decisions` row
  if OPEN: PositionService.open_position() -> `positions` row
```

**3. Position monitoring** (`run_position_monitor_cycle`, same pipeline):
```
For every open position: fetch current price
  -> stop/target hit? -> PositionService.close_position()
  -> FeedbackService.record_trade_result() -> `trade_results` row
  -> Telegram "position closed" alert -> logged to `telegram_events`
```

**4. Dashboard reads** (frontend, via the API — never touches the DB
directly, never touches the market data provider or Telegram bot directly):
```
GET /portfolio/positions, /portfolio/decisions, /signals, /feedback/performance
  -> all scoped to the authenticated user where the data is user-owned
```

## Local development database behavior — confirmed intentional

- SQLite is the default (`sqlite:///./trading.db`, relative to `backend/`
  as the working directory — see `docs/LOCAL_DEVELOPMENT.md`'s
  troubleshooting section for what breaks if you run from the wrong
  directory).
- Schema is **always** Alembic-managed, in every environment — there is no
  `Base.metadata.create_all()` call anywhere in application code (only in
  test fixtures, which deliberately use it for speed against a throwaway
  in-memory database, not to describe real behavior).
- `check_same_thread: False` is added to the SQLite connection only —
  correctly gated by `settings.database_url.startswith("sqlite")`, absent
  for Postgres. Confirmed this is the *only* SQLite-conditional code left
  in the entire backend (grepped `backend/app` for `sqlite`; the only other
  hit is the default `DATABASE_URL` value itself, which is just a default,
  not an assumption baked into logic).

## No accidental SQLite assumptions remain (confirmed this audit)

Grepped the full backend and Alembic tree for `sqlite`. Two hits, both
correct and necessary (see above) — zero hardcoded SQLite-only syntax in
any migration (all render as valid Postgres DDL, live-verified) and zero
SQLite-only code paths in application logic.

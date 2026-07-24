# Feature Audit

Audit date: 2026-07-24. Every claim below is backed by a specific test file
or a specific live check performed this session — not assumed from
reading code.

## Watchlist

| Capability | Status | Evidence |
|---|---|---|
| Add symbol | **DONE** | `POST /users/me/watchlist` — `test_watchlist_api.py::test_add_symbol_normalizes_to_uppercase`, live-verified via curl this session (added NVDA to a real account, confirmed in raw Postgres row) |
| Remove symbol | **DONE** | `DELETE /users/me/watchlist/{symbol}` — `test_watchlist_api.py::test_remove_symbol` |
| Retrieve symbols | **DONE** | `GET /users/me/watchlist` — same file |
| User-specific data | **DONE** | Unique `(user_id, symbol)` DB constraint; `test_user_isolation.py::test_watchlists_are_fully_isolated` proves User B can't see or delete User A's symbols (404, not leaked) |
| Wired into the scanner | **DONE** | `engine/pipeline.py::run_scan_cycle` unions every user's watchlist into the scan universe and only alerts a user for symbols on their own list (empty watchlist = watch the system default, unchanged legacy behavior) — `test_telegram_end_to_end.py`, `test_pipeline.py` |
| **Frontend UI** | **NOT BUILT** | Grepped `frontend/lib/api.ts` for `watchlist` — zero matches. No API client function, no page, no way to view or manage a watchlist except direct API calls (curl/Postman). Backend is complete and tested; the dashboard has no visibility into this feature at all. **Flagging, not building** — a new page is feature work, out of this audit's stated scope ("do NOT add unnecessary features"). Your call whether this blocks Phase 1 completion. |

## Risk Engine

| Capability | Status | Evidence |
|---|---|---|
| Fixed-preference policies load (conservative/moderate/aggressive) | **DONE** | Seeded in `risk_policies` table (migration `09fcbf085b28`); `RiskPolicyService` reads them at runtime, falls back to hardcoded percents if unseeded — `test_risk_policy_service.py` |
| Data-driven "experimental" curve (scaled by account size) | **DONE** | Piecewise-linear interpolation in `risk/policy.py`; `test_risk_policy.py` covers flat-before-first-point, flat-after-last-point, linear interpolation, unsorted input, empty-input rejection |
| Calculations produce expected results | **DONE** | `test_risk_calculator.py` — every case is a hand-computed expected value (e.g. "account=1000, 2% risk → $20 budget; entry 175, stop 168 → $7/share; floor(20/7) = 2 shares"), not just "does it run" |
| Edge cases handled | **DONE** | Zero-shares-when-budget-too-small, non-positive account size rejected, non-positive entry rejected, stop==entry rejected (zero risk per share, would divide by zero), short positions (stop above entry) use absolute distance correctly |
| Live-verified against real Postgres | **DONE** | This session: registered a live account with `risk_preference: experimental`, confirmed the value round-tripped correctly through a real Postgres database and back through the API |

## Position Management

| Capability | Status | Evidence |
|---|---|---|
| Positions save correctly | **DONE** | `test_position_service.py::test_open_position_sizes_from_current_profile` — entry/stop/target captured at open time (not read live off the signal later, so a user's risk sizing reflects their profile *at the moment they opened*, deliberately) |
| Duplicate prevention | **DONE** | One position per `(user, signal)`, enforced at both the DB (unique constraint) and service layer (`ConflictError`) — `test_open_position_rejects_duplicate_for_same_user_and_signal` |
| Zero-affordable-shares handled | **DONE** | `RiskLimitError` raised rather than silently opening a 0-share position — `test_open_position_rejects_when_risk_budget_affords_zero_shares` |
| Updates (closing) work | **DONE** | `check_and_close_open_positions` correctly closes on stop hit, target hit, leaves open between bounds, handles short positions' inverted stop/target logic, and skips (doesn't crash on) a symbol with no available price — all 6 scenarios individually tested in `test_position_service.py` |
| Calculations remain accurate through close | **DONE** | Close price, `closed_at` timestamp, and resulting `PositionStatus` all asserted per scenario |

## Pipeline / Intelligence Engine

| Capability | Status | Evidence |
|---|---|---|
| Inputs accepted | **DONE** | `run_scan_cycle` takes a market data provider, a strategy list, and a universe — all overridable for testing, defaulting to the real `YFinanceProvider` + 3 registered strategies + default universe in production |
| Processing works | **DONE** | Full chain — Scanner (quality-filters candidates) → each Strategy's `evaluate()` (momentum, breakout, momentum_breakout — all deterministic, no randomness or network calls in the decision logic itself) → `SignalService.record_signal()` → `RiskPolicyService.size_position()` → Telegram alert — exercised end-to-end in `test_telegram_end_to_end.py::test_pipeline_end_to_end_routes_alert_to_correct_chat_id_only` with a fake provider producing a real qualifying signal |
| Outputs are predictable | **DONE** | Strategies are pure functions of (symbol, price history) — same input always produces the same signal or `None`, verified by per-strategy test suites (`test_momentum_strategy.py`, `test_breakout_strategy.py`, `test_momentum_breakout_strategy.py`) with hand-picked fixtures for both the fires-a-signal case and every individual reject condition |
| Failure isolation | **DONE** | One symbol's `MarketDataError` doesn't abort the scan (`test_scanner.py`, `test_scanner_worker.py::test_run_forever_continues_after_a_cycle_raises`); one user's Telegram delivery failure doesn't block another user's alert — new this audit, `test_telegram_end_to_end.py::test_one_users_delivery_failure_does_not_block_another_users_alert` |
| Position monitoring loop | **DONE** | Separate cycle (`run_position_monitor_cycle`), same failure-isolation properties, covered by `test_position_monitor.py` |

## Other product surfaces (not explicitly named in the audit's 4 features, included for completeness)

| Feature | Status | Notes |
|---|---|---|
| Authentication (register/login/logout, JWT) | **DONE** | See `docs/BACKEND_AUDIT.md` and `tests/test_auth_api.py`, `test_users_api.py` — includes expired-token rejection, added this audit |
| User isolation (cross-cutting) | **DONE** | New dedicated suite this audit: `tests/test_user_isolation.py`, 7 tests across profile/watchlist/positions/decisions/Telegram-chat-id/unauthenticated-access |
| Telegram bot: commands (`/start`, `/status`, `/ping`, `/help`, `/profile`, `/positions`, `/open`, `/ignore`) | **DONE** (code) / ⚠️ **BLOCKED** (live) | All fully implemented and tested (`test_telegram_handlers.py`, `test_telegram_end_to_end.py`). Live bot process currently can't run: the token in `.env`, which worked earlier this session, now gets `InvalidToken` from Telegram — revoked or regenerated externally, not a code issue. See `docs/PHASE_1_COMPLETION_REPORT.md`. |
| Dashboard (market status, positions, recent signals, performance) | **DONE** | `app/page.tsx` — loading/empty/error states all present, live-verified in browser with zero console errors |
| History page (decisions + outcomes) | **DONE** | `app/history/page.tsx` — same state coverage |
| Profile page (edit risk/trading/alert preference) | **DONE** | `app/profile/page.tsx`, includes the new "Experimental" risk option |
| Login/Register pages | **DONE** | Both had the same render-time-redirect React error (`Cannot update a component while rendering a different component`) — login fixed in an earlier session, **register fixed this audit** (same pattern, same fix). Both live-verified with zero console errors after the fix. |

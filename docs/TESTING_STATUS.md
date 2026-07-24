# Testing Status

Audit date: 2026-07-24. Full suite run fresh for this document — not
pulled from memory of an earlier run.

## Headline numbers

```
$ backend/venv/bin/python -m pytest -q      (run from repo root)
217 passed, 1 warning in ~25s
```

- **0 failed**
- **0 skipped**
- **0 xfail / ignored** — no test in the suite is marked skip, xfail, or
  otherwise excluded. Grepped for `@pytest.mark.skip`, `pytest.mark.xfail`,
  `pytest.importorskip` — zero matches anywhere in `tests/`.
- The 1 warning is a `StarletteDeprecationWarning` about `httpx` vs
  `httpx2` in FastAPI's `TestClient` — a library deprecation notice, not a
  test failure or a code issue in this project.

Frontend: `npm run test` (vitest) — **5 passed**, 0 failed. `npx tsc
--noEmit` — clean. `npm run build` — succeeds.

## Coverage against the minimum-required list

| Required area | Covered? | Files |
|---|---|---|
| Authentication | ✅ | `test_auth_api.py` (11), `test_users_api.py` (5, incl. expired-token — added this audit) |
| Database | ✅ | Exercised indirectly by every service/API test (all use a real, migrated schema via `db_session`/`client` fixtures); schema itself verified against live Postgres this session (see `docs/DEPLOYMENT_READY_CHECKLIST.md`) |
| API routes | ✅ | Every route has a dedicated test file — see the full table in `docs/BACKEND_AUDIT.md` |
| Risk calculations | ✅ | `test_risk_calculator.py` (8), `test_risk_policy.py` (7), `test_risk_policy_service.py` (4) |
| User isolation | ✅ | `test_user_isolation.py` (7, new this audit — a dedicated cross-cutting suite) plus isolation assertions embedded in `test_watchlist_api.py`, `test_users_api.py` |
| Telegram logic | ✅ | `test_telegram_handlers.py` (26 — per-handler units), `test_telegram_end_to_end.py` (7, new this audit — bot construction, full pipeline routing, failure isolation, alert→reply→decision round trip) |

## Full per-file breakdown

| File | Tests |
|---|---|
| `test_telegram_handlers.py` | 26 |
| `test_technical.py` | 18 |
| `test_market_provider.py` | 11 |
| `test_auth_api.py` | 11 |
| `test_pipeline.py` | 10 |
| `test_user_service.py` | 8 |
| `test_risk_calculator.py` | 8 |
| `test_position_service.py` | 8 |
| `test_watchlist_api.py` | 7 |
| `test_user_isolation.py` | 7 |
| `test_telegram_end_to_end.py` | 7 |
| `test_scoring.py` | 7 |
| `test_risk_policy.py` | 7 |
| `test_scanner.py` | 6 |
| `test_momentum_breakout_strategy.py` | 6 |
| `test_filtering.py` | 6 |
| `test_feedback_service.py` | 6 |
| `test_config.py` | 6 |
| `test_users_api.py` | 5 |
| `test_position_monitor.py` | 5 |
| `test_momentum_strategy.py` | 5 |
| `test_scanner_worker.py` | 4 |
| `test_risk_policy_service.py` | 4 |
| `test_portfolio_and_market_api.py` | 4 |
| `test_decision_service.py` | 4 |
| `test_breakout_strategy.py` | 4 |
| `test_signals_api.py` | 3 |
| `test_scheduler.py` | 3 |
| `test_feedback_api.py` | 3 |
| `test_alert_formatting.py` | 3 |
| `test_signal_service.py` | 2 |
| `test_market_factory.py` | 2 |
| `test_health.py` | 1 |

## Added this audit (19 new tests, all passing)

- `test_user_isolation.py` — new file, 7 tests (didn't exist before; explicitly requested)
- `test_telegram_end_to_end.py` — new file, 7 tests (didn't exist before; explicitly requested)
- `test_auth_api.py` — 5 new tests (invalid email/password/username, missing profile, duplicate email)
- `test_users_api.py` — 1 new test (expired token rejection)
- `test_config.py` — was already new from an earlier session this week; unchanged this audit

## Known non-issues

- No SQLite-vs-Postgres test duplication: the suite runs against SQLite
  (fast, in-memory, hermetic) for every test; Postgres compatibility is
  verified separately and explicitly (`docs/DEPLOYMENT_READY_CHECKLIST.md`),
  not by running the whole suite twice. This is a deliberate, documented
  choice (see `tests/conftest.py`'s docstring), not a gap.
- Frontend has 5 tests (`frontend/lib/api.test.ts`) — thin by backend
  standards, but the frontend is a straightforward API-consuming UI with no
  complex client-side logic to unit test; its correctness is mostly proven
  by (a) TypeScript, (b) the backend contract it calls being tested, and
  (c) live browser verification performed this session (zero console
  errors across login/register/dashboard/logout flows).

## Real gaps found and closed this audit

1. Registration accepted malformed input in principle (Pydantic schema
   validation existed) but nothing proved it — 4 tests added.
2. Nothing proved an expired JWT gets rejected (only a garbage-string token
   was tested) — 1 test added.
3. No single test suite proved cross-user isolation as one coherent
   end-to-end property (it was previously implied by scattered individual
   assertions) — `test_user_isolation.py` added.
4. No end-to-end Telegram test existed that exercised the *actual* wired
   pipeline (scan → signal → alert) with two users and confirmed correct
   per-user routing and failure isolation in one place —
   `test_telegram_end_to_end.py` added.

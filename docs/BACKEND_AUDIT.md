# Backend Audit

Audit date: 2026-07-24. Every route below was enumerated by importing the
real `app.main:app` and walking its route table live (not read off the
source and assumed correct) — see the exact commands used at the bottom of
this file if you want to reproduce it.

## Startup, middleware, routers, CORS, database (`backend/app/main.py`)

| Aspect | Finding |
|---|---|
| Startup events | `lifespan` context manager: logs startup, starts the APScheduler (`core/scheduler.py`), conditionally registers scan/position-monitor jobs only if `ENABLE_SCHEDULED_SCANNING=true` (off by default). Shuts the scheduler down cleanly on exit. |
| Hidden startup errors | None found. Also added this audit: `assert_production_secret_key_is_set(settings)` runs at **import time**, before the `FastAPI()` instance is even constructed — refuses to start if `ENVIRONMENT=production` with the default insecure `SECRET_KEY`. Verified live: raises `RuntimeError` with a clear message. |
| Middleware | `CORSMiddleware` only. `allow_origins` parsed from `CORS_ALLOWED_ORIGINS` (comma-separated, whitespace-trimmed, empties filtered), `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. |
| Routers | 7 routers registered: `auth`, `users`, `signals`, `feedback`, `portfolio`, `market`, `watchlist`. All present and correctly included — confirmed by walking `app.routes` on the live app object, not just reading the `include_router` calls. |
| CORS | Comma-separated origin list supports multiple production frontends. Live-verified this audit (deployment session): `OPTIONS /auth/register` with `Origin: http://localhost:3000` returns a correct preflight response. |
| Database initialization | Explicitly **not** done in `main.py` — schema is Alembic-managed (`alembic upgrade head`), never `Base.metadata.create_all()` in application code. `database.py` builds the engine once at import time from `settings.database_url`, with `check_same_thread: False` conditionally added only for SQLite. |
| Exception handling | `register_exception_handlers(app)` maps 4 domain exceptions to HTTP status codes: `NotFoundError`→404, `ConflictError`→409, `ForbiddenError`→403, `UnauthorizedError`→401. Every handler returns `{"detail": str(exc)}`. Unmapped exceptions (bugs) surface as FastAPI's default 500 — no code found that swallows errors silently. |

## Route-by-route checklist

| Route | Purpose | Auth required? | DB interaction? | Test coverage |
|---|---|---|---|---|
| `GET /health` | Liveness probe for deploy platforms/load balancers | No | No | `test_health.py` |
| `POST /auth/register` | Create a new user + profile | No (that's the point) | Write: `users`, `profiles` | `test_auth_api.py` (create, duplicate username/email rejected, invalid email/password/username/missing-profile all rejected with 422) |
| `POST /auth/login` | Exchange username+password for a JWT | No (credentials are the auth) | Read: `users` | `test_auth_api.py` (correct creds → token, wrong password → 401, unknown user → 401) |
| `POST /auth/logout` | Documented no-op (stateless JWT, nothing server-side to invalidate) | No | No | `test_auth_api.py` |
| `GET /users/me` | Read your own account + profile | Yes (Bearer JWT) | Read: `users`, `profiles` | `test_users_api.py` (own data returned, 401 with no/invalid/**expired** token — expired-token test added this audit) |
| `PATCH /users/me/profile` | Update your own risk/trading/alert preferences | Yes | Write: `profiles` | `test_users_api.py` (own update applies, confirmed **not** visible to a second user) |
| `GET /signals` | List recent market signals (system-wide facts, not user-owned — see `docs/DATABASE_ARCHITECTURE.md`) | Yes | Read: `signals` | `test_signals_api.py` |
| `GET /feedback/performance` | Aggregate win-rate/R-multiple by strategy, across all users (intentionally global — this is the system's track record, not personal data) | Yes (any authenticated user; response contains no per-user or per-trade financial detail) | Read: `signals`, `decisions`, `trade_results` | `test_feedback_api.py`, `test_feedback_service.py` |
| `GET /portfolio/positions` | List **your own** positions | Yes | Read: `positions`, scoped by `user_id` | `test_portfolio_and_market_api.py`, `test_user_isolation.py` |
| `GET /portfolio/decisions` | List **your own** OPEN/IGNORE decisions | Yes | Read: `decisions`, scoped by `user_id` | `test_portfolio_and_market_api.py`, `test_user_isolation.py` |
| `GET /market/status` | Is the market open right now | Yes | No (calls the market data provider, not the DB) | `test_portfolio_and_market_api.py` |
| `GET /users/me/watchlist` | List **your own** watchlist symbols | Yes | Read: `watchlist_symbols`, scoped by `user_id` | `test_watchlist_api.py`, `test_user_isolation.py` |
| `POST /users/me/watchlist` | Add a symbol to **your own** watchlist | Yes | Write: `watchlist_symbols` | `test_watchlist_api.py` (uppercase normalization, duplicate → 409) |
| `DELETE /users/me/watchlist/{symbol}` | Remove a symbol from **your own** watchlist | Yes | Delete: `watchlist_symbols`, scoped by `user_id` | `test_watchlist_api.py`, `test_user_isolation.py` (confirmed User B cannot delete User A's symbol — 404, not 200/403, since it doesn't exist *for that user*) |

**Authorization pattern used everywhere**: every authenticated route takes
`current_user: User = Depends(get_current_user)` (`api/dependencies.py`,
which decodes the JWT and loads the user by id) and every query is scoped
to `current_user.id` at the repository/service layer — there is no route
anywhere that accepts a client-supplied user id for reading or writing
another user's data. Confirmed by reading every route file, not just
grepping for the pattern.

## Findings from this audit

- No hidden/silent startup failures found.
- No route found that skips authentication where it should be required.
- No route found that trusts a client-supplied user id instead of the JWT's.
- One real gap fixed: registration's Pydantic-level input validation
  (`UserRegister` schema — `EmailStr`, `Field(min_length=...)`, username
  regex) existed but had **zero test coverage** proving invalid input
  actually gets rejected. Added 4 tests to `test_auth_api.py`.
- One real gap fixed: no test proved an **expired** JWT is rejected (only
  a malformed one was tested). Added `test_rejects_expired_token` to
  `test_users_api.py`.

## How the route table above was produced (reproducible)

```python
from app.main import app
for route in app.routes:
    if type(route).__name__ == "_IncludedRouter":
        for r in route.original_router.routes:
            print(sorted(r.methods - {"HEAD", "OPTIONS"}), r.path)
```

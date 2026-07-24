# Dashboard (frontend)

Next.js (App Router) + TypeScript + Tailwind CSS dashboard for the Trading
Intelligence System backend. Talks to the FastAPI backend over its REST API
using a JWT bearer token stored in `localStorage`.

## Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at the backend, defaults to localhost:8000
npm run dev
```

Requires the backend running (see `backend/README.md`) with CORS configured
to allow this app's origin — the backend's default `CORS_ALLOWED_ORIGINS`
already includes `http://localhost:3000`.

## Pages

- `/login`, `/register` — auth
- `/` — dashboard home: market status, active positions, recent signals,
  performance by strategy
- `/profile` — view/edit account size, risk preference, trading style,
  alert preference
- `/history` — past signals, decisions, and their outcomes

All pages except `/login` and `/register` are wrapped in `ProtectedRoute`
(`components/ProtectedRoute.tsx`), which redirects to `/login` if there's no
authenticated user.

## Testing

```bash
npm run lint      # ESLint
npx tsc --noEmit  # type-check
npm run test      # Vitest — unit tests for lib/api.ts
npm run build     # production build (also type-checks)
```

There is no component/E2E test suite yet (Jest/RTL or Playwright) — current
coverage is limited to the API client's request/error-handling logic.
Manual verification was done via `curl` against a running backend (including
CORS headers) rather than an interactive browser session; see
docs/ROADMAP.md Phase 12 for what was and wasn't verified.

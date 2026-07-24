# Build context is the repo root (requirements.txt lives there, alongside
# backend/) — see docker-compose.yml or `docker build -f backend/Dockerfile .`
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg2-binary's runtime (libpq) — kept minimal.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ ./backend/
WORKDIR /app/backend

EXPOSE 8000

# Applies pending Alembic migrations, then starts the API. Never
# Base.metadata.create_all() in production — see Decision 12.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

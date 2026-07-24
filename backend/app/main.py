import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, feedback, market, portfolio, signals, users, watchlist
from app.core.config import assert_production_secret_key_is_set, get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.scheduler import get_scheduler

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

assert_production_secret_key_is_set(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Schema is managed by Alembic migrations (`alembic upgrade head`), not
    # created here — see backend/README or docs/ARCHITECTURE.md.
    logger.info("%s starting up (env=%s)", settings.app_name, settings.environment)
    scheduler = get_scheduler()
    scheduler.start()

    if settings.enable_scheduled_scanning:
        from app.engine.pipeline import run_position_monitor_cycle_sync, run_scan_cycle_sync

        scheduler.add_interval_job(
            run_scan_cycle_sync, seconds=settings.scan_interval_seconds, job_id="scan_cycle"
        )
        scheduler.add_interval_job(
            run_position_monitor_cycle_sync,
            seconds=settings.position_monitor_interval_seconds,
            job_id="position_monitor_cycle",
        )
        logger.info(
            "scheduled scanning enabled: scan every %ss, position monitor every %ss",
            settings.scan_interval_seconds,
            settings.position_monitor_interval_seconds,
        )
    else:
        logger.info("scheduled scanning disabled (ENABLE_SCHEDULED_SCANNING=false)")

    yield
    scheduler.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(signals.router)
app.include_router(feedback.router)
app.include_router(portfolio.router)
app.include_router(market.router)
app.include_router(watchlist.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "online"}

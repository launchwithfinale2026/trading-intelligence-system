import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, users
from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.scheduler import get_scheduler

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Schema is managed by Alembic migrations (`alembic upgrade head`), not
    # created here — see backend/README or docs/ARCHITECTURE.md.
    logger.info("%s starting up (env=%s)", settings.app_name, settings.environment)
    scheduler = get_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_exception_handlers(app)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "online"}

"""Standalone scanner worker process.

Runs the scan-and-alert and position-monitor cycles continuously and
independently of both the FastAPI app and the Telegram bot process — same
reasoning as telegram/bot.py: a "run forever" background loop has a
different lifecycle than a request/response web server, so it's its own
process rather than bolted onto app startup.

    python -m app.engine.worker

This is separate from (and doesn't require) core.scheduler / main.py's
opt-in ENABLE_SCHEDULED_SCANNING flag, which embeds the same cycles inside
the API process instead — two ways to run the same work, pick whichever
fits your deployment (see docs/DEPLOYMENT.md).

Requires no credentials to run: run_scan_cycle_sync()/
run_position_monitor_cycle_sync() no-op safely (logged, not raised) when
TELEGRAM_BOT_TOKEN isn't set, so this worker can start and loop correctly
before a bot exists.
"""

import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.engine.pipeline import run_position_monitor_cycle_sync, run_scan_cycle_sync

logger = logging.getLogger(__name__)


def _run_one_cycle() -> None:
    try:
        signals_produced = run_scan_cycle_sync()
        logger.info("scan cycle complete: %s signal(s) produced", signals_produced)
    except Exception:
        logger.exception("scan cycle failed")

    try:
        positions_closed = run_position_monitor_cycle_sync()
        logger.info("position monitor cycle complete: %s position(s) closed", positions_closed)
    except Exception:
        logger.exception("position monitor cycle failed")


def run_forever(*, max_iterations: int | None = None) -> int:
    """Runs scan + position-monitor cycles on a loop until interrupted, or
    until `max_iterations` cycles have run (used by tests — real usage
    passes None and runs until the process is stopped).

    A failure in either cycle is logged and the loop continues — one bad
    cycle (a data-provider outage, a transient DB error) must never take
    the whole worker down. Returns the number of cycles completed.
    """
    settings = get_settings()
    interval = settings.scan_interval_seconds
    iterations = 0

    logger.info("scanner worker starting (interval=%ss)", interval)
    try:
        while max_iterations is None or iterations < max_iterations:
            _run_one_cycle()
            iterations += 1
            if max_iterations is None or iterations < max_iterations:
                time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("scanner worker stopping (interrupted)")

    return iterations


if __name__ == "__main__":
    _settings = get_settings()
    configure_logging(_settings.log_level)
    run_forever()

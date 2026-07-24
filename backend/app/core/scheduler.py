"""Recurring job runner.

A thin wrapper around APScheduler's BackgroundScheduler. No jobs are
registered here — this is deliberately just the skeleton; the market
scanner (Phase 6) and position monitor (Phase 10) register their own jobs
against this scheduler once they exist, instead of this module knowing
about them.
"""

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self) -> None:
        self._scheduler = BackgroundScheduler()

    def add_interval_job(self, func: Callable[[], None], *, seconds: int, job_id: str) -> None:
        self._scheduler.add_job(func, "interval", seconds=seconds, id=job_id, replace_existing=True)
        logger.info("registered job %r every %ss", job_id, seconds)

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("scheduler started")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("scheduler stopped")


_scheduler = Scheduler()


def get_scheduler() -> Scheduler:
    return _scheduler

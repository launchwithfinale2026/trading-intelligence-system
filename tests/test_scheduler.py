import time

from app.core.scheduler import Scheduler


def test_scheduler_runs_registered_job() -> None:
    scheduler = Scheduler()
    calls: list[int] = []

    scheduler.add_interval_job(lambda: calls.append(1), seconds=1, job_id="test-job")
    scheduler.start()
    try:
        time.sleep(1.5)
    finally:
        scheduler.shutdown()

    assert len(calls) >= 1


def test_scheduler_start_is_idempotent() -> None:
    scheduler = Scheduler()
    scheduler.start()
    try:
        scheduler.start()  # must not raise
        assert scheduler._scheduler.running is True
    finally:
        scheduler.shutdown()


def test_scheduler_shutdown_is_idempotent() -> None:
    scheduler = Scheduler()
    scheduler.start()
    scheduler.shutdown()
    scheduler.shutdown()  # must not raise

    assert scheduler._scheduler.running is False

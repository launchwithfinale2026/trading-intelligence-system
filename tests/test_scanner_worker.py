import pytest

from app.engine import worker


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: None)


def test_run_forever_runs_the_requested_number_of_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    scan_calls = []
    monitor_calls = []
    monkeypatch.setattr(worker, "run_scan_cycle_sync", lambda: scan_calls.append(1) or 0)
    monkeypatch.setattr(worker, "run_position_monitor_cycle_sync", lambda: monitor_calls.append(1) or 0)

    completed = worker.run_forever(max_iterations=3)

    assert completed == 3
    assert len(scan_calls) == 3
    assert len(monitor_calls) == 3


def test_run_forever_continues_after_a_cycle_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = {"n": 0}

    def flaky_scan() -> int:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated provider outage")
        return 0

    monkeypatch.setattr(worker, "run_scan_cycle_sync", flaky_scan)
    monkeypatch.setattr(worker, "run_position_monitor_cycle_sync", lambda: 0)

    completed = worker.run_forever(max_iterations=3)

    assert completed == 3  # the loop did not stop after the first cycle's exception
    assert call_count["n"] == 3


def test_run_forever_does_not_sleep_after_the_final_iteration(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls = []
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(worker, "run_scan_cycle_sync", lambda: 0)
    monkeypatch.setattr(worker, "run_position_monitor_cycle_sync", lambda: 0)

    worker.run_forever(max_iterations=3)

    assert len(sleep_calls) == 2  # slept between cycles 1->2 and 2->3, not after the 3rd


def test_run_forever_with_zero_max_iterations_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "run_scan_cycle_sync", lambda: (_ for _ in ()).throw(AssertionError("should not run")))

    completed = worker.run_forever(max_iterations=0)

    assert completed == 0

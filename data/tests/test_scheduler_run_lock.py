from scheduler.run_lock import SchedulerRunLock


def test_only_one_process_lock_can_be_held(tmp_path) -> None:
    path = tmp_path / "tier1.lock"
    first = SchedulerRunLock.try_acquire(path)
    assert first is not None
    try:
        assert SchedulerRunLock.try_acquire(path) is None
    finally:
        first.release()

    second = SchedulerRunLock.try_acquire(path)
    assert second is not None
    second.release()

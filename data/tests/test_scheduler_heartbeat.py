import json
from datetime import UTC, datetime, timedelta

from scheduler.heartbeat import SCHEMA_VERSION, SchedulerHeartbeat


def test_heartbeat_records_running_and_stopped_state_atomically(tmp_path) -> None:
    moments = iter([
        datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        datetime(2026, 8, 1, 12, 1, tzinfo=UTC),
        datetime(2026, 8, 1, 12, 2, tzinfo=UTC),
    ])
    target = tmp_path / "heartbeat.json"
    heartbeat = SchedulerHeartbeat(target, now=lambda: next(moments))

    heartbeat.start()
    started = json.loads(target.read_text())
    heartbeat.pulse()
    running = json.loads(target.read_text())
    heartbeat.stop()
    stopped = json.loads(target.read_text())

    assert started["schemaVersion"] == SCHEMA_VERSION
    assert running["status"] == "RUNNING"
    assert running["startedAt"] == started["startedAt"]
    assert datetime.fromisoformat(running["lastHeartbeatAt"]) == (
        datetime.fromisoformat(started["lastHeartbeatAt"]) + timedelta(minutes=1)
    )
    assert stopped["status"] == "STOPPED"
    assert not target.with_suffix(".json.tmp").exists()

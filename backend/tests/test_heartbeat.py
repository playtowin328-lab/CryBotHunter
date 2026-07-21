from datetime import datetime, timedelta, timezone

from app.services.heartbeat import heartbeat_transition


def test_heartbeat_transition_alerts_once_and_reports_recovery():
    now = datetime.now(timezone.utc)
    old = now - timedelta(seconds=181)
    fresh = now - timedelta(seconds=10)

    assert heartbeat_transition(last_seen=old, stale_alerted=False, now=now, stale_seconds=180) == "STALE"
    assert heartbeat_transition(last_seen=old, stale_alerted=True, now=now, stale_seconds=180) is None
    assert heartbeat_transition(last_seen=fresh, stale_alerted=True, now=now, stale_seconds=180) == "RECOVERED"
    assert heartbeat_transition(last_seen=fresh, stale_alerted=False, now=now, stale_seconds=180) is None

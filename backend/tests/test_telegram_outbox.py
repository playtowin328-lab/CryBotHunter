from app.services.telegram_outbox import retry_delay_seconds


def test_outbox_retry_uses_capped_exponential_backoff():
    assert [retry_delay_seconds(attempt) for attempt in range(1, 6)] == [5, 10, 20, 40, 80]
    assert retry_delay_seconds(100) == 300

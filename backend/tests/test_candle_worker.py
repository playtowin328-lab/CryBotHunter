from app.candle_worker import _next_rate_limit_delay


def test_rate_limit_backoff_doubles_and_caps_at_thirty_minutes():
    assert _next_rate_limit_delay(300, 300) == 600
    assert _next_rate_limit_delay(600, 300) == 1200
    assert _next_rate_limit_delay(1200, 300) == 1800
    assert _next_rate_limit_delay(1800, 300) == 1800

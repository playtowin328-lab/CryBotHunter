from app.services.performance_guard import PerformanceGuardService


def test_loss_streak_count_stops_at_first_win():
    assert PerformanceGuardService().loss_streak([-1, -2, 3, -4]) == 2
    assert PerformanceGuardService().loss_streak([5, -1, -2]) == 0

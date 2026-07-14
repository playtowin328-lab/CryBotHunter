from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

pytest.importorskip("gymnasium")
check_env = pytest.importorskip("stable_baselines3.common.env_checker").check_env

from app.services.rl_environment import CryptoTradingEnv, build_feature_frame


def candles(count: int, growth: float = 0.001):
    price = 100.0
    rows = []
    for index in range(count):
        price *= 1 + growth
        rows.append(
            SimpleNamespace(
                timestamp=datetime.now(timezone.utc) + timedelta(hours=index),
                open=price * 0.999,
                high=price * 1.003,
                low=price * 0.997,
                close=price,
                volume=10_000 + (index % 31) * 100,
            )
        )
    return rows


def run_actions(env: CryptoTradingEnv, action_for_step):
    observation, _ = env.reset()
    terminated = False
    truncated = False
    info = env.metrics()
    step = 0
    while not (terminated or truncated):
        observation, _, terminated, truncated, info = env.step(action_for_step(step))
        step += 1
    return info


def test_rl_environment_matches_gymnasium_contract():
    env = CryptoTradingEnv(build_feature_frame(candles(300)))
    check_env(env, warn=True)


def test_long_policy_profits_on_rising_market_after_costs():
    env = CryptoTradingEnv(build_feature_frame(candles(300, growth=0.002)), fee_rate=0.0004, slippage_bps=2)

    metrics = run_actions(env, lambda _step: 1)

    assert metrics["return_percent"] > 0
    assert metrics["trades"] == 1


def test_churning_flat_market_loses_to_fees_and_slippage():
    env = CryptoTradingEnv(build_feature_frame(candles(300, growth=0.0)), fee_rate=0.0004, slippage_bps=2)

    metrics = run_actions(env, lambda step: 1 if step % 2 == 0 else 2)

    assert metrics["return_percent"] < 0
    assert metrics["trades"] > 10

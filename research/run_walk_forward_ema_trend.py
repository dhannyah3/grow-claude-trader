"""
Walk-forward validation for EMA Trend Continuation.
"""

from research.ema_trend_continuation_strategy import (
    EMATrendContinuationStrategy,
)
from research.walk_forward_validator import (
    WalkForwardValidator,
)


symbols = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "LT",
    "AXISBANK",
    "ITC",
    "BHARTIARTL",
]


parameter_grid = {
    "stop_atr_multiplier": [
        1.0,
        1.2,
        1.5,
    ],
    "target_atr_multiplier": [
        2.0,
        2.5,
        3.0,
    ],
    "minimum_rsi": [
        50,
        55,
        60,
    ],
    "maximum_rsi": [
        70,
        75,
    ],
    "maximum_ema_distance_percent": [
        0.20,
        0.30,
        0.50,
    ],
    "minimum_volume_ratio": [
        0.8,
        1.0,
        1.2,
    ],
    "pullback_lookback_candles": [
        3,
        5,
        7,
    ],
}


validator = WalkForwardValidator(
    strategy_factory=EMATrendContinuationStrategy,
    parameter_grid=parameter_grid,
    symbols=symbols,
    train_days=120,
    test_days=30,
    step_days=30,
    interval_name="5m",
    year=2025,
    minimum_training_trades=20,
    minimum_test_trades=3,
)


print()
print("=" * 80)
print("EMA TREND CONTINUATION WALK-FORWARD VALIDATION")
print("=" * 80)


results = validator.run()


print()
print("=" * 80)
print("FINAL RESULT")
print("=" * 80)
print(results)
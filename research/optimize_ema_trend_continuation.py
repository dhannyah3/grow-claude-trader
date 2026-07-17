"""
Optimizer for EMA Trend Continuation Strategy.
"""

from research.dataset_builder import DatasetBuilder
from research.ema_trend_continuation_strategy import (
    EMATrendContinuationStrategy,
)
from research.strategy_optimizer import (
    StrategyOptimizer,
)


builder = DatasetBuilder()

datasets = {}

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

print()
print("=" * 80)
print("LOADING DATASETS")
print("=" * 80)

for symbol in symbols:

    print(f"Loading {symbol}...")

    datasets[symbol] = builder.build_dataset(
        symbol=symbol,
        interval_name="5m",
        year=2025,
    )

strategy = EMATrendContinuationStrategy()

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

optimizer = StrategyOptimizer(
    strategy=strategy,
    datasets=datasets,
)

best = optimizer.optimize(
    parameter_grid=parameter_grid,
)

print()
print("=" * 80)
print("BEST RESULT")
print("=" * 80)
print(best)
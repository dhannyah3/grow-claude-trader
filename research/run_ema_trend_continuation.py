"""
Run EMA Trend Continuation through the shared research engine.
"""

from research.base_strategy_evaluator import (
    BaseStrategyEvaluator,
)
from research.dataset_builder import DatasetBuilder
from research.ema_trend_continuation_strategy import (
    EMATrendContinuationStrategy,
)


def main() -> None:
    builder = DatasetBuilder()

    data = builder.build_dataset(
        symbol="RELIANCE",
        interval_name="5m",
        year=2025,
    )

    strategy = EMATrendContinuationStrategy(
        stop_atr_multiplier=1.0,
        target_atr_multiplier=2.5,
        minimum_rsi=55.0,
        maximum_rsi=75.0,
        maximum_ema_distance_percent=0.30,
        minimum_volume_ratio=1.0,
        pullback_lookback_candles=5,
    )

    evaluator = BaseStrategyEvaluator(
        strategy=strategy,
        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,
    )

    result = evaluator.evaluate(
        data
    )

    print()
    print("=" * 60)
    print(
        "EMA TREND CONTINUATION "
        "EVALUATION"
    )
    print("=" * 60)

    for key, value in result.items():
        if key == "trades":
            continue

        print(f"{key}: {value}")

    print()
    print("First 5 trades:")

    for trade in result["trades"][:5]:
        print(trade)


if __name__ == "__main__":
    main()
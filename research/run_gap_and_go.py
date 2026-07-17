"""
Run Gap and Go through the shared research engine.
"""

from research.base_strategy_evaluator import (
    BaseStrategyEvaluator,
)
from research.dataset_builder import (
    DatasetBuilder,
)
from research.gap_and_go_strategy import (
    GapAndGoStrategy,
)


def main() -> None:
    builder = DatasetBuilder()

    data = builder.build_dataset(
        symbol="RELIANCE",
        interval_name="5m",
        year=2025,
    )

    strategy = GapAndGoStrategy(
    minimum_gap_percent=0.5,
    opening_range_minutes=15,
    minimum_rsi=50.0,
    maximum_rsi=80.0,
    minimum_volume_ratio=1.2,
    stop_atr_multiplier=1.0,
    target_atr_multiplier=2.5,
    entry_start_time="09:30",
    entry_cutoff_time="11:30",
    force_exit_time="15:20",
)

    evaluator = BaseStrategyEvaluator(
        strategy=strategy,
        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,
    )

    result = evaluator.evaluate(data)

    print()
    print("=" * 60)
    print("GAP AND GO EVALUATION")
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
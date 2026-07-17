"""
Run all research strategies and print a leaderboard.
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
from research.cpr_breakout_strategy import (
    CPRBreakoutStrategy,
)
from research.ema_trend_continuation_strategy import (
    EMATrendContinuationStrategy,
)
from research.donchian_breakout_strategy import (
    DonchianBreakoutStrategy,
)


INITIAL_BALANCE = 100000.0
RISK_PER_TRADE = 0.5
MAX_POSITION = 20.0
SLIPPAGE_BPS = 5.0


def evaluate_strategy(strategy):
    evaluator = BaseStrategyEvaluator(
        strategy=strategy,
        initial_balance=INITIAL_BALANCE,
        risk_per_trade_percent=RISK_PER_TRADE,
        max_position_percent=MAX_POSITION,
        slippage_bps=SLIPPAGE_BPS,
    )

    return evaluator.evaluate(DATASET)


builder = DatasetBuilder()

DATASET = builder.build_dataset(
    symbol="RELIANCE",
    interval_name="5m",
    year=2025,
)


strategies = [
    GapAndGoStrategy(
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
    ),
    CPRBreakoutStrategy(
        minimum_rsi=55.0,
        maximum_rsi=75.0,
        minimum_volume_ratio=1.5,
        stop_atr_multiplier=1.0,
        target_atr_multiplier=2.5,
        entry_start_time="09:30",
        entry_cutoff_time="11:30",
        force_exit_time="15:20",
    ),
    EMATrendContinuationStrategy(
        stop_atr_multiplier=1.0,
        target_atr_multiplier=2.5,
        minimum_rsi=55.0,
        maximum_rsi=75.0,
        maximum_ema_distance_percent=0.30,
        minimum_volume_ratio=1.0,
        pullback_lookback_candles=5,
    ),
    DonchianBreakoutStrategy(
        lookback_period=20,
        minimum_rsi=55.0,
        maximum_rsi=75.0,
        minimum_volume_ratio=1.5,
        stop_atr_multiplier=1.0,
        target_atr_multiplier=2.5,
        entry_start_time="09:30",
        entry_cutoff_time="11:30",
        force_exit_time="15:20",
    ),
]


results = []

for strategy in strategies:
    result = evaluate_strategy(strategy)

    results.append(
        {
            "strategy": strategy.name,
            "trades": result["total_trades"],
            "win_rate": result["win_rate"],
            "net_pnl": result["total_pnl"],
            "profit_factor": result["profit_factor"],
        }
    )


results.sort(
    key=lambda item: item["net_pnl"],
    reverse=True,
)


print()
print("=" * 75)
print("RESEARCH STRATEGY LEADERBOARD")
print("=" * 75)

print(
    f'{"Rank":<5}'
    f'{"Strategy":<30}'
    f'{"Trades":>8}'
    f'{"Win%":>10}'
    f'{"NetPnL":>15}'
    f'{"PF":>10}'
)

print("-" * 75)

for rank, result in enumerate(
    results,
    start=1,
):
    print(
        f"{rank:<5}"
        f"{result['strategy']:<30}"
        f"{result['trades']:>8}"
        f"{result['win_rate']:>10.2f}"
        f"{result['net_pnl']:>15.2f}"
        f"{result['profit_factor']:>10.2f}"
    )

print("-" * 75)
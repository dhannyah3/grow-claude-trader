"""
Optimize Donchian Breakout strategy parameters.

The optimizer:
- tests multiple parameter combinations;
- stores every result;
- excludes configurations with too few trades from ranking;
- ranks valid configurations by net P&L and profit factor.
"""

from itertools import product
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from research.base_strategy_evaluator import (
    BaseStrategyEvaluator,
)
from research.dataset_builder import (
    DatasetBuilder,
)
from research.donchian_breakout_strategy import (
    DonchianBreakoutStrategy,
)


INITIAL_BALANCE = 100000.0
RISK_PER_TRADE = 0.5
MAX_POSITION = 20.0
SLIPPAGE_BPS = 5.0

MINIMUM_TRADES_FOR_RANKING = 5

ALL_RESULTS_PATH = Path(
    "research/donchian_optimization_results.csv"
)

VALID_RESULTS_PATH = Path(
    "research/donchian_valid_results.csv"
)


def evaluate_strategy(
    strategy: DonchianBreakoutStrategy,
    dataset: pd.DataFrame,
) -> Dict[str, Any]:
    evaluator = BaseStrategyEvaluator(
        strategy=strategy,
        initial_balance=INITIAL_BALANCE,
        risk_per_trade_percent=RISK_PER_TRADE,
        max_position_percent=MAX_POSITION,
        slippage_bps=SLIPPAGE_BPS,
    )

    return evaluator.evaluate(dataset)


def main() -> None:
    builder = DatasetBuilder()

    dataset = builder.build_dataset(
        symbol="RELIANCE",
        interval_name="5m",
        year=2025,
    )

    # Lookbacks must become available before the 11:30 entry cutoff.
    lookback_periods = [
        8,
        10,
        12,
        15,
        20,
    ]

    minimum_rsi_values = [
        50.0,
        55.0,
        60.0,
    ]

    minimum_volume_ratios = [
        1.0,
        1.5,
    ]

    stop_atr_multipliers = [
        1.0,
        1.2,
    ]

    target_atr_multipliers = [
        2.0,
        2.5,
        3.0,
    ]

    parameter_combinations = list(
        product(
            lookback_periods,
            minimum_rsi_values,
            minimum_volume_ratios,
            stop_atr_multipliers,
            target_atr_multipliers,
        )
    )

    total_tests = len(parameter_combinations)

    print()
    print(
        f"Running {total_tests} Donchian "
        "parameter combinations..."
    )
    print()

    results: List[Dict[str, Any]] = []

    for test_number, parameters in enumerate(
        parameter_combinations,
        start=1,
    ):
        (
            lookback_period,
            minimum_rsi,
            minimum_volume_ratio,
            stop_atr_multiplier,
            target_atr_multiplier,
        ) = parameters

        print(
            f"[{test_number}/{total_tests}] "
            f"L={lookback_period} "
            f"RSI={minimum_rsi} "
            f"VOL={minimum_volume_ratio} "
            f"SL={stop_atr_multiplier} "
            f"TP={target_atr_multiplier}"
        )

        strategy = DonchianBreakoutStrategy(
            lookback_period=lookback_period,
            minimum_rsi=minimum_rsi,
            maximum_rsi=75.0,
            minimum_volume_ratio=minimum_volume_ratio,
            stop_atr_multiplier=stop_atr_multiplier,
            target_atr_multiplier=target_atr_multiplier,
            entry_start_time="09:30",
            entry_cutoff_time="11:30",
            force_exit_time="15:20",
        )

        evaluation = evaluate_strategy(
            strategy=strategy,
            dataset=dataset,
        )

        total_trades = int(
            evaluation["total_trades"]
        )

        net_pnl = float(
            evaluation["total_pnl"]
        )

        profit_factor = float(
            evaluation["profit_factor"]
        )

        win_rate = float(
            evaluation["win_rate"]
        )

        results.append(
            {
                "lookback": lookback_period,
                "minimum_rsi": minimum_rsi,
                "volume_ratio": minimum_volume_ratio,
                "stop_multiplier": stop_atr_multiplier,
                "target_multiplier": target_atr_multiplier,
                "trades": total_trades,
                "win_rate": win_rate,
                "net_pnl": net_pnl,
                "profit_factor": profit_factor,
                "eligible_for_ranking": (
                    total_trades
                    >= MINIMUM_TRADES_FOR_RANKING
                ),
            }
        )

    all_results = pd.DataFrame(results)

    all_results = all_results.sort_values(
        by=[
            "eligible_for_ranking",
            "net_pnl",
            "profit_factor",
            "trades",
        ],
        ascending=[
            False,
            False,
            False,
            False,
        ],
    ).reset_index(drop=True)

    valid_results = all_results[
        all_results["eligible_for_ranking"]
    ].copy()

    valid_results = valid_results.sort_values(
        by=[
            "net_pnl",
            "profit_factor",
            "trades",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    ).reset_index(drop=True)

    ALL_RESULTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_results.to_csv(
        ALL_RESULTS_PATH,
        index=False,
    )

    valid_results.to_csv(
        VALID_RESULTS_PATH,
        index=False,
    )

    print()
    print("=" * 110)
    print(
        "TOP VALID DONCHIAN CONFIGURATIONS "
        f"(MINIMUM {MINIMUM_TRADES_FOR_RANKING} TRADES)"
    )
    print("=" * 110)

    if valid_results.empty:
        print(
            "No configuration generated enough trades "
            "for ranking."
        )
    else:
        display_columns = [
            "lookback",
            "minimum_rsi",
            "volume_ratio",
            "stop_multiplier",
            "target_multiplier",
            "trades",
            "win_rate",
            "net_pnl",
            "profit_factor",
        ]

        print(
            valid_results[
                display_columns
            ]
            .head(20)
            .to_string(index=False)
        )

        best_result = valid_results.iloc[0]

        print()
        print("=" * 110)
        print("BEST CONFIGURATION")
        print("=" * 110)

        print(
            f"Lookback period: "
            f"{int(best_result['lookback'])}"
        )
        print(
            f"Minimum RSI: "
            f"{best_result['minimum_rsi']:.2f}"
        )
        print(
            f"Minimum volume ratio: "
            f"{best_result['volume_ratio']:.2f}"
        )
        print(
            f"Stop ATR multiplier: "
            f"{best_result['stop_multiplier']:.2f}"
        )
        print(
            f"Target multiplier: "
            f"{best_result['target_multiplier']:.2f}"
        )
        print(
            f"Trades: "
            f"{int(best_result['trades'])}"
        )
        print(
            f"Win rate: "
            f"{best_result['win_rate']:.2f}%"
        )
        print(
            f"Net P&L: "
            f"{best_result['net_pnl']:.2f}"
        )
        print(
            f"Profit factor: "
            f"{best_result['profit_factor']:.2f}"
        )

    print()
    print("All results saved to:")
    print(ALL_RESULTS_PATH)

    print()
    print("Valid ranked results saved to:")
    print(VALID_RESULTS_PATH)


if __name__ == "__main__":
    main()
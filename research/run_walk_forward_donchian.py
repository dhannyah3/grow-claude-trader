"""
Run multi-stock walk-forward validation for the
Donchian Breakout strategy.

The validator will:

1. Optimize parameters on each training window.
2. Freeze the best configuration.
3. Test it on the next unseen window.
4. Repeat across the available 2025 dataset.
5. Save all out-of-sample results to CSV.
"""

from pathlib import Path
from typing import Any, Dict

import pandas as pd

from research.donchian_breakout_strategy import (
    DonchianBreakoutStrategy,
)
from research.walk_forward_validator import (
    WalkForwardValidator,
)


OUTPUT_DIRECTORY = Path("research")

FOLDS_PATH = OUTPUT_DIRECTORY / (
    "donchian_walk_forward_folds.csv"
)

SYMBOL_RESULTS_PATH = OUTPUT_DIRECTORY / (
    "donchian_walk_forward_symbol_results.csv"
)

PARAMETER_HISTORY_PATH = OUTPUT_DIRECTORY / (
    "donchian_walk_forward_parameter_history.csv"
)

OVERALL_SUMMARY_PATH = OUTPUT_DIRECTORY / (
    "donchian_walk_forward_overall_summary.csv"
)


def build_strategy(
    **parameters: Any,
) -> DonchianBreakoutStrategy:
    """
    Create one Donchian strategy instance.

    The optimizer controls the parameters supplied through
    ``parameters``. Trading times and maximum RSI remain fixed.
    """

    return DonchianBreakoutStrategy(
        **parameters,
        maximum_rsi=75.0,
        entry_start_time="09:30",
        entry_cutoff_time="11:30",
        force_exit_time="15:20",
    )


def print_fold_results(
    folds: pd.DataFrame,
) -> None:
    """
    Print the out-of-sample result for every completed fold.
    """

    print()
    print("=" * 150)
    print("DONCHIAN WALK-FORWARD OUT-OF-SAMPLE FOLDS")
    print("=" * 150)

    if folds.empty:
        print("No completed walk-forward folds.")
        return

    preferred_columns = [
        "fold",
        "train_start",
        "train_end",
        "test_start",
        "test_end",
        "lookback_period",
        "minimum_rsi",
        "minimum_volume_ratio",
        "stop_atr_multiplier",
        "target_atr_multiplier",
        "test_symbols",
        "profitable_symbols",
        "test_total_trades",
        "test_combined_win_rate",
        "test_combined_net_pnl",
        "test_average_pnl_per_symbol",
        "test_portfolio_profit_factor",
        "eligible_test_fold",
    ]

    available_columns = [
        column
        for column in preferred_columns
        if column in folds.columns
    ]

    print(
        folds[available_columns].to_string(
            index=False
        )
    )


def print_parameter_history(
    parameter_history: pd.DataFrame,
) -> None:
    """
    Print the best parameters selected during each training fold.
    """

    print()
    print("=" * 150)
    print("TRAINING-WINDOW PARAMETER HISTORY")
    print("=" * 150)

    if parameter_history.empty:
        print("No parameter history was produced.")
        return

    preferred_columns = [
        "fold",
        "train_start",
        "train_end",
        "lookback_period",
        "minimum_rsi",
        "minimum_volume_ratio",
        "stop_atr_multiplier",
        "target_atr_multiplier",
        "training_total_trades",
        "training_win_rate",
        "training_net_pnl",
        "training_profit_factor",
    ]

    available_columns = [
        column
        for column in preferred_columns
        if column in parameter_history.columns
    ]

    print(
        parameter_history[
            available_columns
        ].to_string(index=False)
    )


def print_overall_summary(
    summary: Dict[str, Any],
) -> None:
    """
    Print aggregate out-of-sample performance.
    """

    print()
    print("=" * 90)
    print("OVERALL WALK-FORWARD RESULT")
    print("=" * 90)

    print(
        "Completed folds: "
        f"{summary['completed_folds']}"
    )

    print(
        "Total out-of-sample trades: "
        f"{summary['total_test_trades']}"
    )

    print(
        "Combined out-of-sample P&L: "
        f"{summary['combined_test_pnl']:.2f}"
    )

    print(
        "Weighted out-of-sample win rate: "
        f"{summary['weighted_test_win_rate']:.2f}%"
    )

    print(
        "Profitable folds: "
        f"{summary['profitable_folds']}"
    )

    print(
        "Profitable fold percentage: "
        f"{summary['profitable_fold_percent']:.2f}%"
    )

    print(
        "Average P&L per fold: "
        f"{summary['average_pnl_per_fold']:.2f}"
    )


def save_overall_summary(
    summary: Dict[str, Any],
) -> None:
    """
    Save the aggregate validation summary to one-row CSV.
    """

    summary_dataframe = pd.DataFrame(
        [summary]
    )

    summary_dataframe.to_csv(
        OVERALL_SUMMARY_PATH,
        index=False,
    )

    print(
        "Overall summary saved to: "
        f"{OVERALL_SUMMARY_PATH}"
    )


def main() -> None:
    """
    Configure and run Donchian walk-forward validation.
    """

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

    # Smaller initial grid to confirm the full engine works.
    #
    # 3 × 2 × 2 × 2 × 2 = 48 configurations per fold.
    #
    # Once validation is working, we can expand this grid.
    parameter_grid = {
        "lookback_period": [
            10,
            15,
            20,
        ],
        "minimum_rsi": [
            55.0,
            60.0,
        ],
        "minimum_volume_ratio": [
            1.0,
            1.5,
        ],
        "stop_atr_multiplier": [
            1.0,
            1.2,
        ],
        "target_atr_multiplier": [
            2.0,
            2.5,
        ],
    }

    validator = WalkForwardValidator(
        strategy_factory=build_strategy,
        parameter_grid=parameter_grid,
        symbols=symbols,

        # Initial validation settings:
        # 120 trading days for training.
        # 30 unseen trading days for testing.
        # Move forward by 30 days per fold.
        train_days=120,
        test_days=30,
        step_days=30,

        interval_name="5m",
        year=2025,

        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,

        minimum_training_trades=50,
        minimum_test_trades=5,
    )

    results = validator.run()

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    validator.save_results(
        results=results,
        folds_path=str(FOLDS_PATH),
        symbol_results_path=str(
            SYMBOL_RESULTS_PATH
        ),
        parameter_history_path=str(
            PARAMETER_HISTORY_PATH
        ),
    )

    overall_summary = (
        validator.build_overall_summary(
            results["folds"]
        )
    )

    save_overall_summary(
        overall_summary
    )

    print_fold_results(
        results["folds"]
    )

    print_parameter_history(
        results["parameter_history"]
    )

    print_overall_summary(
        overall_summary
    )


if __name__ == "__main__":
    main()
"""
Run Donchian Breakout optimization across multiple stocks.
"""

from pathlib import Path

import pandas as pd

from research.donchian_breakout_strategy import (
    DonchianBreakoutStrategy,
)
from research.multistock_optimizer import (
    MultiStockOptimizer,
)


SUMMARY_PATH = Path(
    "research/donchian_multistock_summary.csv"
)

SYMBOL_RESULTS_PATH = Path(
    "research/donchian_multistock_symbol_results.csv"
)

VALID_RESULTS_PATH = Path(
    "research/donchian_multistock_valid_results.csv"
)


def build_strategy(**parameters):
    """
    Create one Donchian strategy instance.

    Fixed trading-time parameters are added here so they do not
    need to appear inside the optimization grid.
    """

    return DonchianBreakoutStrategy(
        **parameters,
        maximum_rsi=75.0,
        entry_start_time="09:30",
        entry_cutoff_time="11:30",
        force_exit_time="15:20",
    )


def print_top_results(
    valid_results: pd.DataFrame,
    limit: int = 20,
) -> None:
    print()
    print("=" * 130)
    print("TOP MULTI-STOCK DONCHIAN CONFIGURATIONS")
    print("=" * 130)

    if valid_results.empty:
        print(
            "No configuration produced enough trades "
            "to qualify for ranking."
        )
        return

    display_columns = [
        "lookback_period",
        "minimum_rsi",
        "minimum_volume_ratio",
        "stop_atr_multiplier",
        "target_atr_multiplier",
        "symbols_tested",
        "profitable_symbols",
        "profitable_symbol_percent",
        "total_trades",
        "combined_win_rate",
        "combined_net_pnl",
        "average_pnl_per_symbol",
        "portfolio_profit_factor",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in valid_results.columns
    ]

    print(
        valid_results[
            available_columns
        ]
        .head(limit)
        .to_string(index=False)
    )


def print_best_result(
    valid_results: pd.DataFrame,
) -> None:
    if valid_results.empty:
        return

    best = valid_results.iloc[0]

    print()
    print("=" * 90)
    print("BEST MULTI-STOCK CONFIGURATION")
    print("=" * 90)

    print(
        f"Lookback period: "
        f"{int(best['lookback_period'])}"
    )

    print(
        f"Minimum RSI: "
        f"{best['minimum_rsi']:.2f}"
    )

    print(
        f"Minimum volume ratio: "
        f"{best['minimum_volume_ratio']:.2f}"
    )

    print(
        f"Stop ATR multiplier: "
        f"{best['stop_atr_multiplier']:.2f}"
    )

    print(
        f"Target ATR multiplier: "
        f"{best['target_atr_multiplier']:.2f}"
    )

    print(
        f"Symbols tested: "
        f"{int(best['symbols_tested'])}"
    )

    print(
        f"Profitable symbols: "
        f"{int(best['profitable_symbols'])}"
    )

    print(
        f"Profitable symbol percentage: "
        f"{best['profitable_symbol_percent']:.2f}%"
    )

    print(
        f"Total trades: "
        f"{int(best['total_trades'])}"
    )

    print(
        f"Combined win rate: "
        f"{best['combined_win_rate']:.2f}%"
    )

    print(
        f"Combined net P&L: "
        f"{best['combined_net_pnl']:.2f}"
    )

    print(
        f"Average P&L per symbol: "
        f"{best['average_pnl_per_symbol']:.2f}"
    )

    print(
        f"Portfolio profit factor: "
        f"{best['portfolio_profit_factor']:.2f}"
    )


def main() -> None:
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
        "lookback_period": [
            8,
            10,
            12,
            15,
            20,
        ],
        "minimum_rsi": [
            50.0,
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
            3.0,
        ],
    }

    optimizer = MultiStockOptimizer(
        strategy_factory=build_strategy,
        parameter_grid=parameter_grid,
        symbols=symbols,
        interval_name="5m",
        year=2025,
        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,
        minimum_total_trades=50,
    )

    results = optimizer.optimize()

    valid_results = optimizer.get_valid_results(
        results["summary"]
    )

    SUMMARY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    optimizer.save_results(
        results=results,
        summary_path=str(SUMMARY_PATH),
        symbol_results_path=str(
            SYMBOL_RESULTS_PATH
        ),
    )

    valid_results.to_csv(
        VALID_RESULTS_PATH,
        index=False,
    )

    print_top_results(
        valid_results=valid_results,
        limit=20,
    )

    print_best_result(
        valid_results=valid_results,
    )

    print()
    print(
        "Valid ranked results saved to: "
        f"{VALID_RESULTS_PATH}"
    )


if __name__ == "__main__":
    main()
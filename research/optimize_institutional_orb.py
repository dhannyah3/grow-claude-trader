"""
Multi-stock optimization for Institutional ORB.

Tests Institutional ORB parameter combinations across multiple
stocks using the generic MultiStockOptimizer framework.
"""

from pathlib import Path

from research.institutional_orb_strategy import (
    InstitutionalORBStrategy,
)
from research.multistock_optimizer import (
    MultiStockOptimizer,
)


SYMBOLS = [
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


PARAMETER_GRID = {
    "stop_atr_multiplier": [
        0.8,
        1.0,
        1.2,
    ],
    "target_risk_multiplier": [
        1.5,
        2.0,
        2.5,
    ],
    "minimum_volume_ratio": [
        1.2,
        1.5,
        2.0,
    ],
    "maximum_entry_distance_atr": [
        0.30,
        0.50,
        0.75,
    ],
    "atr_expansion_lookback": [
        5,
        10,
        15,
    ],
}


OUTPUT_DIRECTORY = Path(
    "research/results"
)

SUMMARY_PATH = (
    OUTPUT_DIRECTORY
    / "institutional_orb_optimization_summary.csv"
)

SYMBOL_RESULTS_PATH = (
    OUTPUT_DIRECTORY
    / "institutional_orb_symbol_results.csv"
)


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    optimizer = MultiStockOptimizer(
        strategy_factory=InstitutionalORBStrategy,
        parameter_grid=PARAMETER_GRID,
        symbols=SYMBOLS,
        interval_name="5m",
        year=2025,
        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,
        minimum_total_trades=20,
    )

    print()
    print("=" * 90)
    print("INSTITUTIONAL ORB MULTI-STOCK OPTIMIZATION")
    print("=" * 90)

    results = optimizer.optimize()

    optimizer.save_results(
        results=results,
        summary_path=str(SUMMARY_PATH),
        symbol_results_path=str(
            SYMBOL_RESULTS_PATH
        ),
    )

    summary = results["summary"]

    print()
    print("=" * 90)
    print("TOP 10 CONFIGURATIONS")
    print("=" * 90)

    if summary.empty:
        print(
            "No optimization results were produced."
        )
        return

    display_columns = [
        "stop_atr_multiplier",
        "target_risk_multiplier",
        "minimum_volume_ratio",
        "maximum_entry_distance_atr",
        "atr_expansion_lookback",
        "symbols_tested",
        "profitable_symbols",
        "profitable_symbol_percent",
        "total_trades",
        "combined_win_rate",
        "combined_net_pnl",
        "portfolio_profit_factor",
        "eligible_for_ranking",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in summary.columns
    ]

    print(
        summary[
            available_columns
        ].head(10).to_string(
            index=False
        )
    )

    valid_results = (
        optimizer.get_valid_results(
            summary
        )
    )

    print()
    print("=" * 90)
    print("BEST ELIGIBLE CONFIGURATION")
    print("=" * 90)

    if valid_results.empty:
        print(
            "No configuration reached the "
            "minimum trade requirement."
        )
        return

    best_result = valid_results.iloc[0]

    for column in available_columns:
        if column in best_result.index:
            print(
                f"{column}: "
                f"{best_result[column]}"
            )


if __name__ == "__main__":
    main()

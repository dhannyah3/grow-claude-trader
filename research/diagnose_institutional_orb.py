"""
Trade-level diagnostics for Institutional ORB.

Runs the best eligible Institutional ORB configuration across the same
10 symbols and 2025 five-minute datasets used by the optimizer.

Exports every individual trade for detailed analysis.
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from research.base_strategy_evaluator import BaseStrategyEvaluator
from research.dataset_builder import DatasetBuilder
from research.institutional_orb_strategy import InstitutionalORBStrategy


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


BEST_PARAMS: Dict[str, Any] = {
    "stop_atr_multiplier": 1.0,
    "target_risk_multiplier": 2.5,
    "minimum_volume_ratio": 1.5,
    "maximum_entry_distance_atr": 0.75,
    "atr_expansion_lookback": 15,
}


INTERVAL_NAME = "5m"
YEAR = 2025

OUTPUT_FILE = Path(
    "research/results/institutional_orb_trade_diagnostics.csv"
)


def main() -> None:
    dataset_builder = DatasetBuilder()
    all_trades: List[Dict[str, Any]] = []

    print()
    print("=" * 70)
    print("INSTITUTIONAL ORB TRADE DIAGNOSTICS")
    print("=" * 70)

    for index, symbol in enumerate(
        SYMBOLS,
        start=1,
    ):
        print()
        print(
            f"[{index}/{len(SYMBOLS)}] "
            f"Loading {symbol}..."
        )

        try:
            dataframe = dataset_builder.build_dataset(
                symbol=symbol,
                interval_name=INTERVAL_NAME,
                year=YEAR,
            )
        except Exception as error:
            print(
                f"Skipped {symbol}: {error}"
            )
            continue

        if dataframe is None or dataframe.empty:
            print(
                f"Skipped {symbol}: empty dataset."
            )
            continue

        print(
            f"Loaded {symbol}: "
            f"{len(dataframe)} rows"
        )

        strategy = InstitutionalORBStrategy(
            **BEST_PARAMS
        )

        evaluator = BaseStrategyEvaluator(
            strategy=strategy,
            initial_balance=100000.0,
            risk_per_trade_percent=0.5,
            max_position_percent=20.0,
            slippage_bps=5.0,
        )

        result = evaluator.evaluate(
            dataframe=dataframe,
        )

        trades = result.get(
            "trades",
            [],
        )

        print(
            f"Trades: {result.get('total_trades', 0)} | "
            f"Win rate: {result.get('win_rate', 0.0)}% | "
            f"Net P&L: {result.get('total_pnl', 0.0)}"
        )

        for trade in trades:
            trade_record = dict(trade)

            trade_record["symbol"] = symbol
            trade_record["interval_name"] = INTERVAL_NAME
            trade_record["year"] = YEAR

            for parameter_name, parameter_value in (
                BEST_PARAMS.items()
            ):
                trade_record[
                    parameter_name
                ] = parameter_value

            all_trades.append(
                trade_record
            )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    diagnostics = pd.DataFrame(
        all_trades
    )

    diagnostics.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    print()
    print("=" * 70)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 70)
    print(
        f"Trades exported : "
        f"{len(diagnostics)}"
    )
    print(
        f"Output file     : "
        f"{OUTPUT_FILE}"
    )

    if diagnostics.empty:
        print(
            "No trades were generated."
        )
        return

    total_pnl = float(
        diagnostics["net_pnl"].sum()
    )
    wins = int(
        (
            diagnostics["net_pnl"] > 0
        ).sum()
    )
    losses = int(
        (
            diagnostics["net_pnl"] < 0
        ).sum()
    )
    breakeven = int(
        (
            diagnostics["net_pnl"] == 0
        ).sum()
    )

    win_rate = (
        wins
        / len(diagnostics)
        * 100.0
    )

    print(
        f"Total net P&L   : "
        f"{round(total_pnl, 2)}"
    )
    print(
        f"Wins            : "
        f"{wins}"
    )
    print(
        f"Losses          : "
        f"{losses}"
    )
    print(
        f"Breakeven       : "
        f"{breakeven}"
    )
    print(
        f"Win rate        : "
        f"{round(win_rate, 2)}%"
    )

    print()
    print("EXIT REASONS")
    print("-" * 70)

    if "exit_reason" in diagnostics.columns:
        print(
            diagnostics[
                "exit_reason"
            ]
            .value_counts()
            .to_string()
        )

    print()
    print("SYMBOL PERFORMANCE")
    print("-" * 70)

    symbol_summary = (
        diagnostics.groupby(
            "symbol"
        )
        .agg(
            trades=(
                "net_pnl",
                "count",
            ),
            wins=(
                "net_pnl",
                lambda values: int(
                    (
                        values > 0
                    ).sum()
                ),
            ),
            net_pnl=(
                "net_pnl",
                "sum",
            ),
            average_pnl=(
                "net_pnl",
                "mean",
            ),
        )
        .reset_index()
    )

    symbol_summary[
        "win_rate"
    ] = (
        symbol_summary["wins"]
        / symbol_summary["trades"]
        * 100.0
    )

    print(
        symbol_summary[
            [
                "symbol",
                "trades",
                "wins",
                "win_rate",
                "net_pnl",
                "average_pnl",
            ]
        ]
        .sort_values(
            "net_pnl",
            ascending=False,
        )
        .to_string(
            index=False,
        )
    )


if __name__ == "__main__":
    main()
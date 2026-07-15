"""
Multi-Symbol Strategy Evaluator

Evaluates ORB across many symbols, ranks the results,
and saves a summary report.
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from research.multi_year_evaluator import (
    MultiYearEvaluator,
)


SYMBOLS: List[str] = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "LT",
    "AXISBANK",
    "BHARTIARTL",
    "ITC",
]


class MultiSymbolEvaluator:
    def __init__(
        self,
        symbols: List[str],
        interval_name: str = "5m",
        initial_balance: float = 100000.0,
    ) -> None:
        self.symbols = [
            str(symbol).strip().upper()
            for symbol in symbols
            if str(symbol).strip()
        ]

        self.interval_name = str(
            interval_name
        ).strip()

        self.initial_balance = float(
            initial_balance
        )

    def run(
        self,
    ) -> pd.DataFrame:
        results: List[
            Dict[str, Any]
        ] = []

        for symbol in self.symbols:
            print()
            print("=" * 60)
            print(f"Evaluating {symbol}")
            print("=" * 60)

            evaluator = MultiYearEvaluator(
                symbol=symbol,
                interval_name=(
                    self.interval_name
                ),
                initial_balance=(
                    self.initial_balance
                ),
            )

            raw_data = (
                evaluator.load_all_years()
            )

            if raw_data.empty:
                print(
                    f"{symbol}: skipped because "
                    "no historical data is available."
                )
                continue

            dataset = evaluator.build_dataset(
                raw_data
            )

            if dataset.empty:
                print(
                    f"{symbol}: skipped because "
                    "the feature dataset is empty."
                )
                continue

            result = evaluator.evaluate(
                dataset
            )

            results.append(
                {
                    "symbol": symbol,
                    "total_trades": (
                        result.get(
                            "total_trades",
                            0,
                        )
                    ),
                    "wins": result.get(
                        "wins",
                        0,
                    ),
                    "losses": result.get(
                        "losses",
                        0,
                    ),
                    "win_rate": result.get(
                        "win_rate",
                        0.0,
                    ),
                    "total_pnl": result.get(
                        "total_pnl",
                        0.0,
                    ),
                    "profit_factor": (
                        result.get(
                            "profit_factor",
                            0.0,
                        )
                    ),
                    "expectancy": result.get(
                        "expectancy",
                        0.0,
                    ),
                    "average_r": result.get(
                        "average_r",
                        0.0,
                    ),
                    "max_drawdown": (
                        result.get(
                            "max_drawdown",
                            0.0,
                        )
                    ),
                    "ending_balance": (
                        result.get(
                            "ending_balance",
                            self.initial_balance,
                        )
                    ),
                }
            )

        if not results:
            print(
                "\nNo symbols had usable "
                "historical data."
            )
            return pd.DataFrame()

        summary = pd.DataFrame(
            results
        )

        summary["rank_score"] = (
            summary["average_r"] * 100
            + summary["profit_factor"] * 10
            - summary["max_drawdown"] * 0.1
        )

        summary = summary.sort_values(
            by=[
                "rank_score",
                "profit_factor",
                "expectancy",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        ).reset_index(
            drop=True
        )

        summary.insert(
            0,
            "rank",
            range(
                1,
                len(summary) + 1,
            ),
        )

        output_directory = Path(
            "research/results"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_file = (
            output_directory
            / "multi_symbol_orb_summary.csv"
        )

        summary.to_csv(
            output_file,
            index=False,
        )

        print()
        print("=" * 60)
        print("MULTI-SYMBOL ORB RANKING")
        print("=" * 60)

        print(
            summary.to_string(
                index=False
            )
        )

        print()
        print(
            "Summary saved to:",
            output_file,
        )

        return summary


if __name__ == "__main__":
    evaluator = MultiSymbolEvaluator(
        symbols=SYMBOLS,
        interval_name="5m",
        initial_balance=100000.0,
    )

    evaluator.run()
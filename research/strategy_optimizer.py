"""
ORB Strategy Optimizer

Tests multiple ORB parameter combinations
and ranks them by performance.
"""

from itertools import product
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from research.dataset_builder import DatasetBuilder
from research.strategy_evaluator import StrategyEvaluator


class StrategyOptimizer:
    def __init__(
        self,
        symbol: str,
        interval_name: str = "5m",
        initial_balance: float = 100000.0,
    ) -> None:
        self.symbol = str(
            symbol
        ).strip().upper()

        self.interval_name = str(
            interval_name
        ).strip()

        self.builder = DatasetBuilder()

        self.evaluator = StrategyEvaluator(
            initial_balance=initial_balance
        )

    def load_dataset(
        self,
    ) -> pd.DataFrame:
        raw_data = (
            self.builder.historical.load(
                symbol=self.symbol,
                interval_name=(
                    self.interval_name
                ),
                year=None,
            )
        )

        if raw_data.empty:
            print(
                f"{self.symbol}: no historical "
                "data found."
            )
            return raw_data

        raw_data = (
            self.builder._prepare_timestamp(
                raw_data
            )
        )

        indicator_input = {
            "candles": raw_data[
                [
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            ].values.tolist()
        }

        from strategies.indicators import (
            calculate_indicators,
        )

        dataset = calculate_indicators(
            indicator_input
        )

        if dataset.empty:
            print(
                "Indicator calculation "
                "returned no rows."
            )
            return dataset

        dataset = (
            self.builder._prepare_timestamp(
                dataset
            )
        )

        dataset = self.builder._add_features(
            dataset
        )

        print(
            f"{self.symbol}: loaded "
            f"{len(dataset)} feature rows."
        )

        return dataset

    def optimize(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        if dataframe.empty:
            return pd.DataFrame()

        opening_ranges = [
            5,
            10,
            15,
            20,
        ]

        stop_multipliers = [
            0.75,
            1.0,
            1.25,
        ]

        target_multipliers = [
            1.5,
            2.0,
            2.5,
        ]

        minimum_rsi_values = [
            45.0,
            50.0,
            55.0,
        ]

        maximum_rsi_values = [
            65.0,
            70.0,
        ]

        volume_ratios = [
            0.8,
            1.0,
            1.2,
        ]

        combinations = list(
            product(
                opening_ranges,
                stop_multipliers,
                target_multipliers,
                minimum_rsi_values,
                maximum_rsi_values,
                volume_ratios,
            )
        )

        print(
            f"Testing "
            f"{len(combinations)} "
            "parameter combinations..."
        )

        results: List[
            Dict[str, Any]
        ] = []

        for index, parameters in enumerate(
            combinations,
            start=1,
        ):
            (
                opening_range,
                stop_multiplier,
                target_multiplier,
                minimum_rsi,
                maximum_rsi,
                volume_ratio,
            ) = parameters

            result = (
                self.evaluator.evaluate_orb(
                    dataframe=dataframe,
                    opening_range_minutes=(
                        opening_range
                    ),
                    stop_atr_multiplier=(
                        stop_multiplier
                    ),
                    target_atr_multiplier=(
                        target_multiplier
                    ),
                    minimum_rsi=minimum_rsi,
                    maximum_rsi=maximum_rsi,
                    minimum_volume_ratio=(
                        volume_ratio
                    ),
                )
            )

            results.append(
                {
                    "opening_range_minutes": (
                        opening_range
                    ),
                    "stop_atr_multiplier": (
                        stop_multiplier
                    ),
                    "target_atr_multiplier": (
                        target_multiplier
                    ),
                    "minimum_rsi": (
                        minimum_rsi
                    ),
                    "maximum_rsi": (
                        maximum_rsi
                    ),
                    "minimum_volume_ratio": (
                        volume_ratio
                    ),
                    "total_trades": (
                        result.get(
                            "total_trades",
                            0,
                        )
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
                }
            )

            if (
                index % 50 == 0
                or index
                == len(combinations)
            ):
                print(
                    f"Completed "
                    f"{index}/"
                    f"{len(combinations)}"
                )

        summary = pd.DataFrame(
            results
        )

        if summary.empty:
            return summary

        minimum_trade_count = 20

        summary[
            "eligible"
        ] = (
            summary["total_trades"]
            >= minimum_trade_count
        )

        summary[
            "rank_score"
        ] = (
            summary["average_r"] * 100
            + summary[
                "profit_factor"
            ] * 10
            + summary[
                "expectancy"
            ]
            - summary[
                "max_drawdown"
            ] * 0.1
        )

        summary.loc[
            ~summary["eligible"],
            "rank_score",
        ] = -999999.0

        summary = summary.sort_values(
            by=[
                "eligible",
                "rank_score",
                "profit_factor",
                "total_trades",
            ],
            ascending=[
                False,
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

        return summary

    def save_results(
        self,
        results: pd.DataFrame,
    ) -> Path:
        output_directory = Path(
            "research/results"
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_file = (
            output_directory
            / (
                f"{self.symbol}_"
                f"{self.interval_name}_"
                "orb_optimization.csv"
            )
        )

        results.to_csv(
            output_file,
            index=False,
        )

        return output_file

    def run(
        self,
    ) -> pd.DataFrame:
        dataset = self.load_dataset()

        results = self.optimize(
            dataset
        )

        if results.empty:
            print(
                "No optimization results."
            )
            return results

        output_file = self.save_results(
            results
        )

        print()
        print("=" * 60)
        print(
            f"{self.symbol} ORB "
            "OPTIMIZATION RESULTS"
        )
        print("=" * 60)

        display_columns = [
            "rank",
            "opening_range_minutes",
            "stop_atr_multiplier",
            "target_atr_multiplier",
            "minimum_rsi",
            "maximum_rsi",
            "minimum_volume_ratio",
            "total_trades",
            "win_rate",
            "profit_factor",
            "expectancy",
            "average_r",
            "max_drawdown",
            "rank_score",
        ]

        print(
            results[
                display_columns
            ]
            .head(20)
            .to_string(
                index=False
            )
        )

        print()
        print(
            "Optimization results "
            "saved to:",
            output_file,
        )

        return results


if __name__ == "__main__":
    optimizer = StrategyOptimizer(
        symbol="RELIANCE",
        interval_name="5m",
        initial_balance=100000.0,
    )

    optimizer.run()
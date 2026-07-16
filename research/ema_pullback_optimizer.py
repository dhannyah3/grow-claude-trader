"""
EMA Pullback Optimizer

Runs a coarse 256-combination search over the EMA pullback
strategy using realistic costs, slippage, dynamic sizing,
capital limits, and post-cost performance ranking.
"""

from itertools import product
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from research.dataset_builder import DatasetBuilder
from research.ema_pullback_evaluator import (
    EMAPullbackEvaluator,
)


class EMAPullbackOptimizer:
    def __init__(
        self,
        symbol: str,
        interval_name: str = "5m",
        initial_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_position_percent: float = 20.0,
        slippage_bps: float = 5.0,
    ) -> None:
        self.symbol = str(
            symbol
        ).strip().upper()

        self.interval_name = str(
            interval_name
        ).strip()

        self.builder = DatasetBuilder()

        self.evaluator = EMAPullbackEvaluator(
            initial_balance=initial_balance,
            risk_per_trade_percent=(
                risk_per_trade_percent
            ),
            max_position_percent=(
                max_position_percent
            ),
            slippage_bps=slippage_bps,
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

        minimum_rsi_values = [
            40.0,
            50.0,
        ]

        maximum_rsi_values = [
            65.0,
            75.0,
        ]

        ema_distances = [
            0.10,
            0.30,
        ]

        stop_multipliers = [
            0.75,
            1.25,
        ]

        target_multipliers = [
            2.0,
            3.0,
        ]

        volume_ratios = [
            0.5,
            1.0,
        ]

        pullback_lookbacks = [
            3,
            8,
        ]

        bullish_candle_options = [
            True,
            False,
        ]

        combinations = list(
            product(
                minimum_rsi_values,
                maximum_rsi_values,
                ema_distances,
                stop_multipliers,
                target_multipliers,
                volume_ratios,
                pullback_lookbacks,
                bullish_candle_options,
            )
        )

        print(
            f"Testing "
            f"{len(combinations)} "
            "EMA parameter combinations..."
        )

        results: List[
            Dict[str, Any]
        ] = []

        for index, parameters in enumerate(
            combinations,
            start=1,
        ):
            (
                minimum_rsi,
                maximum_rsi,
                ema_distance,
                stop_multiplier,
                target_multiplier,
                volume_ratio,
                pullback_lookback,
                require_bullish_candle,
            ) = parameters

            result = self.evaluator.evaluate(
                dataframe=dataframe,
                minimum_rsi=minimum_rsi,
                maximum_rsi=maximum_rsi,
                maximum_ema_distance_percent=(
                    ema_distance
                ),
                stop_atr_multiplier=(
                    stop_multiplier
                ),
                target_atr_multiplier=(
                    target_multiplier
                ),
                minimum_volume_ratio=(
                    volume_ratio
                ),
                pullback_lookback_candles=(
                    pullback_lookback
                ),
                require_bullish_candle=(
                    require_bullish_candle
                ),
                entry_start_time="09:30",
                entry_cutoff_time="15:10",
                force_exit_time="15:20",
            )

            results.append(
                {
                    "minimum_rsi": (
                        minimum_rsi
                    ),
                    "maximum_rsi": (
                        maximum_rsi
                    ),
                    "maximum_ema_distance_percent": (
                        ema_distance
                    ),
                    "stop_atr_multiplier": (
                        stop_multiplier
                    ),
                    "target_atr_multiplier": (
                        target_multiplier
                    ),
                    "minimum_volume_ratio": (
                        volume_ratio
                    ),
                    "pullback_lookback_candles": (
                        pullback_lookback
                    ),
                    "require_bullish_candle": (
                        require_bullish_candle
                    ),
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
                    "gross_strategy_pnl": (
                        result.get(
                            "gross_strategy_pnl",
                            0.0,
                        )
                    ),
                    "transaction_costs": (
                        result.get(
                            "transaction_costs",
                            0.0,
                        )
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
                    "max_drawdown_percent": (
                        result.get(
                            "max_drawdown_percent",
                            0.0,
                        )
                    ),
                    "total_return_percent": (
                        result.get(
                            "total_return_percent",
                            0.0,
                        )
                    ),
                    "ending_balance": (
                        result.get(
                            "ending_balance",
                            0.0,
                        )
                    ),
                    "average_quantity": (
                        result.get(
                            "average_quantity",
                            0.0,
                        )
                    ),
                    "skipped_for_quantity": (
                        result.get(
                            "skipped_for_quantity",
                            0,
                        )
                    ),
                }
            )

            if (
                index % 25 == 0
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

        summary["eligible"] = (
            summary["total_trades"]
            >= minimum_trade_count
        )

        summary["profitable"] = (
            summary["total_pnl"] > 0
        )

        summary["rank_score"] = (
            summary["average_r"] * 100
            + summary[
                "profit_factor"
            ] * 10
            + summary[
                "total_return_percent"
            ]
            - summary[
                "max_drawdown_percent"
            ] * 2
        )

        summary.loc[
            ~summary["eligible"],
            "rank_score",
        ] = -999999.0

        summary = summary.sort_values(
            by=[
                "eligible",
                "profitable",
                "rank_score",
                "profit_factor",
                "total_trades",
            ],
            ascending=[
                False,
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
                "ema_pullback_coarse_optimization.csv"
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
            f"{self.symbol} EMA "
            "PULLBACK COARSE OPTIMIZATION"
        )
        print("=" * 60)

        display_columns = [
            "rank",
            "minimum_rsi",
            "maximum_rsi",
            "maximum_ema_distance_percent",
            "stop_atr_multiplier",
            "target_atr_multiplier",
            "minimum_volume_ratio",
            "pullback_lookback_candles",
            "require_bullish_candle",
            "total_trades",
            "win_rate",
            "total_pnl",
            "profit_factor",
            "expectancy",
            "average_r",
            "max_drawdown_percent",
            "total_return_percent",
            "eligible",
            "profitable",
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

        eligible_count = int(
            results["eligible"].sum()
        )

        profitable_eligible_count = int(
            (
                results["eligible"]
                & results["profitable"]
            ).sum()
        )

        print()
        print(
            "Eligible combinations:",
            eligible_count,
        )

        print(
            "Profitable eligible combinations:",
            profitable_eligible_count,
        )

        print(
            "Optimization results saved to:",
            output_file,
        )

        return results


if __name__ == "__main__":
    optimizer = EMAPullbackOptimizer(
        symbol="RELIANCE",
        interval_name="5m",
        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,
    )

    optimizer.run()
    
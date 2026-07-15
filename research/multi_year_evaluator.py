"""
Multi-Year Strategy Evaluator

Loads all available historical years for a symbol,
builds indicators and research features, evaluates ORB,
prints summary metrics, and saves the generated trades.
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from research.dataset_builder import DatasetBuilder
from research.strategy_evaluator import StrategyEvaluator


class MultiYearEvaluator:
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

    def load_all_years(
        self,
    ) -> pd.DataFrame:
        dataframe = (
            self.builder.historical.load(
                symbol=self.symbol,
                interval_name=(
                    self.interval_name
                ),
                year=None,
            )
        )

        if dataframe.empty:
            print(
                f"{self.symbol}: no historical "
                "data found."
            )
            return dataframe

        print(
            f"{self.symbol}: loaded "
            f"{len(dataframe)} raw rows."
        )

        return dataframe

    def build_dataset(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        if dataframe.empty:
            return dataframe

        dataframe = (
            self.builder._prepare_timestamp(
                dataframe
            )
        )

        indicator_input = {
            "candles": dataframe[
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
            f"{self.symbol}: built "
            f"{len(dataset)} feature rows."
        )

        return dataset

    def evaluate(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict[str, Any]:
        return self.evaluator.evaluate_orb(
            dataframe=dataframe,
            opening_range_minutes=15,
            stop_atr_multiplier=1.0,
            target_atr_multiplier=2.0,
            minimum_rsi=50.0,
            maximum_rsi=70.0,
            minimum_volume_ratio=1.0,
        )

    def save_trades(
        self,
        trades: List[Dict[str, Any]],
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
                "orb_trades.csv"
            )
        )

        trade_dataframe = pd.DataFrame(
            trades
        )

        trade_dataframe.to_csv(
            output_file,
            index=False,
        )

        return output_file

    def run(
        self,
    ) -> Dict[str, Any]:
        raw_data = self.load_all_years()

        dataset = self.build_dataset(
            raw_data
        )

        if dataset.empty:
            return {
                "total_trades": 0,
                "trades": [],
            }

        result = self.evaluate(
            dataset
        )

        output_file = self.save_trades(
            result.get(
                "trades",
                [],
            )
        )

        print()
        print("=" * 60)
        print(
            f"{self.symbol} MULTI-YEAR "
            "ORB EVALUATION"
        )
        print("=" * 60)

        for key, value in (
            result.items()
        ):
            if key == "trades":
                continue

            print(
                f"{key}: {value}"
            )

        print()
        print(
            "Trades saved to:",
            output_file,
        )

        return result


if __name__ == "__main__":
    evaluator = MultiYearEvaluator(
        symbol="RELIANCE",
        interval_name="5m",
        initial_balance=100000.0,
    )

    evaluator.run()
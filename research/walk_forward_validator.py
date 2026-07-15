"""
Walk-Forward Validator

Optimizes ORB parameters on a training period
and evaluates the best parameters on unseen test data.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd

from research.strategy_evaluator import (
    StrategyEvaluator,
)
from research.strategy_optimizer import (
    StrategyOptimizer,
)


@dataclass
class WalkForwardSplit:
    training: pd.DataFrame
    testing: pd.DataFrame


class WalkForwardValidator:
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

        self.initial_balance = float(
            initial_balance
        )

        self.optimizer = StrategyOptimizer(
            symbol=self.symbol,
            interval_name=self.interval_name,
            initial_balance=self.initial_balance,
        )

        self.evaluator = StrategyEvaluator(
            initial_balance=self.initial_balance,
        )

    def load_dataset(
        self,
    ) -> pd.DataFrame:
        dataset = self.optimizer.load_dataset()

        if dataset.empty:
            print(
                f"{self.symbol}: no dataset "
                "available."
            )
            return dataset

        dataset = dataset.copy()

        dataset["timestamp"] = pd.to_datetime(
            dataset["timestamp"],
            errors="coerce",
        )

        dataset = dataset.dropna(
            subset=["timestamp"]
        )

        dataset = dataset.sort_values(
            "timestamp"
        ).reset_index(
            drop=True
        )

        return dataset

    def split_dataset(
        self,
        dataframe: pd.DataFrame,
        year: int = 2025,
        training_end_month: int = 9,
    ) -> WalkForwardSplit:
        if dataframe.empty:
            return WalkForwardSplit(
                training=pd.DataFrame(),
                testing=pd.DataFrame(),
            )

        selected_year = dataframe[
            dataframe["timestamp"].dt.year
            == int(year)
        ].copy()

        training = selected_year[
            selected_year["timestamp"].dt.month
            <= int(training_end_month)
        ].copy()

        testing = selected_year[
            selected_year["timestamp"].dt.month
            > int(training_end_month)
        ].copy()

        training = training.reset_index(
            drop=True
        )

        testing = testing.reset_index(
            drop=True
        )

        return WalkForwardSplit(
            training=training,
            testing=testing,
        )

    def print_split_summary(
        self,
        split: WalkForwardSplit,
        year: int,
        training_end_month: int,
    ) -> None:
        print()
        print("=" * 60)
        print("WALK-FORWARD DATA SPLIT")
        print("=" * 60)

        print(
            f"Symbol             : "
            f"{self.symbol}"
        )

        print(
            f"Year               : "
            f"{year}"
        )

        print(
            f"Training months    : "
            f"1-{training_end_month}"
        )

        print(
            f"Testing months     : "
            f"{training_end_month + 1}-12"
        )

        print(
            f"Training rows      : "
            f"{len(split.training)}"
        )

        print(
            f"Testing rows       : "
            f"{len(split.testing)}"
        )

        if not split.training.empty:
            print(
                f"Training start     : "
                f"{split.training['timestamp'].min()}"
            )

            print(
                f"Training end       : "
                f"{split.training['timestamp'].max()}"
            )

        if not split.testing.empty:
            print(
                f"Testing start      : "
                f"{split.testing['timestamp'].min()}"
            )

            print(
                f"Testing end        : "
                f"{split.testing['timestamp'].max()}"
            )

    def run_split_test(
        self,
        year: int = 2025,
        training_end_month: int = 9,
    ) -> Optional[WalkForwardSplit]:
        dataset = self.load_dataset()

        if dataset.empty:
            return None

        split = self.split_dataset(
            dataframe=dataset,
            year=year,
            training_end_month=training_end_month,
        )

        self.print_split_summary(
            split=split,
            year=year,
            training_end_month=training_end_month,
        )

        return split

    def optimize_training(
        self,
        training: pd.DataFrame,
    ) -> pd.Series:
        if training.empty:
            raise ValueError(
                "Training dataset is empty."
            )

        results = self.optimizer.optimize(
            training
        )

        if results.empty:
            raise RuntimeError(
                "Optimizer returned no results."
            )

        eligible_results = results[
            results["eligible"] == True
        ]

        if eligible_results.empty:
            raise RuntimeError(
                "No eligible optimization "
                "results were found."
            )

        return eligible_results.iloc[0]

    def evaluate_parameters(
        self,
        dataframe: pd.DataFrame,
        parameters: pd.Series,
    ) -> Dict[str, Any]:
        if dataframe.empty:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "win_rate": 0.0,
                "loss_rate": 0.0,
                "total_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "average_r": 0.0,
                "max_drawdown": 0.0,
                "ending_balance": (
                    self.initial_balance
                ),
                "trades": [],
            }

        return self.evaluator.evaluate_orb(
            dataframe=dataframe,
            opening_range_minutes=int(
                parameters[
                    "opening_range_minutes"
                ]
            ),
            stop_atr_multiplier=float(
                parameters[
                    "stop_atr_multiplier"
                ]
            ),
            target_atr_multiplier=float(
                parameters[
                    "target_atr_multiplier"
                ]
            ),
            minimum_rsi=float(
                parameters[
                    "minimum_rsi"
                ]
            ),
            maximum_rsi=float(
                parameters[
                    "maximum_rsi"
                ]
            ),
            minimum_volume_ratio=float(
                parameters[
                    "minimum_volume_ratio"
                ]
            ),
        )

    def _extract_training_result(
        self,
        best_parameters: pd.Series,
    ) -> Dict[str, Any]:
        return {
            "total_trades": int(
                best_parameters[
                    "total_trades"
                ]
            ),
            "win_rate": float(
                best_parameters[
                    "win_rate"
                ]
            ),
            "total_pnl": float(
                best_parameters[
                    "total_pnl"
                ]
            ),
            "profit_factor": float(
                best_parameters[
                    "profit_factor"
                ]
            ),
            "expectancy": float(
                best_parameters[
                    "expectancy"
                ]
            ),
            "average_r": float(
                best_parameters[
                    "average_r"
                ]
            ),
            "max_drawdown": float(
                best_parameters[
                    "max_drawdown"
                ]
            ),
        }

    def _print_best_parameters(
        self,
        best: pd.Series,
    ) -> None:
        print()
        print("=" * 60)
        print("BEST TRAINING PARAMETERS")
        print("=" * 60)

        print(
            "Opening range      :",
            int(
                best[
                    "opening_range_minutes"
                ]
            ),
        )

        print(
            "Stop ATR multiplier:",
            float(
                best[
                    "stop_atr_multiplier"
                ]
            ),
        )

        print(
            "Target ATR mult.   :",
            float(
                best[
                    "target_atr_multiplier"
                ]
            ),
        )

        print(
            "Minimum RSI        :",
            float(
                best[
                    "minimum_rsi"
                ]
            ),
        )

        print(
            "Maximum RSI        :",
            float(
                best[
                    "maximum_rsi"
                ]
            ),
        )

        print(
            "Minimum volume     :",
            float(
                best[
                    "minimum_volume_ratio"
                ]
            ),
        )

    def _print_result(
        self,
        title: str,
        result: Dict[str, Any],
    ) -> None:
        print()
        print("=" * 60)
        print(title)
        print("=" * 60)

        display_keys = [
            "total_trades",
            "wins",
            "losses",
            "breakeven",
            "win_rate",
            "loss_rate",
            "total_pnl",
            "gross_profit",
            "gross_loss",
            "average_win",
            "average_loss",
            "profit_factor",
            "expectancy",
            "average_r",
            "max_drawdown",
            "ending_balance",
        ]

        for key in display_keys:
            if key in result:
                print(
                    f"{key}: "
                    f"{result[key]}"
                )

    def run_walk_forward(
        self,
        year: int = 2025,
        training_end_month: int = 9,
    ) -> Optional[Dict[str, Any]]:
        split = self.run_split_test(
            year=year,
            training_end_month=training_end_month,
        )

        if split is None:
            return None

        if split.training.empty:
            print(
                "Training dataset is empty."
            )
            return None

        if split.testing.empty:
            print(
                "Testing dataset is empty."
            )
            return None

        print()
        print("=" * 60)
        print("OPTIMIZING TRAINING DATA")
        print("=" * 60)

        best = self.optimize_training(
            split.training
        )

        self._print_best_parameters(
            best
        )

        training_result = (
            self._extract_training_result(
                best
            )
        )

        testing_result = (
            self.evaluate_parameters(
                dataframe=split.testing,
                parameters=best,
            )
        )

        self._print_result(
            title="TRAINING RESULTS",
            result=training_result,
        )

        self._print_result(
            title="OUT-OF-SAMPLE TEST RESULTS",
            result=testing_result,
        )

        profit_factor_change = (
            float(
                testing_result.get(
                    "profit_factor",
                    0.0,
                )
            )
            - float(
                training_result.get(
                    "profit_factor",
                    0.0,
                )
            )
        )

        average_r_change = (
            float(
                testing_result.get(
                    "average_r",
                    0.0,
                )
            )
            - float(
                training_result.get(
                    "average_r",
                    0.0,
                )
            )
        )

        print()
        print("=" * 60)
        print("GENERALIZATION SUMMARY")
        print("=" * 60)

        print(
            "Training profit factor :",
            training_result[
                "profit_factor"
            ],
        )

        print(
            "Testing profit factor  :",
            testing_result.get(
                "profit_factor",
                0.0,
            ),
        )

        print(
            "Profit factor change   :",
            round(
                profit_factor_change,
                4,
            ),
        )

        print(
            "Training average R     :",
            training_result[
                "average_r"
            ],
        )

        print(
            "Testing average R      :",
            testing_result.get(
                "average_r",
                0.0,
            ),
        )

        print(
            "Average R change       :",
            round(
                average_r_change,
                4,
            ),
        )

        return {
            "symbol": self.symbol,
            "year": year,
            "training_end_month": (
                training_end_month
            ),
            "best_parameters": (
                best.to_dict()
            ),
            "training_result": (
                training_result
            ),
            "testing_result": (
                testing_result
            ),
            "profit_factor_change": (
                profit_factor_change
            ),
            "average_r_change": (
                average_r_change
            ),
        }


if __name__ == "__main__":
    validator = WalkForwardValidator(
        symbol="RELIANCE",
        interval_name="5m",
        initial_balance=100000.0,
    )

    validator.run_walk_forward(
        year=2025,
        training_end_month=9,
    )
"""
Reusable multi-stock strategy optimization engine.

This module tests every parameter combination across multiple symbols,
aggregates the results, and ranks configurations by combined performance.
"""

from itertools import product
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd

from research.base_strategy_evaluator import BaseStrategyEvaluator
from research.dataset_builder import DatasetBuilder


StrategyFactory = Callable[..., Any]


class MultiStockOptimizer:
    """
    Optimize any compatible strategy across multiple stocks.

    Parameters
    ----------
    strategy_factory:
        Strategy class or callable used to create a strategy instance.

    parameter_grid:
        Dictionary containing parameter names and candidate values.

        Example:

        {
            "lookback_period": [8, 10, 15],
            "minimum_rsi": [55.0, 60.0],
        }

    symbols:
        Symbols on which every configuration will be evaluated.
    """

    def __init__(
        self,
        strategy_factory: StrategyFactory,
        parameter_grid: Dict[str, Sequence[Any]],
        symbols: Sequence[str],
        interval_name: str = "5m",
        year: int = 2025,
        initial_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_position_percent: float = 20.0,
        slippage_bps: float = 5.0,
        minimum_total_trades: int = 20,
        dataset_builder: Optional[DatasetBuilder] = None,
    ) -> None:
        if not parameter_grid:
            raise ValueError(
                "parameter_grid cannot be empty."
            )

        if not symbols:
            raise ValueError(
                "At least one symbol is required."
            )

        if minimum_total_trades < 1:
            raise ValueError(
                "minimum_total_trades must be at least 1."
            )

        self.strategy_factory = strategy_factory
        self.parameter_grid = parameter_grid
        self.symbols = list(symbols)

        self.interval_name = interval_name
        self.year = year

        self.initial_balance = initial_balance
        self.risk_per_trade_percent = (
            risk_per_trade_percent
        )
        self.max_position_percent = (
            max_position_percent
        )
        self.slippage_bps = slippage_bps

        self.minimum_total_trades = (
            minimum_total_trades
        )

        self.dataset_builder = (
            dataset_builder or DatasetBuilder()
        )

        self.datasets: Dict[str, pd.DataFrame] = {}

    def load_datasets(self) -> Dict[str, pd.DataFrame]:
        """
        Load and cache the dataset for every requested symbol.
        """

        print()
        print("LOADING MULTI-STOCK DATASETS")
        print("=" * 70)

        self.datasets = {}

        for index, symbol in enumerate(
            self.symbols,
            start=1,
        ):
            print(
                f"[{index}/{len(self.symbols)}] "
                f"Loading {symbol}..."
            )

            try:
                dataset = (
                    self.dataset_builder.build_dataset(
                        symbol=symbol,
                        interval_name=self.interval_name,
                        year=self.year,
                    )
                )
            except Exception as error:
                print(
                    f"Skipped {symbol}: {error}"
                )
                continue

            if dataset is None or dataset.empty:
                print(
                    f"Skipped {symbol}: empty dataset."
                )
                continue

            self.datasets[symbol] = dataset

            print(
                f"Loaded {symbol}: "
                f"{len(dataset)} rows"
            )

        if not self.datasets:
            raise RuntimeError(
                "No valid datasets were loaded."
            )

        print()
        print(
            f"Successfully loaded "
            f"{len(self.datasets)} datasets."
        )

        return self.datasets

    def _build_parameter_combinations(
        self,
    ) -> List[Dict[str, Any]]:
        parameter_names = list(
            self.parameter_grid.keys()
        )

        parameter_values = [
            self.parameter_grid[name]
            for name in parameter_names
        ]

        combinations: List[Dict[str, Any]] = []

        for values in product(*parameter_values):
            combinations.append(
                dict(
                    zip(
                        parameter_names,
                        values,
                    )
                )
            )

        return combinations

    def _evaluate_symbol(
        self,
        strategy_parameters: Dict[str, Any],
        dataset: pd.DataFrame,
    ) -> Dict[str, Any]:
        strategy = self.strategy_factory(
            **strategy_parameters
        )

        evaluator = BaseStrategyEvaluator(
            strategy=strategy,
            initial_balance=self.initial_balance,
            risk_per_trade_percent=(
                self.risk_per_trade_percent
            ),
            max_position_percent=(
                self.max_position_percent
            ),
            slippage_bps=self.slippage_bps,
        )

        return evaluator.evaluate(dataset)

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            converted = float(value)

            if pd.isna(converted):
                return default

            return converted
        except (TypeError, ValueError):
            return default

    def optimize(
        self,
    ) -> Dict[str, pd.DataFrame]:
        """
        Run every parameter combination across all loaded symbols.

        Returns
        -------
        Dictionary containing:

        - summary:
          One aggregated row per parameter combination.

        - symbol_results:
          One row per combination and symbol.
        """

        if not self.datasets:
            self.load_datasets()

        parameter_combinations = (
            self._build_parameter_combinations()
        )

        total_combinations = len(
            parameter_combinations
        )

        print()
        print("=" * 90)
        print(
            "RUNNING MULTI-STOCK OPTIMIZATION"
        )
        print("=" * 90)
        print(
            f"Configurations: {total_combinations}"
        )
        print(
            f"Symbols: {len(self.datasets)}"
        )
        print(
            "Total evaluations: "
            f"{total_combinations * len(self.datasets)}"
        )
        print()

        summary_rows: List[
            Dict[str, Any]
        ] = []

        symbol_rows: List[
            Dict[str, Any]
        ] = []

        for combination_number, parameters in enumerate(
            parameter_combinations,
            start=1,
        ):
            parameter_text = " ".join(
                f"{name}={value}"
                for name, value in parameters.items()
            )

            print(
                f"[{combination_number}/"
                f"{total_combinations}] "
                f"{parameter_text}"
            )

            total_trades = 0
            profitable_symbols = 0
            losing_symbols = 0
            breakeven_symbols = 0

            combined_pnl = 0.0
            gross_profit = 0.0
            gross_loss = 0.0

            weighted_wins = 0.0
            completed_symbols = 0

            for symbol, dataset in (
                self.datasets.items()
            ):
                try:
                    result = self._evaluate_symbol(
                        strategy_parameters=parameters,
                        dataset=dataset,
                    )
                except Exception as error:
                    print(
                        f"  {symbol}: evaluation "
                        f"failed — {error}"
                    )
                    continue

                trades = int(
                    result.get(
                        "total_trades",
                        0,
                    )
                )

                win_rate = self._safe_float(
                    result.get(
                        "win_rate",
                        0.0,
                    )
                )

                net_pnl = self._safe_float(
                    result.get(
                        "total_pnl",
                        0.0,
                    )
                )

                profit_factor = self._safe_float(
                    result.get(
                        "profit_factor",
                        0.0,
                    )
                )

                symbol_row = {
                    **parameters,
                    "symbol": symbol,
                    "trades": trades,
                    "win_rate": win_rate,
                    "net_pnl": net_pnl,
                    "profit_factor": profit_factor,
                }

                symbol_rows.append(symbol_row)

                total_trades += trades
                combined_pnl += net_pnl
                weighted_wins += (
                    trades * win_rate / 100.0
                )

                completed_symbols += 1

                if net_pnl > 0:
                    profitable_symbols += 1
                    gross_profit += net_pnl
                elif net_pnl < 0:
                    losing_symbols += 1
                    gross_loss += abs(net_pnl)
                else:
                    breakeven_symbols += 1

            if total_trades > 0:
                combined_win_rate = (
                    weighted_wins
                    / total_trades
                    * 100.0
                )
            else:
                combined_win_rate = 0.0

            if gross_loss > 0:
                portfolio_profit_factor = (
                    gross_profit / gross_loss
                )
            elif gross_profit > 0:
                portfolio_profit_factor = (
                    float("inf")
                )
            else:
                portfolio_profit_factor = 0.0

            if completed_symbols > 0:
                average_pnl_per_symbol = (
                    combined_pnl
                    / completed_symbols
                )

                profitable_symbol_percent = (
                    profitable_symbols
                    / completed_symbols
                    * 100.0
                )
            else:
                average_pnl_per_symbol = 0.0
                profitable_symbol_percent = 0.0

            eligible_for_ranking = (
                total_trades
                >= self.minimum_total_trades
                and completed_symbols > 0
            )

            summary_rows.append(
                {
                    **parameters,
                    "symbols_tested": (
                        completed_symbols
                    ),
                    "profitable_symbols": (
                        profitable_symbols
                    ),
                    "losing_symbols": (
                        losing_symbols
                    ),
                    "breakeven_symbols": (
                        breakeven_symbols
                    ),
                    "profitable_symbol_percent": (
                        profitable_symbol_percent
                    ),
                    "total_trades": total_trades,
                    "combined_win_rate": (
                        combined_win_rate
                    ),
                    "combined_net_pnl": (
                        combined_pnl
                    ),
                    "average_pnl_per_symbol": (
                        average_pnl_per_symbol
                    ),
                    "portfolio_profit_factor": (
                        portfolio_profit_factor
                    ),
                    "eligible_for_ranking": (
                        eligible_for_ranking
                    ),
                }
            )

        summary_dataframe = pd.DataFrame(
            summary_rows
        )

        symbol_dataframe = pd.DataFrame(
            symbol_rows
        )

        if not summary_dataframe.empty:
            summary_dataframe = (
                summary_dataframe.sort_values(
                    by=[
                        "eligible_for_ranking",
                        "combined_net_pnl",
                        "profitable_symbol_percent",
                        "portfolio_profit_factor",
                        "total_trades",
                    ],
                    ascending=[
                        False,
                        False,
                        False,
                        False,
                        False,
                    ],
                ).reset_index(drop=True)
            )

        return {
            "summary": summary_dataframe,
            "symbol_results": symbol_dataframe,
        }

    def get_valid_results(
        self,
        summary_dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Return only configurations with sufficient trades.
        """

        if summary_dataframe.empty:
            return summary_dataframe.copy()

        if (
            "eligible_for_ranking"
            not in summary_dataframe.columns
        ):
            raise KeyError(
                "The summary dataframe does not contain "
                "'eligible_for_ranking'."
            )

        valid_results = summary_dataframe[
            summary_dataframe[
                "eligible_for_ranking"
            ]
        ].copy()

        return valid_results.reset_index(
            drop=True
        )

    @staticmethod
    def save_results(
        results: Dict[str, pd.DataFrame],
        summary_path: str,
        symbol_results_path: str,
    ) -> None:
        """
        Save aggregated and per-symbol results to CSV.
        """

        summary_dataframe = results[
            "summary"
        ]

        symbol_dataframe = results[
            "symbol_results"
        ]

        summary_dataframe.to_csv(
            summary_path,
            index=False,
        )

        symbol_dataframe.to_csv(
            symbol_results_path,
            index=False,
        )

        print()
        print(
            f"Summary saved to: {summary_path}"
        )
        print(
            "Per-symbol results saved to: "
            f"{symbol_results_path}"
        )
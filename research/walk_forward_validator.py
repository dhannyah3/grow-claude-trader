"""
Generic multi-stock walk-forward validation engine.

The engine repeatedly:

1. Optimizes strategy parameters on a training window.
2. Freezes the best parameters.
3. Evaluates those parameters on the next unseen test window.
4. Moves forward and repeats the process.

Only out-of-sample test results are used for final validation.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd

from research.base_strategy_evaluator import BaseStrategyEvaluator
from research.dataset_builder import DatasetBuilder
from research.multistock_optimizer import MultiStockOptimizer


StrategyFactory = Callable[..., Any]


class WalkForwardValidator:
    """
    Perform rolling walk-forward validation across multiple stocks.

    Parameters
    ----------
    strategy_factory:
        Strategy class or function that creates a strategy instance.

    parameter_grid:
        Parameters to test during each training-window optimization.

    symbols:
        Symbols included in the validation.

    train_days:
        Number of trading days used for optimization.

    test_days:
        Number of unseen trading days used for validation.

    step_days:
        Number of trading days to move forward after each fold.
        Defaults to test_days.

    minimum_training_trades:
        Minimum combined trades required for a training configuration
        to qualify for selection.

    minimum_test_trades:
        Minimum combined trades required for a test fold to be marked
        as eligible.
    """

    def __init__(
        self,
        strategy_factory: StrategyFactory,
        parameter_grid: Dict[str, Sequence[Any]],
        symbols: Sequence[str],
        train_days: int = 120,
        test_days: int = 30,
        step_days: Optional[int] = None,
        interval_name: str = "5m",
        year: int = 2025,
        initial_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_position_percent: float = 20.0,
        slippage_bps: float = 5.0,
        minimum_training_trades: int = 30,
        minimum_test_trades: int = 1,
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

        if train_days < 1:
            raise ValueError(
                "train_days must be at least 1."
            )

        if test_days < 1:
            raise ValueError(
                "test_days must be at least 1."
            )

        resolved_step_days = (
            step_days
            if step_days is not None
            else test_days
        )

        if resolved_step_days < 1:
            raise ValueError(
                "step_days must be at least 1."
            )

        if minimum_training_trades < 1:
            raise ValueError(
                "minimum_training_trades must be at least 1."
            )

        if minimum_test_trades < 1:
            raise ValueError(
                "minimum_test_trades must be at least 1."
            )

        self.strategy_factory = strategy_factory
        self.parameter_grid = parameter_grid
        self.symbols = list(symbols)

        self.train_days = train_days
        self.test_days = test_days
        self.step_days = resolved_step_days

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

        self.minimum_training_trades = (
            minimum_training_trades
        )
        self.minimum_test_trades = (
            minimum_test_trades
        )

        self.dataset_builder = (
            dataset_builder or DatasetBuilder()
        )

        self.datasets: Dict[str, pd.DataFrame] = {}
        self.trading_dates: List[pd.Timestamp] = []

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

    @staticmethod
    def _prepare_datetime_index(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Return a copy with a valid timestamp column.

        Supports datasets where time is stored in:

        - the existing DataFrame index
        - timestamp
        - datetime
        - date
        - time
        """

        prepared = dataframe.copy()

        if isinstance(
            prepared.index,
            pd.DatetimeIndex,
        ):
            datetime_index = pd.to_datetime(
                prepared.index,
                errors="coerce",
            )
        else:
            timestamp_column = None

            candidate_columns = [
                "timestamp",
                "datetime",
                "date_time",
                "date",
                "time",
            ]

            for candidate in candidate_columns:
                if candidate in prepared.columns:
                    timestamp_column = candidate
                    break

            if timestamp_column is None:
                raise ValueError(
                    "Dataset must contain a DatetimeIndex "
                    "or a supported timestamp column."
                )

            datetime_index = pd.to_datetime(
                prepared[timestamp_column],
                errors="coerce",
            )

        valid_rows = ~pd.isna(datetime_index)

        prepared = prepared.loc[
            valid_rows
        ].copy()

        prepared["timestamp"] = pd.to_datetime(
            datetime_index[valid_rows]
        )

        prepared = (
            prepared.sort_values("timestamp")
            .reset_index(drop=True)
        )

        return prepared

    def load_datasets(
        self,
    ) -> Dict[str, pd.DataFrame]:
        """
        Load, normalize, and cache every requested dataset.
        """

        print()
        print("LOADING WALK-FORWARD DATASETS")
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

                if dataset is None or dataset.empty:
                    print(
                        f"Skipped {symbol}: empty dataset."
                    )
                    continue

                prepared = (
                    self._prepare_datetime_index(
                        dataset
                    )
                )

            except Exception as error:
                print(
                    f"Skipped {symbol}: {error}"
                )
                continue

            if prepared.empty:
                print(
                    f"Skipped {symbol}: no valid rows."
                )
                continue

            self.datasets[symbol] = prepared

            symbol_dates = (
                prepared["timestamp"]
                .dt.normalize()
                .unique()
            )

            print(
                f"Loaded {symbol}: "
                f"{len(prepared)} rows, "
                f"{len(symbol_dates)} trading days"
            )

        if not self.datasets:
            raise RuntimeError(
                "No valid datasets were loaded."
            )

        all_dates = set()

        for dataset in self.datasets.values():
            all_dates.update(
                dataset["timestamp"]
                .dt.normalize()
                .unique()
            )

        self.trading_dates = sorted(
            pd.Timestamp(date)
            for date in all_dates
        )

        required_days = (
            self.train_days + self.test_days
        )

        if len(self.trading_dates) < required_days:
            raise RuntimeError(
                "Not enough trading days for walk-forward "
                f"validation. Required: {required_days}, "
                f"available: {len(self.trading_dates)}."
            )

        print()
        print(
            f"Successfully loaded "
            f"{len(self.datasets)} datasets."
        )
        print(
            f"Combined trading calendar: "
            f"{len(self.trading_dates)} days"
        )

        return self.datasets

    @staticmethod
    def _slice_dataset(
        dataframe: pd.DataFrame,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> pd.DataFrame:
        """
        Slice a dataset using inclusive trading dates.
        """

        normalized_dates = (
            dataframe["timestamp"]
            .dt.normalize()
        )

        mask = (
            (normalized_dates >= start_date)
            & (normalized_dates <= end_date)
        )

        return (
            dataframe.loc[mask]
            .copy()
            .reset_index(drop=True)
        )

    def _build_window_datasets(
        self,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> Dict[str, pd.DataFrame]:
        """
        Build symbol datasets for one train or test window.
        """

        window_datasets: Dict[
            str,
            pd.DataFrame
        ] = {}

        for symbol, dataset in (
            self.datasets.items()
        ):
            sliced = self._slice_dataset(
                dataframe=dataset,
                start_date=start_date,
                end_date=end_date,
            )

            if not sliced.empty:
                window_datasets[symbol] = sliced

        return window_datasets

    def _optimize_training_window(
        self,
        training_datasets: Dict[
            str,
            pd.DataFrame
        ],
    ) -> Dict[str, Any]:
        """
        Optimize parameters only on the training datasets.
        """

        optimizer = MultiStockOptimizer(
            strategy_factory=self.strategy_factory,
            parameter_grid=self.parameter_grid,
            symbols=list(
                training_datasets.keys()
            ),
            interval_name=self.interval_name,
            year=self.year,
            initial_balance=self.initial_balance,
            risk_per_trade_percent=(
                self.risk_per_trade_percent
            ),
            max_position_percent=(
                self.max_position_percent
            ),
            slippage_bps=self.slippage_bps,
            minimum_total_trades=(
                self.minimum_training_trades
            ),
            dataset_builder=self.dataset_builder,
        )

        # Prevent the optimizer from reloading full-year data.
        optimizer.datasets = training_datasets

        optimization_results = optimizer.optimize()

        valid_results = (
            optimizer.get_valid_results(
                optimization_results["summary"]
            )
        )

        if valid_results.empty:
            raise RuntimeError(
                "No training configuration produced "
                "enough trades to qualify."
            )

        best_row = valid_results.iloc[0]

        parameter_names = list(
            self.parameter_grid.keys()
        )

        best_parameters = {
            name: best_row[name]
            for name in parameter_names
        }

        return {
            "parameters": best_parameters,
            "training_result": best_row.to_dict(),
            "optimization_summary": (
                optimization_results["summary"]
            ),
        }

    def _evaluate_test_symbol(
        self,
        parameters: Dict[str, Any],
        dataset: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Evaluate frozen parameters on one unseen test dataset.
        """

        strategy = self.strategy_factory(
            **parameters
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

    def _evaluate_test_window(
        self,
        fold_number: int,
        parameters: Dict[str, Any],
        test_datasets: Dict[str, pd.DataFrame],
        train_start: pd.Timestamp,
        train_end: pd.Timestamp,
        test_start: pd.Timestamp,
        test_end: pd.Timestamp,
    ) -> Dict[str, Any]:
        """
        Evaluate frozen parameters across all test symbols.
        """

        symbol_rows: List[
            Dict[str, Any]
        ] = []

        total_trades = 0
        weighted_wins = 0.0
        combined_pnl = 0.0

        profitable_symbols = 0
        losing_symbols = 0
        breakeven_symbols = 0

        gross_profit = 0.0
        gross_loss = 0.0

        completed_symbols = 0

        for symbol, dataset in (
            test_datasets.items()
        ):
            try:
                result = self._evaluate_test_symbol(
                    parameters=parameters,
                    dataset=dataset,
                )
            except Exception as error:
                print(
                    f"  Test failed for {symbol}: "
                    f"{error}"
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

            symbol_rows.append(
                {
                    "fold": fold_number,
                    "train_start": train_start.date(),
                    "train_end": train_end.date(),
                    "test_start": test_start.date(),
                    "test_end": test_end.date(),
                    **parameters,
                    "symbol": symbol,
                    "test_trades": trades,
                    "test_win_rate": win_rate,
                    "test_net_pnl": net_pnl,
                    "test_profit_factor": (
                        profit_factor
                    ),
                }
            )

            total_trades += trades
            weighted_wins += (
                trades * win_rate / 100.0
            )
            combined_pnl += net_pnl
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

        return {
            "summary": {
                "fold": fold_number,
                "train_start": train_start.date(),
                "train_end": train_end.date(),
                "test_start": test_start.date(),
                "test_end": test_end.date(),
                **parameters,
                "test_symbols": completed_symbols,
                "profitable_symbols": (
                    profitable_symbols
                ),
                "losing_symbols": losing_symbols,
                "breakeven_symbols": (
                    breakeven_symbols
                ),
                "profitable_symbol_percent": (
                    profitable_symbol_percent
                ),
                "test_total_trades": total_trades,
                "test_combined_win_rate": (
                    combined_win_rate
                ),
                "test_combined_net_pnl": (
                    combined_pnl
                ),
                "test_average_pnl_per_symbol": (
                    average_pnl_per_symbol
                ),
                "test_portfolio_profit_factor": (
                    portfolio_profit_factor
                ),
                "eligible_test_fold": (
                    total_trades
                    >= self.minimum_test_trades
                ),
            },
            "symbol_results": symbol_rows,
        }

    def run(
        self,
    ) -> Dict[str, pd.DataFrame]:
        """
        Execute all walk-forward folds.

        Returns
        -------
        Dictionary containing:

        - folds:
          One row per walk-forward test fold.

        - symbol_results:
          One row per fold and test symbol.

        - parameter_history:
          Best parameters selected during every training fold.
        """

        if not self.datasets:
            self.load_datasets()

        fold_rows: List[
            Dict[str, Any]
        ] = []

        symbol_rows: List[
            Dict[str, Any]
        ] = []

        parameter_rows: List[
            Dict[str, Any]
        ] = []

        start_index = 0
        fold_number = 1

        while True:
            train_start_index = start_index
            train_end_index = (
                train_start_index
                + self.train_days
                - 1
            )

            test_start_index = (
                train_end_index + 1
            )

            test_end_index = (
                test_start_index
                + self.test_days
                - 1
            )

            if test_end_index >= len(
                self.trading_dates
            ):
                break

            train_start = self.trading_dates[
                train_start_index
            ]

            train_end = self.trading_dates[
                train_end_index
            ]

            test_start = self.trading_dates[
                test_start_index
            ]

            test_end = self.trading_dates[
                test_end_index
            ]

            print()
            print("=" * 90)
            print(
                f"WALK-FORWARD FOLD {fold_number}"
            )
            print("=" * 90)
            print(
                f"Training: "
                f"{train_start.date()} → "
                f"{train_end.date()}"
            )
            print(
                f"Testing:  "
                f"{test_start.date()} → "
                f"{test_end.date()}"
            )

            training_datasets = (
                self._build_window_datasets(
                    start_date=train_start,
                    end_date=train_end,
                )
            )

            test_datasets = (
                self._build_window_datasets(
                    start_date=test_start,
                    end_date=test_end,
                )
            )

            if not training_datasets:
                print(
                    "Skipped fold: no training data."
                )
                start_index += self.step_days
                fold_number += 1
                continue

            if not test_datasets:
                print(
                    "Skipped fold: no test data."
                )
                start_index += self.step_days
                fold_number += 1
                continue

            try:
                training_output = (
                    self._optimize_training_window(
                        training_datasets
                    )
                )
            except Exception as error:
                print(
                    f"Skipped fold: training "
                    f"optimization failed — {error}"
                )

                start_index += self.step_days
                fold_number += 1
                continue

            best_parameters = training_output[
                "parameters"
            ]

            training_result = training_output[
                "training_result"
            ]

            print()
            print(
                "Selected parameters:"
            )

            for name, value in (
                best_parameters.items()
            ):
                print(
                    f"  {name}: {value}"
                )

            parameter_rows.append(
                {
                    "fold": fold_number,
                    "train_start": train_start.date(),
                    "train_end": train_end.date(),
                    "test_start": test_start.date(),
                    "test_end": test_end.date(),
                    **best_parameters,
                    "training_total_trades": (
                        training_result.get(
                            "total_trades",
                            0,
                        )
                    ),
                    "training_net_pnl": (
                        training_result.get(
                            "combined_net_pnl",
                            0.0,
                        )
                    ),
                    "training_win_rate": (
                        training_result.get(
                            "combined_win_rate",
                            0.0,
                        )
                    ),
                    "training_profit_factor": (
                        training_result.get(
                            "portfolio_profit_factor",
                            0.0,
                        )
                    ),
                }
            )

            test_output = (
                self._evaluate_test_window(
                    fold_number=fold_number,
                    parameters=best_parameters,
                    test_datasets=test_datasets,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )

            fold_summary = test_output[
                "summary"
            ]

            fold_rows.append(
                fold_summary
            )

            symbol_rows.extend(
                test_output["symbol_results"]
            )

            print()
            print("OUT-OF-SAMPLE RESULT")
            print(
                f"Trades: "
                f"{fold_summary['test_total_trades']}"
            )
            print(
                f"Win rate: "
                f"{fold_summary['test_combined_win_rate']:.2f}%"
            )
            print(
                f"Net P&L: "
                f"{fold_summary['test_combined_net_pnl']:.2f}"
            )
            print(
                f"Profitable symbols: "
                f"{fold_summary['profitable_symbols']}/"
                f"{fold_summary['test_symbols']}"
            )

            start_index += self.step_days
            fold_number += 1

        folds_dataframe = pd.DataFrame(
            fold_rows
        )

        symbol_dataframe = pd.DataFrame(
            symbol_rows
        )

        parameter_dataframe = pd.DataFrame(
            parameter_rows
        )

        if folds_dataframe.empty:
            raise RuntimeError(
                "Walk-forward validation produced "
                "no completed folds."
            )

        return {
            "folds": folds_dataframe,
            "symbol_results": symbol_dataframe,
            "parameter_history": (
                parameter_dataframe
            ),
        }

    @staticmethod
    def build_overall_summary(
        folds_dataframe: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Aggregate all completed out-of-sample folds.
        """

        if folds_dataframe.empty:
            return {
                "completed_folds": 0,
                "total_test_trades": 0,
                "combined_test_pnl": 0.0,
                "weighted_test_win_rate": 0.0,
                "profitable_folds": 0,
                "profitable_fold_percent": 0.0,
                "average_pnl_per_fold": 0.0,
            }

        completed_folds = len(
            folds_dataframe
        )

        total_test_trades = int(
            folds_dataframe[
                "test_total_trades"
            ].sum()
        )

        combined_test_pnl = float(
            folds_dataframe[
                "test_combined_net_pnl"
            ].sum()
        )

        profitable_folds = int(
            (
                folds_dataframe[
                    "test_combined_net_pnl"
                ]
                > 0
            ).sum()
        )

        if total_test_trades > 0:
            weighted_test_win_rate = float(
                (
                    folds_dataframe[
                        "test_combined_win_rate"
                    ]
                    * folds_dataframe[
                        "test_total_trades"
                    ]
                ).sum()
                / total_test_trades
            )
        else:
            weighted_test_win_rate = 0.0

        profitable_fold_percent = (
            profitable_folds
            / completed_folds
            * 100.0
        )

        average_pnl_per_fold = (
            combined_test_pnl
            / completed_folds
        )

        return {
            "completed_folds": completed_folds,
            "total_test_trades": (
                total_test_trades
            ),
            "combined_test_pnl": (
                combined_test_pnl
            ),
            "weighted_test_win_rate": (
                weighted_test_win_rate
            ),
            "profitable_folds": (
                profitable_folds
            ),
            "profitable_fold_percent": (
                profitable_fold_percent
            ),
            "average_pnl_per_fold": (
                average_pnl_per_fold
            ),
        }

    @staticmethod
    def save_results(
        results: Dict[str, pd.DataFrame],
        folds_path: str,
        symbol_results_path: str,
        parameter_history_path: str,
    ) -> None:
        """
        Save all walk-forward result tables.
        """

        results["folds"].to_csv(
            folds_path,
            index=False,
        )

        results["symbol_results"].to_csv(
            symbol_results_path,
            index=False,
        )

        results["parameter_history"].to_csv(
            parameter_history_path,
            index=False,
        )

        print()
        print(
            f"Fold results saved to: "
            f"{folds_path}"
        )
        print(
            f"Symbol results saved to: "
            f"{symbol_results_path}"
        )
        print(
            f"Parameter history saved to: "
            f"{parameter_history_path}"
        )
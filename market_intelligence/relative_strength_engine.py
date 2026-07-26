"""
Relative Strength Engine.

Compares stock performance against a benchmark across multiple
lookback periods and produces cross-sectional rankings.

This is a research and market-intelligence component. It does not
place trades or generate execution instructions.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

import pandas as pd

from market_intelligence.benchmark import BenchmarkEngine


@dataclass(frozen=True)
class RelativeStrengthResult:
    symbol: str
    weighted_stock_return: float
    weighted_benchmark_return: float
    relative_return: float
    relative_strength_score: float
    percentile_rank: float
    rank: int
    observations: int


class RelativeStrengthEngine:
    """
    Calculate and rank relative strength across a stock universe.

    Parameters
    ----------
    benchmark_engine:
        Existing BenchmarkEngine instance. A new instance is created
        when one is not supplied.
    lookbacks:
        Trading-day return windows used for relative-strength scoring.
    weights:
        Weight assigned to each lookback. Weights are normalized
        automatically and must match the configured lookbacks.
    """

    def __init__(
        self,
        benchmark_engine: Optional[
            BenchmarkEngine
        ] = None,
        lookbacks: Sequence[int] = (
            5,
            10,
            20,
            50,
        ),
        weights: Optional[
            Mapping[int, float]
        ] = None,
    ) -> None:
        self.benchmark_engine = (
            benchmark_engine
            or BenchmarkEngine()
        )

        self.lookbacks = tuple(
            int(value)
            for value in lookbacks
        )

        if not self.lookbacks:
            raise ValueError(
                "At least one lookback is required."
            )

        if any(
            lookback <= 0
            for lookback in self.lookbacks
        ):
            raise ValueError(
                "Every lookback must be greater than zero."
            )

        default_weights: Dict[
            int,
            float,
        ] = {
            5: 0.10,
            10: 0.20,
            20: 0.30,
            50: 0.40,
        }

        configured_weights = (
            dict(weights)
            if weights is not None
            else {
                lookback: default_weights.get(
                    lookback,
                    1.0,
                )
                for lookback in self.lookbacks
            }
        )

        missing_weights = (
            set(self.lookbacks)
            - set(configured_weights)
        )

        if missing_weights:
            raise ValueError(
                "Weights are missing for lookbacks: "
                f"{sorted(missing_weights)}"
            )

        selected_weights = {
            lookback: float(
                configured_weights[lookback]
            )
            for lookback in self.lookbacks
        }

        if any(
            weight < 0
            for weight in selected_weights.values()
        ):
            raise ValueError(
                "Relative-strength weights cannot be negative."
            )

        total_weight = sum(
            selected_weights.values()
        )

        if total_weight <= 0:
            raise ValueError(
                "Relative-strength weights must total "
                "more than zero."
            )

        self.weights = {
            lookback: weight / total_weight
            for lookback, weight
            in selected_weights.items()
        }

    def prepare_price_data(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prepare intraday or daily price data as one close per day.
        """

        required_columns = {
            "timestamp",
            "close",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Price data is missing required columns: "
                f"{sorted(missing_columns)}"
            )

        prepared = dataframe.copy()

        prepared["timestamp"] = pd.to_datetime(
            prepared["timestamp"],
            errors="coerce",
        )

        prepared["close"] = pd.to_numeric(
            prepared["close"],
            errors="coerce",
        )

        prepared = prepared.dropna(
            subset=[
                "timestamp",
                "close",
            ]
        )

        prepared = prepared[
            prepared["close"] > 0
        ]

        prepared = prepared.sort_values(
            "timestamp"
        )

        prepared = prepared.drop_duplicates(
            subset=["timestamp"],
            keep="last",
        )

        daily = (
            prepared.set_index("timestamp")
            .resample("1D")
            .agg(
                {
                    "close": "last",
                }
            )
            .dropna(
                subset=["close"]
            )
            .reset_index()
        )

        return daily

    def align_with_benchmark(
        self,
        stock_data: pd.DataFrame,
        benchmark_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Align stock and benchmark closes using common trading dates.
        """

        stock_daily = self.prepare_price_data(
            stock_data
        ).rename(
            columns={
                "close": "stock_close",
            }
        )

        benchmark_daily = (
            self.prepare_price_data(
                benchmark_data
            )
            .rename(
                columns={
                    "close": "benchmark_close",
                }
            )
        )

        aligned = pd.merge(
            stock_daily,
            benchmark_daily,
            on="timestamp",
            how="inner",
        )

        aligned = aligned.sort_values(
            "timestamp"
        )

        aligned = aligned.reset_index(
            drop=True
        )

        return aligned

    def calculate_period_return(
        self,
        close_series: pd.Series,
        lookback: int,
    ) -> float:
        required_rows = lookback + 1

        if len(close_series) < required_rows:
            raise ValueError(
                f"At least {required_rows} aligned rows "
                f"are required for a {lookback}-day return."
            )

        start_price = float(
            close_series.iloc[
                -required_rows
            ]
        )

        end_price = float(
            close_series.iloc[-1]
        )

        if start_price <= 0:
            raise ValueError(
                "Starting price must be greater than zero."
            )

        return float(
            (
                (
                    end_price
                    / start_price
                )
                - 1.0
            )
            * 100.0
        )

    def analyze_symbol(
        self,
        symbol: str,
        stock_data: pd.DataFrame,
        benchmark_data: pd.DataFrame,
    ) -> Dict[str, object]:
        normalized_symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "Symbol cannot be empty."
            )

        aligned = self.align_with_benchmark(
            stock_data=stock_data,
            benchmark_data=benchmark_data,
        )

        minimum_rows = (
            max(self.lookbacks)
            + 1
        )

        if len(aligned) < minimum_rows:
            raise ValueError(
                f"{normalized_symbol} has only "
                f"{len(aligned)} aligned daily rows. "
                f"At least {minimum_rows} are required."
            )

        stock_returns: Dict[
            int,
            float,
        ] = {}

        benchmark_returns: Dict[
            int,
            float,
        ] = {}

        relative_returns: Dict[
            int,
            float,
        ] = {}

        weighted_stock_return = 0.0
        weighted_benchmark_return = 0.0
        weighted_relative_return = 0.0

        for lookback in self.lookbacks:
            stock_return = (
                self.calculate_period_return(
                    close_series=aligned[
                        "stock_close"
                    ],
                    lookback=lookback,
                )
            )

            benchmark_return = (
                self.calculate_period_return(
                    close_series=aligned[
                        "benchmark_close"
                    ],
                    lookback=lookback,
                )
            )

            relative_return = (
                stock_return
                - benchmark_return
            )

            weight = self.weights[
                lookback
            ]

            stock_returns[
                lookback
            ] = stock_return

            benchmark_returns[
                lookback
            ] = benchmark_return

            relative_returns[
                lookback
            ] = relative_return

            weighted_stock_return += (
                stock_return
                * weight
            )

            weighted_benchmark_return += (
                benchmark_return
                * weight
            )

            weighted_relative_return += (
                relative_return
                * weight
            )

        result: Dict[
            str,
            object,
        ] = {
            "symbol": normalized_symbol,
            "weighted_stock_return": float(
                weighted_stock_return
            ),
            "weighted_benchmark_return": float(
                weighted_benchmark_return
            ),
            "relative_return": float(
                weighted_relative_return
            ),
            "observations": int(
                len(aligned)
            ),
            "latest_timestamp": aligned[
                "timestamp"
            ].iloc[-1],
        }

        for lookback in self.lookbacks:
            result[
                f"stock_return_{lookback}d"
            ] = stock_returns[
                lookback
            ]

            result[
                f"benchmark_return_{lookback}d"
            ] = benchmark_returns[
                lookback
            ]

            result[
                f"relative_return_{lookback}d"
            ] = relative_returns[
                lookback
            ]

        return result

    def rank_universe(
        self,
        stock_data_by_symbol: Mapping[
            str,
            pd.DataFrame,
        ],
        benchmark_data: pd.DataFrame,
        skip_invalid: bool = True,
    ) -> pd.DataFrame:
        """
        Analyze and rank all valid stocks in the supplied universe.
        """

        rows: List[
            Dict[str, object]
        ] = []

        errors: List[str] = []

        for symbol, stock_data in (
            stock_data_by_symbol.items()
        ):
            try:
                result = self.analyze_symbol(
                    symbol=symbol,
                    stock_data=stock_data,
                    benchmark_data=benchmark_data,
                )

                rows.append(
                    result
                )

            except (
                TypeError,
                ValueError,
            ) as error:
                message = (
                    f"{symbol}: {error}"
                )

                if not skip_invalid:
                    raise ValueError(
                        message
                    ) from error

                errors.append(
                    message
                )

        if not rows:
            details = (
                "; ".join(errors)
                if errors
                else "No symbols were supplied."
            )

            raise ValueError(
                "No valid relative-strength results. "
                f"{details}"
            )

        rankings = pd.DataFrame(
            rows
        )

        rankings = rankings.sort_values(
            by=[
                "relative_return",
                "weighted_stock_return",
            ],
            ascending=[
                False,
                False,
            ],
        )

        rankings = rankings.reset_index(
            drop=True
        )

        rankings["rank"] = (
            rankings.index
            + 1
        )

        universe_size = len(
            rankings
        )

        if universe_size == 1:
            rankings[
                "percentile_rank"
            ] = 100.0

        else:
            rankings[
                "percentile_rank"
            ] = (
                (
                    universe_size
                    - rankings["rank"]
                )
                / (
                    universe_size
                    - 1
                )
            ) * 100.0

        rankings[
            "relative_strength_score"
        ] = rankings[
            "percentile_rank"
        ].round(2)

        preferred_columns = [
            "symbol",
            "rank",
            "relative_strength_score",
            "percentile_rank",
            "relative_return",
            "weighted_stock_return",
            "weighted_benchmark_return",
            "observations",
            "latest_timestamp",
        ]

        lookback_columns: List[
            str
        ] = []

        for lookback in self.lookbacks:
            lookback_columns.extend(
                [
                    f"stock_return_{lookback}d",
                    f"benchmark_return_{lookback}d",
                    f"relative_return_{lookback}d",
                ]
            )

        rankings = rankings[
            preferred_columns
            + lookback_columns
        ]

        numeric_columns = rankings.select_dtypes(
            include=["number"]
        ).columns

        rankings[
            numeric_columns
        ] = rankings[
            numeric_columns
        ].round(4)

        rankings.attrs[
            "skipped_symbols"
        ] = errors

        return rankings

    def get_top(
        self,
        rankings: pd.DataFrame,
        count: int = 10,
    ) -> pd.DataFrame:
        if count <= 0:
            raise ValueError(
                "Count must be greater than zero."
            )

        return rankings.head(
            count
        ).copy()

    def get_bottom(
        self,
        rankings: pd.DataFrame,
        count: int = 10,
    ) -> pd.DataFrame:
        if count <= 0:
            raise ValueError(
                "Count must be greater than zero."
            )

        return rankings.tail(
            count
        ).sort_values(
            "rank",
            ascending=False,
        ).copy()

    def export_rankings(
        self,
        rankings: pd.DataFrame,
        output_path: str = (
            "market_intelligence/results/"
            "relative_strength_rankings.csv"
        ),
    ) -> Path:
        if rankings.empty:
            raise ValueError(
                "Cannot export empty relative-strength rankings."
            )

        path = Path(
            output_path
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        rankings.to_csv(
            path,
            index=False,
        )

        return path

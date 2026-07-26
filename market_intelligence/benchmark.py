"""
Benchmark data engine.

Provides a reusable interface for loading benchmark price history
and calculating benchmark returns for relative-strength research.

The engine uses HistoricalDataManager, so it follows the same data
storage structure as the rest of the research platform.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import pandas as pd

from research.historical_data_manager import HistoricalDataManager


@dataclass(frozen=True)
class BenchmarkReturn:
    benchmark: str
    lookback: int
    start_price: float
    end_price: float
    return_percent: float
    start_timestamp: pd.Timestamp
    end_timestamp: pd.Timestamp


class BenchmarkEngine:
    """
    Load, prepare, and analyze benchmark historical data.

    Parameters
    ----------
    historical_manager:
        Existing HistoricalDataManager instance. A new instance is
        created automatically when one is not supplied.
    default_benchmark:
        Benchmark symbol used when no benchmark is explicitly passed.
    """

    SUPPORTED_BENCHMARKS: Dict[str, str] = {
        "NIFTY": "NIFTY",
        "NIFTY50": "NIFTY",
        "NIFTY_50": "NIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTY_BANK": "BANKNIFTY",
    }

    def __init__(
        self,
        historical_manager: Optional[
            HistoricalDataManager
        ] = None,
        default_benchmark: str = "NIFTY",
    ) -> None:
        self.historical = (
            historical_manager
            or HistoricalDataManager()
        )

        self.default_benchmark = (
            self.normalize_benchmark(
                default_benchmark
            )
        )

        self._cache: Dict[
            str,
            pd.DataFrame,
        ] = {}

    def normalize_benchmark(
        self,
        benchmark: str,
    ) -> str:
        normalized = (
            str(benchmark)
            .strip()
            .upper()
            .replace(" ", "")
            .replace("-", "")
        )

        return self.SUPPORTED_BENCHMARKS.get(
            normalized,
            normalized,
        )

    def load(
        self,
        interval_name: str,
        year: Optional[int] = None,
        benchmark: Optional[str] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        symbol = self.normalize_benchmark(
            benchmark
            or self.default_benchmark
        )

        cache_key = (
            f"{symbol}:"
            f"{interval_name}:"
            f"{year}"
        )

        if (
            use_cache
            and cache_key in self._cache
        ):
            return self._cache[
                cache_key
            ].copy()

        dataframe = self.historical.load(
            symbol=symbol,
            interval_name=interval_name,
            year=year,
        )

        if dataframe.empty:
            return pd.DataFrame()

        dataframe = self.prepare(
            dataframe
        )

        if use_cache:
            self._cache[
                cache_key
            ] = dataframe.copy()

        return dataframe

    def prepare(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
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
                "Benchmark data is missing "
                f"required columns: "
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

        prepared = prepared.reset_index(
            drop=True
        )

        return prepared

    def to_daily(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        prepared = self.prepare(
            dataframe
        )

        if prepared.empty:
            return prepared

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

    def calculate_return(
        self,
        dataframe: pd.DataFrame,
        lookback: int,
        benchmark: Optional[str] = None,
    ) -> BenchmarkReturn:
        if lookback <= 0:
            raise ValueError(
                "Lookback must be greater than zero."
            )

        daily = self.to_daily(
            dataframe
        )

        required_rows = lookback + 1

        if len(daily) < required_rows:
            raise ValueError(
                f"At least {required_rows} daily rows "
                f"are required for a {lookback}-day "
                "benchmark return."
            )

        start_row = daily.iloc[
            -required_rows
        ]

        end_row = daily.iloc[-1]

        start_price = float(
            start_row["close"]
        )

        end_price = float(
            end_row["close"]
        )

        return_percent = (
            (
                end_price
                / start_price
            )
            - 1.0
        ) * 100.0

        return BenchmarkReturn(
            benchmark=self.normalize_benchmark(
                benchmark
                or self.default_benchmark
            ),
            lookback=lookback,
            start_price=start_price,
            end_price=end_price,
            return_percent=float(
                return_percent
            ),
            start_timestamp=pd.Timestamp(
                start_row["timestamp"]
            ),
            end_timestamp=pd.Timestamp(
                end_row["timestamp"]
            ),
        )

    def calculate_returns(
        self,
        dataframe: pd.DataFrame,
        lookbacks: Sequence[int] = (
            5,
            10,
            20,
            50,
        ),
        benchmark: Optional[str] = None,
    ) -> Dict[int, BenchmarkReturn]:
        results: Dict[
            int,
            BenchmarkReturn,
        ] = {}

        for lookback in lookbacks:
            results[int(lookback)] = (
                self.calculate_return(
                    dataframe=dataframe,
                    lookback=int(lookback),
                    benchmark=benchmark,
                )
            )

        return results

    def load_and_calculate_returns(
        self,
        interval_name: str,
        year: Optional[int] = None,
        benchmark: Optional[str] = None,
        lookbacks: Sequence[int] = (
            5,
            10,
            20,
            50,
        ),
    ) -> Dict[int, BenchmarkReturn]:
        dataframe = self.load(
            interval_name=interval_name,
            year=year,
            benchmark=benchmark,
        )

        if dataframe.empty:
            symbol = self.normalize_benchmark(
                benchmark
                or self.default_benchmark
            )

            raise FileNotFoundError(
                "No historical benchmark data found "
                f"for {symbol}, interval "
                f"{interval_name}, year {year}."
            )

        return self.calculate_returns(
            dataframe=dataframe,
            lookbacks=lookbacks,
            benchmark=benchmark,
        )

    def clear_cache(
        self,
    ) -> None:
        self._cache.clear()

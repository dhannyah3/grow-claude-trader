"""
Sector strength and sector-rotation intelligence.

This module evaluates the relative performance of market sectors,
ranks them, and identifies leading, neutral, and lagging sectors.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

import pandas as pd


class SectorClassification(str, Enum):
    """
    Broad classification of sector performance.
    """

    LEADING = "LEADING"
    NEUTRAL = "NEUTRAL"
    LAGGING = "LAGGING"


@dataclass(frozen=True)
class SectorStrengthResult:
    """
    Final strength analysis for one sector.
    """

    sector: str
    rank: int
    percentile_rank: float
    sector_score: float
    classification: SectorClassification
    average_return: float
    median_return: float
    benchmark_return: float
    relative_return: float
    positive_stock_ratio: float
    stock_count: int
    strongest_stock: Optional[str]
    weakest_stock: Optional[str]
    lookback: int

    def to_dict(
        self,
    ) -> Dict[str, object]:
        """
        Convert the result into a serializable dictionary.
        """

        result = asdict(self)

        result["classification"] = (
            self.classification.value
        )

        return result


class SectorStrengthEngine:
    """
    Rank sectors using constituent-stock performance.

    The engine accepts:

    - Historical price data for multiple stocks
    - A stock-to-sector mapping
    - An optional benchmark return

    It produces one SectorStrengthResult per sector.
    """

    DEFAULT_LOOKBACKS = (
        5,
        10,
        20,
        50,
    )

    DEFAULT_WEIGHTS = {
        5: 0.35,
        10: 0.30,
        20: 0.25,
        50: 0.10,
    }

    def __init__(
        self,
        lookbacks: Sequence[int] = DEFAULT_LOOKBACKS,
        weights: Optional[
            Mapping[int, float]
        ] = None,
        leading_percentile: float = 70.0,
        lagging_percentile: float = 30.0,
        minimum_stocks_per_sector: int = 1,
    ) -> None:
        """
        Initialize sector-strength configuration.
        """

        self.lookbacks = tuple(
            int(lookback)
            for lookback in lookbacks
        )

        self.weights = dict(
            weights
            if weights is not None
            else self.DEFAULT_WEIGHTS
        )

        self.leading_percentile = float(
            leading_percentile
        )

        self.lagging_percentile = float(
            lagging_percentile
        )

        self.minimum_stocks_per_sector = int(
            minimum_stocks_per_sector
        )

        self._validate_configuration()

    def _validate_configuration(
        self,
    ) -> None:
        """
        Validate engine configuration.
        """

        if not self.lookbacks:
            raise ValueError(
                "At least one lookback is required."
            )

        if any(
            lookback <= 0
            for lookback in self.lookbacks
        ):
            raise ValueError(
                "All lookbacks must be greater than zero."
            )

        missing_weights = (
            set(self.lookbacks)
            - set(self.weights)
        )

        if missing_weights:
            raise ValueError(
                "Missing weights for lookbacks: "
                f"{sorted(missing_weights)}"
            )

        selected_weight_total = sum(
            float(
                self.weights[lookback]
            )
            for lookback in self.lookbacks
        )

        if selected_weight_total <= 0:
            raise ValueError(
                "The total selected weight must be positive."
            )

        if not (
            0.0
            <= self.lagging_percentile
            < self.leading_percentile
            <= 100.0
        ):
            raise ValueError(
                "Percentile thresholds must satisfy: "
                "0 <= lagging < leading <= 100."
            )

        if self.minimum_stocks_per_sector <= 0:
            raise ValueError(
                "minimum_stocks_per_sector must be positive."
            )

    @property
    def required_columns(
        self,
    ) -> tuple:
        """
        Required price-data columns.
        """

        return (
            "timestamp",
            "close",
        )

    def normalized_weights(
        self,
    ) -> Dict[int, float]:
        """
        Return weights normalized to one.
        """

        selected_weights = {
            lookback: float(
                self.weights[lookback]
            )
            for lookback in self.lookbacks
        }

        total = sum(
            selected_weights.values()
        )

        return {
            lookback: weight / total
            for lookback, weight
            in selected_weights.items()
        }

    def configuration(
        self,
    ) -> Dict[str, object]:
        """
        Return active engine configuration.
        """

        return {
            "lookbacks": self.lookbacks,
            "weights": self.normalized_weights(),
            "leading_percentile": (
                self.leading_percentile
            ),
            "lagging_percentile": (
                self.lagging_percentile
            ),
            "minimum_stocks_per_sector": (
                self.minimum_stocks_per_sector
            ),
        }

    @staticmethod
    def calculate_return(
        dataframe: pd.DataFrame,
        lookback: int,
    ) -> float:
        """
        Calculate percentage return over a lookback period.
        """

        if len(dataframe) <= lookback:
            raise ValueError(
                f"Need more than {lookback} rows."
            )

        latest = float(dataframe["close"].iloc[-1])
        previous = float(
            dataframe["close"].iloc[-(lookback + 1)]
        )

        if previous <= 0:
            return 0.0

        return ((latest - previous) / previous) * 100.0

    def calculate_weighted_return(
        self,
        dataframe: pd.DataFrame,
    ) -> float:
        """
        Calculate weighted multi-lookback return.
        """

        weights = self.normalized_weights()

        score = 0.0

        for lookback, weight in weights.items():
            score += (
                self.calculate_return(
                    dataframe,
                    lookback,
                )
                * weight
            )

        return score

    def prepare_price_data(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Validate and prepare stock price data.
        """

        missing = (
            set(self.required_columns)
            - set(dataframe.columns)
        )

        if missing:
            raise ValueError(
                f"Missing columns: {sorted(missing)}"
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

        prepared = prepared.dropna()

        prepared = prepared.sort_values(
            "timestamp"
        )

        prepared = prepared.reset_index(
            drop=True
        )

        return prepared

    def build_stock_return_table(
        self,
        price_data: Mapping[
            str,
            pd.DataFrame,
        ],
        sector_map: Mapping[
            str,
            str,
        ],
    ) -> pd.DataFrame:
        """
        Build one weighted-return record per stock.
        """

        records = []

        for symbol, dataframe in price_data.items():
            normalized_symbol = str(
                symbol
            ).strip().upper()

            sector = sector_map.get(
                normalized_symbol
            )

            if sector is None:
                sector = sector_map.get(
                    symbol
                )

            if sector is None:
                continue

            try:
                prepared = self.prepare_price_data(
                    dataframe
                )

                weighted_return = (
                    self.calculate_weighted_return(
                        prepared
                    )
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            records.append(
                {
                    "symbol": normalized_symbol,
                    "sector": str(
                        sector
                    ).strip().upper(),
                    "weighted_return": float(
                        weighted_return
                    ),
                }
            )

        if not records:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "sector",
                    "weighted_return",
                ]
            )

        result = pd.DataFrame(
            records
        )

        result = result.sort_values(
            [
                "sector",
                "weighted_return",
                "symbol",
            ],
            ascending=[
                True,
                False,
                True,
            ],
        )

        return result.reset_index(
            drop=True
        )

    def aggregate_sector_returns(
        self,
        stock_returns: pd.DataFrame,
        benchmark_return: float = 0.0,
    ) -> pd.DataFrame:
        """
        Aggregate constituent-stock returns by sector.
        """

        required_columns = {
            "symbol",
            "sector",
            "weighted_return",
        }

        missing_columns = (
            required_columns
            - set(stock_returns.columns)
        )

        if missing_columns:
            raise ValueError(
                "Stock-return data is missing columns: "
                f"{sorted(missing_columns)}"
            )

        records = []

        for sector, group in stock_returns.groupby(
            "sector",
            sort=True,
        ):
            valid_group = group.dropna(
                subset=[
                    "weighted_return",
                ]
            )

            stock_count = len(
                valid_group
            )

            if (
                stock_count
                < self.minimum_stocks_per_sector
            ):
                continue

            sorted_group = valid_group.sort_values(
                "weighted_return",
                ascending=False,
            )

            average_return = float(
                valid_group[
                    "weighted_return"
                ].mean()
            )

            median_return = float(
                valid_group[
                    "weighted_return"
                ].median()
            )

            positive_stock_ratio = float(
                (
                    valid_group[
                        "weighted_return"
                    ]
                    > 0
                ).mean()
                * 100.0
            )

            strongest_stock = str(
                sorted_group.iloc[0][
                    "symbol"
                ]
            )

            weakest_stock = str(
                sorted_group.iloc[-1][
                    "symbol"
                ]
            )

            relative_return = (
                average_return
                - float(
                    benchmark_return
                )
            )

            records.append(
                {
                    "sector": str(
                        sector
                    ),
                    "average_return": (
                        average_return
                    ),
                    "median_return": (
                        median_return
                    ),
                    "benchmark_return": float(
                        benchmark_return
                    ),
                    "relative_return": (
                        relative_return
                    ),
                    "positive_stock_ratio": (
                        positive_stock_ratio
                    ),
                    "stock_count": int(
                        stock_count
                    ),
                    "strongest_stock": (
                        strongest_stock
                    ),
                    "weakest_stock": (
                        weakest_stock
                    ),
                }
            )

        if not records:
            return pd.DataFrame(
                columns=[
                    "sector",
                    "average_return",
                    "median_return",
                    "benchmark_return",
                    "relative_return",
                    "positive_stock_ratio",
                    "stock_count",
                    "strongest_stock",
                    "weakest_stock",
                ]
            )

        return pd.DataFrame(
            records
        )

    def rank_sectors(
        self,
        sector_returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Rank sectors and calculate normalized strength scores.
        """

        if sector_returns.empty:
            return sector_returns.copy()

        ranked = sector_returns.copy()

        ranked = ranked.sort_values(
            [
                "relative_return",
                "positive_stock_ratio",
                "average_return",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        ).reset_index(
            drop=True
        )

        ranked["rank"] = (
            ranked.index
            + 1
        )

        sector_count = len(
            ranked
        )

        if sector_count == 1:
            ranked[
                "percentile_rank"
            ] = 100.0

            ranked[
                "sector_score"
            ] = 100.0

        else:
            ranked[
                "percentile_rank"
            ] = (
                (
                    sector_count
                    - ranked["rank"]
                )
                / (
                    sector_count
                    - 1
                )
            ) * 100.0

            return_rank = ranked[
                "relative_return"
            ].rank(
                method="average",
                pct=True,
            ) * 100.0

            breadth_rank = ranked[
                "positive_stock_ratio"
            ].rank(
                method="average",
                pct=True,
            ) * 100.0

            ranked[
                "sector_score"
            ] = (
                return_rank * 0.75
                + breadth_rank * 0.25
            )

        ranked[
            "classification"
        ] = ranked[
            "percentile_rank"
        ].apply(
            self.classify_sector
        )

        return ranked

    def classify_sector(
        self,
        percentile_rank: float,
    ) -> SectorClassification:
        """
        Classify a sector from its percentile rank.
        """

        if (
            percentile_rank
            >= self.leading_percentile
        ):
            return SectorClassification.LEADING

        if (
            percentile_rank
            <= self.lagging_percentile
        ):
            return SectorClassification.LAGGING

        return SectorClassification.NEUTRAL

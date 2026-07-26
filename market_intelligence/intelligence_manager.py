"""
Unified market-intelligence orchestration.

The IntelligenceManager coordinates the benchmark, relative-strength,
market-regime, and sector-strength engines and exposes one consistent
interface for trading strategies and research workflows.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

import pandas as pd

from market_intelligence.benchmark import BenchmarkEngine
from market_intelligence.market_regime_engine import (
    MarketRegimeEngine,
)
from market_intelligence.relative_strength_engine import (
    RelativeStrengthEngine,
)
from market_intelligence.sector_strength_engine import (
    SectorStrengthEngine,
)


@dataclass(frozen=True)
class MarketIntelligenceSnapshot:
    """
    Serializable output from a complete intelligence analysis.
    """

    timestamp: pd.Timestamp
    benchmark_returns: Dict[int, float]
    market_regime: Dict[str, object]
    relative_strength: List[Dict[str, object]]
    sector_strength: List[Dict[str, object]]
    symbols_analyzed: int
    sectors_analyzed: int
    metadata: Dict[str, object] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> Dict[str, object]:
        """
        Convert the snapshot into a serializable dictionary.
        """

        return {
            "timestamp": self.timestamp.isoformat(),
            "benchmark_returns": {
                int(lookback): float(value)
                for lookback, value
                in self.benchmark_returns.items()
            },
            "market_regime": dict(
                self.market_regime
            ),
            "relative_strength": [
                dict(result)
                for result in self.relative_strength
            ],
            "sector_strength": [
                dict(result)
                for result in self.sector_strength
            ],
            "symbols_analyzed": int(
                self.symbols_analyzed
            ),
            "sectors_analyzed": int(
                self.sectors_analyzed
            ),
            "metadata": dict(
                self.metadata
            ),
        }


class IntelligenceManager:
    """
    Coordinate all market-intelligence engines.

    The manager accepts prepared historical market data and produces
    a unified intelligence snapshot for strategy consumption.
    """

    DEFAULT_BENCHMARK_LOOKBACK = 20

    def __init__(
        self,
        benchmark_engine: Optional[
            BenchmarkEngine
        ] = None,
        relative_strength_engine: Optional[
            RelativeStrengthEngine
        ] = None,
        market_regime_engine: Optional[
            MarketRegimeEngine
        ] = None,
        sector_strength_engine: Optional[
            SectorStrengthEngine
        ] = None,
        benchmark_lookback: int = (
            DEFAULT_BENCHMARK_LOOKBACK
        ),
    ) -> None:
        """
        Initialize the intelligence manager and its engines.
        """

        self.benchmark_engine = (
            benchmark_engine
            if benchmark_engine is not None
            else BenchmarkEngine()
        )

        self.relative_strength_engine = (
            relative_strength_engine
            if relative_strength_engine is not None
            else RelativeStrengthEngine()
        )

        self.market_regime_engine = (
            market_regime_engine
            if market_regime_engine is not None
            else MarketRegimeEngine()
        )

        self.sector_strength_engine = (
            sector_strength_engine
            if sector_strength_engine is not None
            else SectorStrengthEngine()
        )

        self.benchmark_lookback = int(
            benchmark_lookback
        )

        self._validate_configuration()

    def _validate_configuration(
        self,
    ) -> None:
        """
        Validate manager configuration.
        """

        if self.benchmark_lookback <= 0:
            raise ValueError(
                "benchmark_lookback must be greater "
                "than zero."
            )

    @property
    def required_inputs(
        self,
    ) -> Tuple[str, ...]:
        """
        Inputs required for a complete intelligence analysis.
        """

        return (
            "benchmark_data",
            "stock_price_data",
            "sector_map",
        )

    @staticmethod
    def _engine_configuration(
        engine: object,
    ) -> Dict[str, object]:
        """
        Safely obtain configuration from an engine.
        """

        configuration_method = getattr(
            engine,
            "configuration",
            None,
        )

        if callable(
            configuration_method
        ):
            configuration = (
                configuration_method()
            )

            if isinstance(
                configuration,
                Mapping,
            ):
                return dict(
                    configuration
                )

        return {
            "engine": engine.__class__.__name__,
        }

    def configuration(
        self,
    ) -> Dict[str, object]:
        """
        Return the manager and engine configuration.
        """

        return {
            "benchmark_lookback": (
                self.benchmark_lookback
            ),
            "benchmark_engine": (
                self._engine_configuration(
                    self.benchmark_engine
                )
            ),
            "relative_strength_engine": (
                self._engine_configuration(
                    self.relative_strength_engine
                )
            ),
            "market_regime_engine": (
                self._engine_configuration(
                    self.market_regime_engine
                )
            ),
            "sector_strength_engine": (
                self._engine_configuration(
                    self.sector_strength_engine
                )
            ),
        }

    @staticmethod
    def _result_to_dict(
        result: object,
    ) -> Dict[str, object]:
        """
        Convert an engine result into a dictionary.
        """

        to_dict_method = getattr(
            result,
            "to_dict",
            None,
        )

        if callable(
            to_dict_method
        ):
            converted = (
                to_dict_method()
            )

            if isinstance(
                converted,
                Mapping,
            ):
                return dict(
                    converted
                )

        if isinstance(
            result,
            Mapping,
        ):
            return dict(
                result
            )

        result_data = getattr(
            result,
            "__dict__",
            None,
        )

        if isinstance(
            result_data,
            Mapping,
        ):
            return dict(
                result_data
            )

        raise TypeError(
            "Engine result cannot be converted "
            "to a dictionary."
        )

    def calculate_benchmark_returns(
        self,
        benchmark_data: pd.DataFrame,
    ) -> Dict[int, float]:
        """
        Calculate benchmark returns for all configured lookbacks.
        """

        returns = (
            self.benchmark_engine
            .calculate_returns(
                dataframe=benchmark_data
            )
        )

        if not returns:
            raise ValueError(
                "Benchmark engine returned no "
                "benchmark returns."
            )

        benchmark_returns = {
            int(lookback): float(
                result.return_percent
            )
            for lookback, result
            in returns.items()
        }

        if not benchmark_returns:
            raise ValueError(
                "Benchmark engine returned no "
                "usable benchmark returns."
            )

        return benchmark_returns

    def get_primary_benchmark_return(
        self,
        benchmark_returns: Mapping[
            int,
            float,
        ],
    ) -> float:
        """
        Select the benchmark return used by other engines.
        """

        if (
            self.benchmark_lookback
            not in benchmark_returns
        ):
            available = sorted(
                int(lookback)
                for lookback
                in benchmark_returns
            )

            raise ValueError(
                "Configured benchmark lookback "
                f"{self.benchmark_lookback} is unavailable. "
                f"Available lookbacks: {available}"
            )

        return float(
            benchmark_returns[
                self.benchmark_lookback
            ]
        )

    def analyze_market_regime(
        self,
        benchmark_data: pd.DataFrame,
    ) -> Dict[str, object]:
        """
        Analyze the benchmark market regime.
        """

        result = (
            self.market_regime_engine
            .analyze(
                benchmark_data
            )
        )

        return self._result_to_dict(
            result
        )

    def analyze_relative_strength(
        self,
        stock_price_data: Mapping[
            str,
            pd.DataFrame,
        ],
        benchmark_data: pd.DataFrame,
    ) -> List[Dict[str, object]]:
        """
        Rank stock relative strength.
        """

        rankings = (
            self.relative_strength_engine
            .rank_universe(
                stock_data_by_symbol=(
                    stock_price_data
                ),
                benchmark_data=(
                    benchmark_data
                ),
            )
        )

        if rankings.empty:
            return []

        return rankings.to_dict(
            orient="records"
        )

    def analyze_sector_strength(
        self,
        stock_price_data: Mapping[
            str,
            pd.DataFrame,
        ],
        sector_map: Mapping[
            str,
            str,
        ],
        benchmark_return: float,
    ) -> List[Dict[str, object]]:
        """
        Rank sector strength.
        """

        stock_returns = (
            self.sector_strength_engine
            .build_stock_return_table(
                price_data=stock_price_data,
                sector_map=sector_map,
            )
        )

        if stock_returns.empty:
            return []

        sector_returns = (
            self.sector_strength_engine
            .aggregate_sector_returns(
                stock_returns=stock_returns,
                benchmark_return=benchmark_return,
            )
        )

        if sector_returns.empty:
            return []

        rankings = (
            self.sector_strength_engine
            .rank_sectors(
                sector_returns=sector_returns,
            )
        )

        if rankings.empty:
            return []

        records = rankings.to_dict(
            orient="records"
        )

        for record in records:
            classification = record.get(
                "classification"
            )

            if hasattr(
                classification,
                "value",
            ):
                record["classification"] = (
                    classification.value
                )

        return records

    def analyze(
        self,
        benchmark_data: pd.DataFrame,
        stock_price_data: Mapping[
            str,
            pd.DataFrame,
        ],
        sector_map: Mapping[
            str,
            str,
        ],
    ) -> MarketIntelligenceSnapshot:
        """
        Run the complete market-intelligence pipeline.

        Parameters
        ----------
        benchmark_data
            Benchmark historical OHLC data.

        stock_price_data
            Dictionary mapping stock symbol to DataFrame.

        sector_map
            Dictionary mapping stock symbol to sector.

        Returns
        -------
        MarketIntelligenceSnapshot
        """

        if benchmark_data.empty:
            raise ValueError(
                "benchmark_data cannot be empty."
            )

        if not stock_price_data:
            raise ValueError(
                "stock_price_data cannot be empty."
            )

        if not sector_map:
            raise ValueError(
                "sector_map cannot be empty."
            )

        benchmark_returns = (
            self.calculate_benchmark_returns(
                benchmark_data
            )
        )

        benchmark_return = (
            self.get_primary_benchmark_return(
                benchmark_returns
            )
        )

        market_regime = (
            self.analyze_market_regime(
                benchmark_data
            )
        )

        relative_strength = (
            self.analyze_relative_strength(
                stock_price_data=stock_price_data,
                benchmark_data=benchmark_data,
            )
        )

        sector_strength = (
            self.analyze_sector_strength(
                stock_price_data=stock_price_data,
                sector_map=sector_map,
                benchmark_return=benchmark_return,
            )
        )

        timestamp = pd.Timestamp(
            benchmark_data.iloc[-1][
                "timestamp"
            ]
        )

        analyzed_sectors = {
            str(sector).strip().upper()
            for symbol, sector
            in sector_map.items()
            if (
                symbol in stock_price_data
                and str(sector).strip()
            )
        }

        return MarketIntelligenceSnapshot(
            timestamp=timestamp,
            benchmark_returns=benchmark_returns,
            market_regime=market_regime,
            relative_strength=relative_strength,
            sector_strength=sector_strength,
            symbols_analyzed=len(
                stock_price_data
            ),
            sectors_analyzed=len(
                analyzed_sectors
            ),
            metadata={
                "benchmark_lookback": (
                    self.benchmark_lookback
                ),
                "primary_benchmark_return": (
                    benchmark_return
                ),
            },
        )

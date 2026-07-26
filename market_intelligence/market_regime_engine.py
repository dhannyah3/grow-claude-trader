"""
Market Regime Engine.

Provides reusable market-regime classifications for research,
backtesting, strategy selection, risk management, and execution.

This first version defines the core types and engine configuration.
Indicator calculation and regime classification will be added next.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Sequence

import pandas as pd


class TrendDirection(str, Enum):
    """
    Broad direction of the market trend.
    """

    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAYS = "SIDEWAYS"


class VolatilityLevel(str, Enum):
    """
    Current volatility relative to recent historical volatility.
    """

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class MarketState(str, Enum):
    """
    High-level structure of the market.
    """

    TRENDING = "TRENDING"
    RANGE_BOUND = "RANGE_BOUND"
    TRANSITION = "TRANSITION"


@dataclass(frozen=True)
class MarketRegimeResult:
    """
    Final market-regime classification returned by the engine.
    """

    trend: TrendDirection
    market_state: MarketState
    volatility: VolatilityLevel
    trend_strength: float
    volatility_score: float
    confidence: float
    risk_multiplier: float
    latest_close: float
    latest_timestamp: pd.Timestamp
    observations: int
    metrics: Dict[str, float]

    def to_dict(
        self,
    ) -> Dict[str, object]:
        """
        Convert the result into a JSON-friendly dictionary.
        """

        return {
            "trend": self.trend.value,
            "market_state": self.market_state.value,
            "volatility": self.volatility.value,
            "trend_strength": self.trend_strength,
            "volatility_score": self.volatility_score,
            "confidence": self.confidence,
            "risk_multiplier": self.risk_multiplier,
            "latest_close": self.latest_close,
            "latest_timestamp": (
                self.latest_timestamp.isoformat()
            ),
            "observations": self.observations,
            "metrics": dict(
                self.metrics
            ),
        }


class MarketRegimeEngine:
    """
    Analyze market data and classify the current market regime.

    Parameters
    ----------
    fast_ema_period:
        Period used for the fast exponential moving average.
    slow_ema_period:
        Period used for the slow exponential moving average.
    atr_period:
        Period used for average true range calculations.
    trend_lookback:
        Number of rows used to evaluate EMA slope and momentum.
    volatility_lookback:
        Number of rows used to compare current and historical
        volatility.
    swing_lookback:
        Number of rows used to evaluate recent highs and lows.
    minimum_rows:
        Minimum observations required before analysis can run.
    """

    def __init__(
        self,
        fast_ema_period: int = 20,
        slow_ema_period: int = 50,
        atr_period: int = 14,
        trend_lookback: int = 10,
        volatility_lookback: int = 50,
        swing_lookback: int = 20,
        minimum_rows: Optional[int] = None,
    ) -> None:
        self.fast_ema_period = self._validate_positive_integer(
            value=fast_ema_period,
            name="fast_ema_period",
        )

        self.slow_ema_period = self._validate_positive_integer(
            value=slow_ema_period,
            name="slow_ema_period",
        )

        self.atr_period = self._validate_positive_integer(
            value=atr_period,
            name="atr_period",
        )

        self.trend_lookback = self._validate_positive_integer(
            value=trend_lookback,
            name="trend_lookback",
        )

        self.volatility_lookback = (
            self._validate_positive_integer(
                value=volatility_lookback,
                name="volatility_lookback",
            )
        )

        self.swing_lookback = self._validate_positive_integer(
            value=swing_lookback,
            name="swing_lookback",
        )

        if (
            self.fast_ema_period
            >= self.slow_ema_period
        ):
            raise ValueError(
                "fast_ema_period must be smaller than "
                "slow_ema_period."
            )

        calculated_minimum = max(
            self.slow_ema_period,
            self.atr_period,
            self.trend_lookback + 1,
            self.volatility_lookback,
            self.swing_lookback,
        ) + 5

        if minimum_rows is None:
            self.minimum_rows = (
                calculated_minimum
            )
        else:
            self.minimum_rows = (
                self._validate_positive_integer(
                    value=minimum_rows,
                    name="minimum_rows",
                )
            )

            if (
                self.minimum_rows
                < calculated_minimum
            ):
                raise ValueError(
                    "minimum_rows is too small for the "
                    "configured indicator periods. "
                    f"Use at least {calculated_minimum}."
                )

    @staticmethod
    def _validate_positive_integer(
        value: int,
        name: str,
    ) -> int:
        """
        Validate a positive integer configuration value.
        """

        if isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"{name} must be an integer."
            )

        try:
            validated = int(
                value
            )
        except (
            TypeError,
            ValueError,
        ) as error:
            raise TypeError(
                f"{name} must be an integer."
            ) from error

        if validated <= 0:
            raise ValueError(
                f"{name} must be greater than zero."
            )

        return validated

    @property
    def required_columns(
        self,
    ) -> Sequence[str]:
        """
        Columns required for full regime analysis.
        """

        return (
            "timestamp",
            "open",
            "high",
            "low",
            "close",
        )

    def configuration(
        self,
    ) -> Dict[str, int]:
        """
        Return the active engine configuration.
        """

        return {
            "fast_ema_period": self.fast_ema_period,
            "slow_ema_period": self.slow_ema_period,
            "atr_period": self.atr_period,
            "trend_lookback": self.trend_lookback,
            "volatility_lookback": (
                self.volatility_lookback
            ),
            "swing_lookback": self.swing_lookback,
            "minimum_rows": self.minimum_rows,
        }

    def prepare_data(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Validate, clean, and enrich OHLC market data.
        """

        missing_columns = (
            set(self.required_columns)
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Market data is missing required columns: "
                f"{sorted(missing_columns)}"
            )

        prepared = dataframe.copy()

        prepared["timestamp"] = pd.to_datetime(
            prepared["timestamp"],
            errors="coerce",
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
        ]

        for column in numeric_columns:
            prepared[column] = pd.to_numeric(
                prepared[column],
                errors="coerce",
            )

        prepared = prepared.dropna(
            subset=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
            ]
        )

        prepared = prepared[
            (
                prepared["open"] > 0
            )
            & (
                prepared["high"] > 0
            )
            & (
                prepared["low"] > 0
            )
            & (
                prepared["close"] > 0
            )
        ]

        prepared = prepared[
            prepared["high"]
            >= prepared["low"]
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

        if len(prepared) < self.minimum_rows:
            raise ValueError(
                "Insufficient market data. "
                f"Received {len(prepared)} rows; "
                f"at least {self.minimum_rows} are required."
            )

        prepared[
            "ema_fast"
        ] = self.calculate_ema(
            series=prepared["close"],
            period=self.fast_ema_period,
        )

        prepared[
            "ema_slow"
        ] = self.calculate_ema(
            series=prepared["close"],
            period=self.slow_ema_period,
        )

        prepared[
            "true_range"
        ] = self.calculate_true_range(
            dataframe=prepared
        )

        prepared[
            "atr"
        ] = self.calculate_atr(
            true_range=prepared[
                "true_range"
            ],
            period=self.atr_period,
        )

        prepared[
            "atr_percent"
        ] = (
            prepared["atr"]
            / prepared["close"]
        ) * 100.0

        prepared[
            "return_percent"
        ] = prepared[
            "close"
        ].pct_change() * 100.0

        return prepared

    @staticmethod
    def calculate_ema(
        series: pd.Series,
        period: int,
    ) -> pd.Series:
        """
        Calculate an exponential moving average.
        """

        if period <= 0:
            raise ValueError(
                "EMA period must be greater than zero."
            )

        numeric_series = pd.to_numeric(
            series,
            errors="coerce",
        )

        return numeric_series.ewm(
            span=period,
            adjust=False,
            min_periods=period,
        ).mean()

    @staticmethod
    def calculate_true_range(
        dataframe: pd.DataFrame,
    ) -> pd.Series:
        """
        Calculate true range from OHLC data.
        """

        previous_close = dataframe[
            "close"
        ].shift(1)

        high_low = (
            dataframe["high"]
            - dataframe["low"]
        ).abs()

        high_previous_close = (
            dataframe["high"]
            - previous_close
        ).abs()

        low_previous_close = (
            dataframe["low"]
            - previous_close
        ).abs()

        true_range = pd.concat(
            [
                high_low,
                high_previous_close,
                low_previous_close,
            ],
            axis=1,
        ).max(
            axis=1
        )

        return true_range

    @staticmethod
    def calculate_atr(
        true_range: pd.Series,
        period: int,
    ) -> pd.Series:
        """
        Calculate Wilder-style average true range.
        """

        if period <= 0:
            raise ValueError(
                "ATR period must be greater than zero."
            )

        numeric_series = pd.to_numeric(
            true_range,
            errors="coerce",
        )

        return numeric_series.ewm(
            alpha=1.0 / period,
            adjust=False,
            min_periods=period,
        ).mean()

    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 100.0,
    ) -> float:
        """
        Restrict a numeric value to a fixed range.
        """

        return float(
            max(
                minimum,
                min(
                    maximum,
                    value,
                ),
            )
        )

    def calculate_trend_metrics(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Calculate EMA separation, slope, momentum, and swing position.
        """

        latest = dataframe.iloc[-1]

        earlier = dataframe.iloc[
            -(self.trend_lookback + 1)
        ]

        latest_close = float(
            latest["close"]
        )

        fast_ema = float(
            latest["ema_fast"]
        )

        slow_ema = float(
            latest["ema_slow"]
        )

        earlier_fast_ema = float(
            earlier["ema_fast"]
        )

        ema_separation_percent = (
            (
                fast_ema
                - slow_ema
            )
            / latest_close
        ) * 100.0

        fast_ema_slope_percent = (
            (
                fast_ema
                - earlier_fast_ema
            )
            / earlier_fast_ema
        ) * 100.0

        earlier_close = float(
            earlier["close"]
        )

        momentum_percent = (
            (
                latest_close
                - earlier_close
            )
            / earlier_close
        ) * 100.0

        recent = dataframe.tail(
            self.swing_lookback
        )

        swing_high = float(
            recent["high"].max()
        )

        swing_low = float(
            recent["low"].min()
        )

        swing_range = (
            swing_high
            - swing_low
        )

        if swing_range <= 0:
            swing_position = 50.0
        else:
            swing_position = (
                (
                    latest_close
                    - swing_low
                )
                / swing_range
            ) * 100.0

        return {
            "ema_separation_percent": float(
                ema_separation_percent
            ),
            "fast_ema_slope_percent": float(
                fast_ema_slope_percent
            ),
            "momentum_percent": float(
                momentum_percent
            ),
            "swing_position": self._clamp(
                swing_position
            ),
            "fast_ema": fast_ema,
            "slow_ema": slow_ema,
        }

    def classify_trend(
        self,
        metrics: Dict[str, float],
    ) -> TrendDirection:
        """
        Classify broad trend direction.
        """

        separation = metrics[
            "ema_separation_percent"
        ]

        slope = metrics[
            "fast_ema_slope_percent"
        ]

        momentum = metrics[
            "momentum_percent"
        ]

        if (
            separation >= 0.15
            and slope > 0
            and momentum > 0
        ):
            return TrendDirection.UPTREND

        if (
            separation <= -0.15
            and slope < 0
            and momentum < 0
        ):
            return TrendDirection.DOWNTREND

        return TrendDirection.SIDEWAYS

    def calculate_trend_strength(
        self,
        metrics: Dict[str, float],
    ) -> float:
        """
        Calculate normalized trend strength from zero to one hundred.
        """

        separation_score = self._clamp(
            abs(
                metrics[
                    "ema_separation_percent"
                ]
            )
            / 1.5
            * 100.0
        )

        slope_score = self._clamp(
            abs(
                metrics[
                    "fast_ema_slope_percent"
                ]
            )
            / 3.0
            * 100.0
        )

        momentum_score = self._clamp(
            abs(
                metrics[
                    "momentum_percent"
                ]
            )
            / 5.0
            * 100.0
        )

        swing_position = metrics[
            "swing_position"
        ]

        swing_score = abs(
            swing_position
            - 50.0
        ) * 2.0

        strength = (
            separation_score * 0.35
            + slope_score * 0.25
            + momentum_score * 0.25
            + swing_score * 0.15
        )

        return round(
            self._clamp(
                strength
            ),
            2,
        )

    def calculate_volatility_metrics(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict[str, float]:
        """
        Compare current ATR percentage with recent ATR history.
        """

        recent = dataframe.tail(
            self.volatility_lookback
        )

        latest_atr_percent = float(
            dataframe[
                "atr_percent"
            ].iloc[-1]
        )

        median_atr_percent = float(
            recent[
                "atr_percent"
            ].median()
        )

        if median_atr_percent <= 0:
            volatility_ratio = 1.0
        else:
            volatility_ratio = (
                latest_atr_percent
                / median_atr_percent
            )

        volatility_score = self._clamp(
            volatility_ratio
            / 2.0
            * 100.0
        )

        return {
            "latest_atr_percent": latest_atr_percent,
            "median_atr_percent": median_atr_percent,
            "volatility_ratio": float(
                volatility_ratio
            ),
            "volatility_score": round(
                volatility_score,
                2,
            ),
        }

    @staticmethod
    def classify_volatility(
        volatility_ratio: float,
    ) -> VolatilityLevel:
        """
        Classify volatility relative to recent history.
        """

        if volatility_ratio < 0.80:
            return VolatilityLevel.LOW

        if volatility_ratio > 1.30:
            return VolatilityLevel.HIGH

        return VolatilityLevel.NORMAL

    @staticmethod
    def classify_market_state(
        trend: TrendDirection,
        trend_strength: float,
    ) -> MarketState:
        """
        Convert trend direction and strength into market structure.
        """

        if (
            trend != TrendDirection.SIDEWAYS
            and trend_strength >= 55.0
        ):
            return MarketState.TRENDING

        if (
            trend == TrendDirection.SIDEWAYS
            and trend_strength <= 35.0
        ):
            return MarketState.RANGE_BOUND

        return MarketState.TRANSITION

    @staticmethod
    def calculate_risk_multiplier(
        market_state: MarketState,
        volatility: VolatilityLevel,
        confidence: float,
    ) -> float:
        """
        Calculate a conservative position-size multiplier.
        """

        state_multiplier = {
            MarketState.TRENDING: 1.10,
            MarketState.RANGE_BOUND: 0.80,
            MarketState.TRANSITION: 0.60,
        }[
            market_state
        ]

        volatility_multiplier = {
            VolatilityLevel.LOW: 0.90,
            VolatilityLevel.NORMAL: 1.00,
            VolatilityLevel.HIGH: 0.70,
        }[
            volatility
        ]

        confidence_multiplier = max(
            0.50,
            min(
                1.00,
                confidence / 100.0,
            ),
        )

        result = (
            state_multiplier
            * volatility_multiplier
            * confidence_multiplier
        )

        return round(
            max(
                0.30,
                min(
                    1.20,
                    result,
                ),
            ),
            2,
        )

    def calculate_confidence(
        self,
        trend: TrendDirection,
        trend_strength: float,
        volatility: VolatilityLevel,
        metrics: Dict[str, float],
    ) -> float:
        """
        Calculate confidence in the current regime classification.
        """

        separation = abs(
            metrics[
                "ema_separation_percent"
            ]
        )

        slope = abs(
            metrics[
                "fast_ema_slope_percent"
            ]
        )

        momentum = abs(
            metrics[
                "momentum_percent"
            ]
        )

        directional_alignment = 0.0

        if trend == TrendDirection.UPTREND:
            positive_signals = sum(
                [
                    metrics[
                        "ema_separation_percent"
                    ] > 0,
                    metrics[
                        "fast_ema_slope_percent"
                    ] > 0,
                    metrics[
                        "momentum_percent"
                    ] > 0,
                    metrics[
                        "swing_position"
                    ] > 50,
                ]
            )

            directional_alignment = (
                positive_signals
                / 4.0
            ) * 100.0

        elif trend == TrendDirection.DOWNTREND:
            negative_signals = sum(
                [
                    metrics[
                        "ema_separation_percent"
                    ] < 0,
                    metrics[
                        "fast_ema_slope_percent"
                    ] < 0,
                    metrics[
                        "momentum_percent"
                    ] < 0,
                    metrics[
                        "swing_position"
                    ] < 50,
                ]
            )

            directional_alignment = (
                negative_signals
                / 4.0
            ) * 100.0

        else:
            sideways_evidence = sum(
                [
                    separation < 0.30,
                    slope < 0.75,
                    momentum < 1.50,
                    30.0
                    <= metrics[
                        "swing_position"
                    ]
                    <= 70.0,
                ]
            )

            directional_alignment = (
                sideways_evidence
                / 4.0
            ) * 100.0

        volatility_reliability = {
            VolatilityLevel.LOW: 80.0,
            VolatilityLevel.NORMAL: 100.0,
            VolatilityLevel.HIGH: 65.0,
        }[
            volatility
        ]

        confidence = (
            directional_alignment
            * 0.45
            + trend_strength
            * 0.35
            + volatility_reliability
            * 0.20
        )

        return round(
            self._clamp(
                confidence
            ),
            2,
        )

    def analyze(
        self,
        dataframe: pd.DataFrame,
    ) -> MarketRegimeResult:
        """
        Run the complete market-regime analysis pipeline.
        """

        prepared = self.prepare_data(
            dataframe
        )

        trend_metrics = (
            self.calculate_trend_metrics(
                prepared
            )
        )

        trend = self.classify_trend(
            trend_metrics
        )

        trend_strength = (
            self.calculate_trend_strength(
                trend_metrics
            )
        )

        volatility_metrics = (
            self.calculate_volatility_metrics(
                prepared
            )
        )

        volatility = (
            self.classify_volatility(
                volatility_metrics[
                    "volatility_ratio"
                ]
            )
        )

        market_state = (
            self.classify_market_state(
                trend=trend,
                trend_strength=trend_strength,
            )
        )

        confidence = (
            self.calculate_confidence(
                trend=trend,
                trend_strength=trend_strength,
                volatility=volatility,
                metrics=trend_metrics,
            )
        )

        risk_multiplier = (
            self.calculate_risk_multiplier(
                market_state=market_state,
                volatility=volatility,
                confidence=confidence,
            )
        )

        latest_row = prepared.iloc[-1]

        combined_metrics = {
            **trend_metrics,
            **volatility_metrics,
            "latest_atr": float(
                latest_row["atr"]
            ),
            "latest_return_percent": float(
                latest_row[
                    "return_percent"
                ]
            ),
        }

        rounded_metrics = {
            key: round(
                float(value),
                4,
            )
            for key, value
            in combined_metrics.items()
        }

        return MarketRegimeResult(
            trend=trend,
            market_state=market_state,
            volatility=volatility,
            trend_strength=trend_strength,
            volatility_score=float(
                volatility_metrics[
                    "volatility_score"
                ]
            ),
            confidence=confidence,
            risk_multiplier=risk_multiplier,
            latest_close=float(
                latest_row["close"]
            ),
            latest_timestamp=pd.Timestamp(
                latest_row["timestamp"]
            ),
            observations=int(
                len(prepared)
            ),
            metrics=rounded_metrics,
        )

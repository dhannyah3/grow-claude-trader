"""
Institutional Opening Range Breakout Strategy

Market hypothesis:
- The first 15 minutes establish the opening range.
- A fresh breakout supported by trend, volume, and volatility
  may continue.
- A confirmation candle reduces false breakout entries.

Version 1 supports long trades only.
"""

from typing import Any, Dict, Set

import pandas as pd

from research.base_strategy import BaseStrategy


class InstitutionalORBStrategy(BaseStrategy):
    """
    Institutional Opening Range Breakout strategy.

    Entry sequence:
    1. Build the opening range from 09:15 until 09:30.
    2. Previous candle must close above the opening-range high.
    3. Current candle must confirm above the opening-range high.
    4. EMA20 must be above EMA50.
    5. Relative volume must meet the minimum threshold.
    6. ATR must be expanding.
    7. Entry must not be too far above the breakout level.
    """

    name = "INSTITUTIONAL_ORB"

    def __init__(
        self,
        stop_atr_multiplier: float = 1.0,
        target_risk_multiplier: float = 2.0,
        minimum_volume_ratio: float = 1.5,
        maximum_entry_distance_atr: float = 0.5,
        atr_expansion_lookback: int = 10,
        opening_range_start_time: str = "09:15",
        opening_range_end_time: str = "09:30",
        entry_start_time: str = "09:30",
        entry_cutoff_time: str = "14:30",
        force_exit_time: str = "15:15",
    ) -> None:
        super().__init__(
            entry_start_time=entry_start_time,
            entry_cutoff_time=entry_cutoff_time,
            force_exit_time=force_exit_time,
        )

        self.stop_atr_multiplier = float(
            stop_atr_multiplier
        )

        self.target_risk_multiplier = float(
            target_risk_multiplier
        )

        self.minimum_volume_ratio = float(
            minimum_volume_ratio
        )

        self.maximum_entry_distance_atr = float(
            maximum_entry_distance_atr
        )

        self.atr_expansion_lookback = int(
            atr_expansion_lookback
        )

        self.opening_range_start_time = pd.Timestamp(
            opening_range_start_time
        ).time()

        self.opening_range_end_time = pd.Timestamp(
            opening_range_end_time
        ).time()

        self._validate_parameters()

    def _validate_parameters(self) -> None:
        """Validate the configured strategy parameters."""

        if self.stop_atr_multiplier <= 0:
            raise ValueError(
                "stop_atr_multiplier must be greater than zero."
            )

        if self.target_risk_multiplier <= 0:
            raise ValueError(
                "target_risk_multiplier must be greater than zero."
            )

        if self.minimum_volume_ratio < 0:
            raise ValueError(
                "minimum_volume_ratio cannot be negative."
            )

        if self.maximum_entry_distance_atr <= 0:
            raise ValueError(
                "maximum_entry_distance_atr must be greater than zero."
            )

        if self.atr_expansion_lookback < 2:
            raise ValueError(
                "atr_expansion_lookback must be at least 2."
            )

        if not (
            self.opening_range_start_time
            < self.opening_range_end_time
            <= self.entry_start_time
        ):
            raise ValueError(
                "Trading times must satisfy: "
                "opening range start < opening range end "
                "<= entry start."
            )

    def required_columns(self) -> Set[str]:
        """Return all dataframe columns required by the strategy."""

        return {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ema_20",
            "ema_50",
            "atr",
            "volume_ratio",
        }

    def prepare_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """Convert timestamps and ensure chronological ordering."""

        prepared = dataframe.copy()

        prepared["timestamp"] = pd.to_datetime(
            prepared["timestamp"]
        )

        return prepared.sort_values(
            "timestamp"
        ).reset_index(drop=True)

    def _get_opening_range(
        self,
        day_data: pd.DataFrame,
    ) -> Dict[str, float]:
        """Calculate the session opening-range high and low."""

        timestamps = pd.to_datetime(
            day_data["timestamp"]
        )

        candle_times = timestamps.dt.time

        opening_candles = day_data.loc[
            (
                candle_times
                >= self.opening_range_start_time
            )
            & (
                candle_times
                < self.opening_range_end_time
            )
        ]

        if opening_candles.empty:
            return {}

        return {
            "high": float(
                opening_candles["high"].max()
            ),
            "low": float(
                opening_candles["low"].min()
            ),
        }

    def _atr_is_expanding(
        self,
        row_index: int,
        row: pd.Series,
        day_data: pd.DataFrame,
    ) -> bool:
        """
        Check whether current ATR exceeds its recent prior average.

        The current candle is excluded from the comparison average.
        """

        start_index = max(
            0,
            row_index - self.atr_expansion_lookback,
        )

        previous_atr_values = day_data.iloc[
            start_index:row_index
        ]["atr"].dropna()

        if len(previous_atr_values) < 2:
            return False

        average_previous_atr = float(
            previous_atr_values.mean()
        )

        current_atr = float(
            row["atr"]
        )

        return (
            average_previous_atr > 0
            and current_atr > average_previous_atr
        )

    def should_enter(
        self,
        row_index: int,
        row: pd.Series,
        day_data: pd.DataFrame,
    ) -> bool:
        """Return True when the current candle confirms a long ORB."""

        if row_index < 2:
            return False

        current_timestamp = pd.Timestamp(
            row["timestamp"]
        )

        if (
            current_timestamp.time()
            < self.opening_range_end_time
        ):
            return False

        required_values = [
            row["close"],
            row["low"],
            row["ema_20"],
            row["ema_50"],
            row["atr"],
            row["volume_ratio"],
        ]

        if any(
            pd.isna(value)
            for value in required_values
        ):
            return False

        current_atr = float(
            row["atr"]
        )

        if current_atr <= 0:
            return False

        opening_range = self._get_opening_range(
            day_data
        )

        if not opening_range:
            return False

        opening_high = opening_range["high"]

        breakout_candle = day_data.iloc[
            row_index - 1
        ]

        candle_before_breakout = day_data.iloc[
            row_index - 2
        ]

        if (
            pd.isna(breakout_candle["close"])
            or pd.isna(
                candle_before_breakout["close"]
            )
        ):
            return False

        breakout_close = float(
            breakout_candle["close"]
        )

        pre_breakout_close = float(
            candle_before_breakout["close"]
        )

        confirmation_close = float(
            row["close"]
        )

        confirmation_low = float(
            row["low"]
        )

        # Previous candle must break above the opening-range high.
        if breakout_close <= opening_high:
            return False

        # Require a fresh breakout rather than repeated signals.
        if pre_breakout_close > opening_high:
            return False

        # Current candle must confirm above the breakout level.
        if confirmation_close <= opening_high:
            return False

        # Confirmation candle should not fall back inside the range.
        if confirmation_low < opening_high:
            return False

        # Trend alignment.
        if (
            float(row["ema_20"])
            <= float(row["ema_50"])
        ):
            return False

        # Relative-volume confirmation.
        if (
            float(row["volume_ratio"])
            < self.minimum_volume_ratio
        ):
            return False

        # Volatility expansion.
        if not self._atr_is_expanding(
            row_index=row_index,
            row=row,
            day_data=day_data,
        ):
            return False

        # Avoid chasing a breakout that has already moved too far.
        entry_distance = (
            confirmation_close
            - opening_high
        )

        maximum_distance = (
            current_atr
            * self.maximum_entry_distance_atr
        )

        if entry_distance > maximum_distance:
            return False

        return True

    def calculate_stop_loss(
        self,
        row: pd.Series,
        entry_price: float,
    ) -> float:
        """Calculate the initial ATR-based stop-loss."""

        return (
            float(entry_price)
            - (
                float(row["atr"])
                * self.stop_atr_multiplier
            )
        )

    def calculate_target(
        self,
        row: pd.Series,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """Calculate the target using a multiple of initial risk."""

        risk = (
            float(entry_price)
            - float(stop_loss)
        )

        return (
            float(entry_price)
            + (
                risk
                * self.target_risk_multiplier
            )
        )

    def additional_trade_metadata(
        self,
        row: pd.Series,
    ) -> Dict[str, Any]:
        """Return signal values and strategy configuration."""

        return {
            "strategy": self.name,
            "ema_20": float(
                row["ema_20"]
            ),
            "ema_50": float(
                row["ema_50"]
            ),
            "atr": float(
                row["atr"]
            ),
            "volume_ratio": float(
                row["volume_ratio"]
            ),
            "stop_atr_multiplier":
                self.stop_atr_multiplier,
            "target_risk_multiplier":
                self.target_risk_multiplier,
            "minimum_volume_ratio":
                self.minimum_volume_ratio,
            "maximum_entry_distance_atr":
                self.maximum_entry_distance_atr,
            "atr_expansion_lookback":
                self.atr_expansion_lookback,
            "opening_range_start_time":
                self.opening_range_start_time.strftime(
                    "%H:%M"
                ),
            "opening_range_end_time":
                self.opening_range_end_time.strftime(
                    "%H:%M"
                ),
        }
"""
Donchian Breakout Strategy.

Long-only entry rules:
- Current close breaks above the highest high of the previous N candles.
- EMA 20 is above EMA 50.
- Price is above VWAP.
- RSI is within the configured range.
- Relative volume meets the configured minimum.
- Stop loss and target are ATR based.
"""

from typing import Any, Dict, Set

import pandas as pd

from research.base_strategy import BaseStrategy


class DonchianBreakoutStrategy(BaseStrategy):
    """Long-only Donchian breakout strategy."""

    name = "DONCHIAN_BREAKOUT"

    def __init__(
        self,
        lookback_period: int = 20,
        minimum_rsi: float = 55.0,
        maximum_rsi: float = 75.0,
        minimum_volume_ratio: float = 1.5,
        stop_atr_multiplier: float = 1.0,
        target_atr_multiplier: float = 2.5,
        entry_start_time: str = "09:30",
        entry_cutoff_time: str = "11:30",
        force_exit_time: str = "15:20",
    ) -> None:
        super().__init__(
            entry_start_time=entry_start_time,
            entry_cutoff_time=entry_cutoff_time,
            force_exit_time=force_exit_time,
        )

        self.lookback_period = int(lookback_period)
        self.minimum_rsi = float(minimum_rsi)
        self.maximum_rsi = float(maximum_rsi)
        self.minimum_volume_ratio = float(minimum_volume_ratio)
        self.stop_atr_multiplier = float(stop_atr_multiplier)
        self.target_atr_multiplier = float(target_atr_multiplier)

        if self.lookback_period <= 0:
            raise ValueError(
                "lookback_period must be greater than zero."
            )

        if self.minimum_rsi > self.maximum_rsi:
            raise ValueError(
                "minimum_rsi cannot be greater than maximum_rsi."
            )

        if self.minimum_volume_ratio < 0:
            raise ValueError(
                "minimum_volume_ratio cannot be negative."
            )

        if self.stop_atr_multiplier <= 0:
            raise ValueError(
                "stop_atr_multiplier must be greater than zero."
            )

        if self.target_atr_multiplier <= 0:
            raise ValueError(
                "target_atr_multiplier must be greater than zero."
            )

    def required_columns(self) -> Set[str]:
        return {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ema_20",
            "ema_50",
            "vwap",
            "atr",
            "rsi",
            "volume_ratio",
            "donchian_upper",
        }

    def prepare_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prepare the dataframe and calculate the upper Donchian channel.

        The current candle is excluded by shifting highs by one candle.
        This avoids look-ahead bias.

        The channel is calculated separately for each trading day.
        """
        df = dataframe.copy()

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ema_20",
            "ema_50",
            "vwap",
            "atr",
            "rsi",
            "volume_ratio",
        ]

        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        df = df.dropna(
            subset=[
                "timestamp",
                "high",
                "close",
            ]
        )

        df = df.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        df["trade_date"] = df["timestamp"].dt.date

        df["donchian_upper"] = (
            df.groupby(
                "trade_date",
                sort=False,
            )["high"]
            .transform(
                lambda series: (
                    series.shift(1)
                    .rolling(
                        window=self.lookback_period,
                        min_periods=self.lookback_period,
                    )
                    .max()
                )
            )
        )

        return df

    def should_enter(
        self,
        row_index: int,
        row: pd.Series,
        day_data: pd.DataFrame,
    ) -> bool:
        """
        Return True when all Donchian breakout conditions are met.
        """
        if row_index < self.lookback_period:
            return False

        required_values = [
            row.get("timestamp"),
            row.get("close"),
            row.get("donchian_upper"),
            row.get("ema_20"),
            row.get("ema_50"),
            row.get("vwap"),
            row.get("atr"),
            row.get("rsi"),
            row.get("volume_ratio"),
        ]

        if any(pd.isna(value) for value in required_values):
            return False

        current_time = row["timestamp"].time()

        if not (
            self.entry_start_time
            <= current_time
            <= self.entry_cutoff_time
        ):
            return False

        close = float(row["close"])
        donchian_upper = float(row["donchian_upper"])
        ema_20 = float(row["ema_20"])
        ema_50 = float(row["ema_50"])
        vwap = float(row["vwap"])
        atr = float(row["atr"])
        rsi = float(row["rsi"])
        volume_ratio = float(row["volume_ratio"])

        if close <= donchian_upper:
            return False

        if ema_20 <= ema_50:
            return False

        if close <= vwap:
            return False

        if not (
            self.minimum_rsi
            <= rsi
            <= self.maximum_rsi
        ):
            return False

        if volume_ratio < self.minimum_volume_ratio:
            return False

        if atr <= 0:
            return False

        return True

    def calculate_stop_loss(
        self,
        row: pd.Series,
        entry_price: float,
    ) -> float:
        """Calculate an ATR-based stop loss."""
        atr = float(row["atr"])

        stop_loss = (
            entry_price
            - atr * self.stop_atr_multiplier
        )

        return float(stop_loss)

    def calculate_target(
        self,
        row: pd.Series,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """Calculate the target using the configured risk multiple."""
        risk_per_share = entry_price - stop_loss

        target = (
            entry_price
            + risk_per_share * self.target_atr_multiplier
        )

        return float(target)

    def additional_trade_metadata(
        self,
        row: pd.Series,
    ) -> Dict[str, Any]:
        """Return strategy information saved with each trade."""
        return {
            "strategy": self.name,
            "lookback_period": self.lookback_period,
            "donchian_upper": float(
                row["donchian_upper"]
            ),
            "minimum_rsi": self.minimum_rsi,
            "maximum_rsi": self.maximum_rsi,
            "minimum_volume_ratio": (
                self.minimum_volume_ratio
            ),
            "stop_atr_multiplier": (
                self.stop_atr_multiplier
            ),
            "target_atr_multiplier": (
                self.target_atr_multiplier
            ),
            "close": float(
                row["close"]
            ),
            "ema_20": float(
                row["ema_20"]
            ),
            "ema_50": float(
                row["ema_50"]
            ),
            "vwap": float(
                row["vwap"]
            ),
            "atr": float(
                row["atr"]
            ),
            "rsi": float(
                row["rsi"]
            ),
            "volume_ratio": float(
                row["volume_ratio"]
            ),
        }
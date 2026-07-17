"""
Gap and Go Strategy

Long-only idea:
- today's open gaps above the previous trading day's close;
- wait until the opening range is complete;
- price breaks above the opening-range high;
- EMA20 is above EMA50;
- price is above VWAP;
- RSI confirms momentum;
- relative volume exceeds the configured threshold;
- stop and target are ATR based.
"""

from typing import Any, Dict, Set

import pandas as pd

from research.base_strategy import BaseStrategy


class GapAndGoStrategy(BaseStrategy):
    """Long-only Gap and Go strategy."""

    name = "GAP_AND_GO"

    def __init__(
        self,
        minimum_gap_percent: float = 1.0,
        opening_range_minutes: int = 15,
        minimum_rsi: float = 55.0,
        maximum_rsi: float = 75.0,
        minimum_volume_ratio: float = 2.0,
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

        self.minimum_gap_percent = float(minimum_gap_percent)
        self.opening_range_minutes = int(opening_range_minutes)
        self.minimum_rsi = float(minimum_rsi)
        self.maximum_rsi = float(maximum_rsi)
        self.minimum_volume_ratio = float(minimum_volume_ratio)
        self.stop_atr_multiplier = float(stop_atr_multiplier)
        self.target_atr_multiplier = float(target_atr_multiplier)

        if self.minimum_gap_percent < 0:
            raise ValueError("Minimum gap percent cannot be negative.")
        if self.opening_range_minutes <= 0:
            raise ValueError("Opening range minutes must be greater than zero.")
        if self.minimum_rsi > self.maximum_rsi:
            raise ValueError("Minimum RSI cannot exceed maximum RSI.")
        if self.minimum_volume_ratio < 0:
            raise ValueError("Minimum volume ratio cannot be negative.")
        if self.stop_atr_multiplier <= 0:
            raise ValueError("Stop ATR multiplier must be greater than zero.")
        if self.target_atr_multiplier <= 0:
            raise ValueError("Target ATR multiplier must be greater than zero.")

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
            "previous_close",
        }

    def prepare_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """Add previous trading day's close to every current-day candle."""
        df = dataframe.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["timestamp", "close"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["trade_date"] = df["timestamp"].dt.date

        daily_close = df.groupby("trade_date", sort=True)["close"].last()
        previous_daily_close = daily_close.shift(1)
        df["previous_close"] = df["trade_date"].map(previous_daily_close)

        return df

    def should_enter(
        self,
        row_index: int,
        row: pd.Series,
        day_data: pd.DataFrame,
    ) -> bool:
        if row_index < 1:
            return False

        current_time = row["timestamp"].time()
        if not (
            self.entry_start_time
            <= current_time
            <= self.entry_cutoff_time
        ):
            return False

        previous_day_close = float(row.get("previous_close", 0.0))
        if pd.isna(previous_day_close) or previous_day_close <= 0:
            return False

        day_open = float(day_data.iloc[0]["open"])
        gap_percent = (
            (day_open - previous_day_close)
            / previous_day_close
            * 100.0
        )

        if gap_percent < self.minimum_gap_percent:
            return False

        market_open = day_data.iloc[0]["timestamp"]
        opening_range_end = market_open + pd.Timedelta(
            minutes=self.opening_range_minutes
        )

        if row["timestamp"] < opening_range_end:
            return False

        opening_data = day_data[
            day_data["timestamp"] < opening_range_end
        ]
        if opening_data.empty:
            return False

        opening_high = float(opening_data["high"].max())
        close = float(row["close"])

        if close <= opening_high:
            return False
        if float(row["ema_20"]) <= float(row["ema_50"]):
            return False
        if close <= float(row["vwap"]):
            return False

        rsi = float(row["rsi"])
        if not (self.minimum_rsi <= rsi <= self.maximum_rsi):
            return False

        if float(row["volume_ratio"]) < self.minimum_volume_ratio:
            return False
        if float(row["atr"]) <= 0:
            return False

        return True

    def calculate_stop_loss(
        self,
        row: pd.Series,
        entry_price: float,
    ) -> float:
        return (
            entry_price
            - float(row["atr"]) * self.stop_atr_multiplier
        )

    def calculate_target(
        self,
        row: pd.Series,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        risk_per_share = entry_price - stop_loss
        return (
            entry_price
            + risk_per_share * self.target_atr_multiplier
        )

    def additional_trade_metadata(
        self,
        row: pd.Series,
    ) -> Dict[str, Any]:
        previous_close = float(row["previous_close"])

        return {
            "strategy": self.name,
            "previous_close": previous_close,
            "minimum_gap_percent": float(self.minimum_gap_percent),
            "opening_range_minutes": int(self.opening_range_minutes),
            "minimum_rsi": float(self.minimum_rsi),
            "maximum_rsi": float(self.maximum_rsi),
            "minimum_volume_ratio": float(self.minimum_volume_ratio),
            "stop_atr_multiplier": float(self.stop_atr_multiplier),
            "target_atr_multiplier": float(self.target_atr_multiplier),
            "rsi": float(row["rsi"]),
            "atr": float(row["atr"]),
            "volume_ratio": float(row["volume_ratio"]),
            "ema_20": float(row["ema_20"]),
            "ema_50": float(row["ema_50"]),
            "vwap": float(row["vwap"]),
        }
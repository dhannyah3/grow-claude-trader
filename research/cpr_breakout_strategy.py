"""
CPR Breakout Strategy

Long-only intraday strategy based on the Central Pivot Range.

CPR levels are calculated using the previous trading day's:

- High
- Low
- Close

Entry conditions:

- Price crosses above the CPR top
- EMA20 is above EMA50
- Price is above VWAP
- RSI confirms bullish momentum
- Relative volume exceeds the configured threshold
- ATR is valid

Exit conditions:

- ATR-based stop-loss
- Risk-multiple target
- Day-end exit handled by BaseStrategyEvaluator
"""

from typing import Any, Dict, Set

import pandas as pd

from research.base_strategy import BaseStrategy


class CPRBreakoutStrategy(BaseStrategy):
    """Long-only CPR breakout strategy."""

    name = "CPR_BREAKOUT"

    def __init__(
        self,
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

        self.minimum_rsi = float(
            minimum_rsi
        )
        self.maximum_rsi = float(
            maximum_rsi
        )
        self.minimum_volume_ratio = float(
            minimum_volume_ratio
        )
        self.stop_atr_multiplier = float(
            stop_atr_multiplier
        )
        self.target_atr_multiplier = float(
            target_atr_multiplier
        )

        if self.minimum_rsi > self.maximum_rsi:
            raise ValueError(
                "Minimum RSI cannot exceed maximum RSI."
            )

        if self.minimum_volume_ratio < 0:
            raise ValueError(
                "Minimum volume ratio cannot be negative."
            )

        if self.stop_atr_multiplier <= 0:
            raise ValueError(
                "Stop ATR multiplier must be greater than zero."
            )

        if self.target_atr_multiplier <= 0:
            raise ValueError(
                "Target ATR multiplier must be greater than zero."
            )

    def required_columns(
        self,
    ) -> Set[str]:
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
            "rsi",
            "atr",
            "volume_ratio",
            "pivot",
            "cpr_top",
            "cpr_bottom",
        }

    def prepare_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Calculate previous-day CPR levels and add them
        to every candle of the current trading day.
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
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df = df.dropna(
            subset=[
                "timestamp",
                "high",
                "low",
                "close",
            ]
        )

        df = df.sort_values(
            "timestamp"
        ).reset_index(
            drop=True
        )

        df["trade_date"] = (
            df["timestamp"].dt.date
        )

        daily_prices = (
            df.groupby(
                "trade_date",
                sort=True,
            )
            .agg(
                daily_high=(
                    "high",
                    "max",
                ),
                daily_low=(
                    "low",
                    "min",
                ),
                daily_close=(
                    "close",
                    "last",
                ),
            )
        )

        previous_day = (
            daily_prices.shift(1)
        )

        previous_day["pivot"] = (
            previous_day["daily_high"]
            + previous_day["daily_low"]
            + previous_day["daily_close"]
        ) / 3.0

        previous_day["bc"] = (
            previous_day["daily_high"]
            + previous_day["daily_low"]
        ) / 2.0

        previous_day["tc"] = (
            2.0 * previous_day["pivot"]
            - previous_day["bc"]
        )

        previous_day["cpr_top"] = (
            previous_day[
                [
                    "bc",
                    "tc",
                ]
            ].max(
                axis=1
            )
        )

        previous_day["cpr_bottom"] = (
            previous_day[
                [
                    "bc",
                    "tc",
                ]
            ].min(
                axis=1
            )
        )

        previous_day["cpr_width"] = (
            previous_day["cpr_top"]
            - previous_day["cpr_bottom"]
        )

        previous_day[
            "cpr_width_percent"
        ] = (
            previous_day["cpr_width"]
            / previous_day["pivot"]
            * 100.0
        )

        cpr_columns = previous_day[
            [
                "daily_high",
                "daily_low",
                "daily_close",
                "pivot",
                "bc",
                "tc",
                "cpr_top",
                "cpr_bottom",
                "cpr_width",
                "cpr_width_percent",
            ]
        ]

        df = df.merge(
            cpr_columns,
            left_on="trade_date",
            right_index=True,
            how="left",
        )

        return df

    def should_enter(
        self,
        row_index: int,
        row: pd.Series,
        day_data: pd.DataFrame,
    ) -> bool:
        """
        Return True when price crosses above the CPR top
        with bullish trend, VWAP, RSI, volume and ATR confirmation.
        """

        if row_index < 1:
            return False

        current_time = (
            row["timestamp"].time()
        )

        if not (
            self.entry_start_time
            <= current_time
            <= self.entry_cutoff_time
        ):
            return False

        required_values = [
            "cpr_top",
            "cpr_bottom",
            "pivot",
            "ema_20",
            "ema_50",
            "vwap",
            "rsi",
            "atr",
            "volume_ratio",
        ]

        for column in required_values:
            if pd.isna(
                row.get(column)
            ):
                return False

        previous_row = (
            day_data.iloc[
                row_index - 1
            ]
        )

        cpr_top = float(
            row["cpr_top"]
        )

        current_close = float(
            row["close"]
        )

        previous_close = float(
            previous_row["close"]
        )

        crossed_above_cpr = (
            previous_close
            <= cpr_top
            and current_close
            > cpr_top
        )

        if not crossed_above_cpr:
            return False

        ema_20 = float(
            row["ema_20"]
        )

        ema_50 = float(
            row["ema_50"]
        )

        if ema_20 <= ema_50:
            return False

        vwap = float(
            row["vwap"]
        )

        if current_close <= vwap:
            return False

        rsi = float(
            row["rsi"]
        )

        if not (
            self.minimum_rsi
            <= rsi
            <= self.maximum_rsi
        ):
            return False

        volume_ratio = float(
            row["volume_ratio"]
        )

        if (
            volume_ratio
            < self.minimum_volume_ratio
        ):
            return False

        atr = float(
            row["atr"]
        )

        if atr <= 0:
            return False

        return True

    def calculate_stop_loss(
        self,
        row: pd.Series,
        entry_price: float,
    ) -> float:
        """
        Place the stop below entry using ATR.

        The stop is also prevented from being above
        the CPR bottom.
        """

        atr_stop = (
            entry_price
            - float(row["atr"])
            * self.stop_atr_multiplier
        )

        cpr_bottom = float(
            row["cpr_bottom"]
        )

        return min(
            atr_stop,
            cpr_bottom,
        )

    def calculate_target(
        self,
        row: pd.Series,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Calculate target from the actual entry-to-stop risk.
        """

        risk_per_share = (
            entry_price
            - stop_loss
        )

        return (
            entry_price
            + risk_per_share
            * self.target_atr_multiplier
        )

    def additional_trade_metadata(
        self,
        row: pd.Series,
    ) -> Dict[str, Any]:
        """Return CPR and indicator values for trade reporting."""

        return {
            "strategy": self.name,
            "minimum_rsi": float(
                self.minimum_rsi
            ),
            "maximum_rsi": float(
                self.maximum_rsi
            ),
            "minimum_volume_ratio": float(
                self.minimum_volume_ratio
            ),
            "stop_atr_multiplier": float(
                self.stop_atr_multiplier
            ),
            "target_atr_multiplier": float(
                self.target_atr_multiplier
            ),
            "previous_day_high": float(
                row["daily_high"]
            ),
            "previous_day_low": float(
                row["daily_low"]
            ),
            "previous_day_close": float(
                row["daily_close"]
            ),
            "pivot": float(
                row["pivot"]
            ),
            "bc": float(
                row["bc"]
            ),
            "tc": float(
                row["tc"]
            ),
            "cpr_top": float(
                row["cpr_top"]
            ),
            "cpr_bottom": float(
                row["cpr_bottom"]
            ),
            "cpr_width": float(
                row["cpr_width"]
            ),
            "cpr_width_percent": float(
                row["cpr_width_percent"]
            ),
            "rsi": float(
                row["rsi"]
            ),
            "atr": float(
                row["atr"]
            ),
            "volume_ratio": float(
                row["volume_ratio"]
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
        }
"""
EMA Trend Continuation Strategy

Uses the shared research framework.

Entry idea:
- Strong uptrend
- Pullback to EMA20
- Trend resumes
"""

from research.base_strategy import BaseStrategy


class EMATrendContinuationStrategy(BaseStrategy):
    """
    EMA Trend Continuation Strategy.
    """

    name = "EMA_TREND_CONTINUATION"

    def __init__(
        self,
        stop_atr_multiplier: float = 1.0,
        target_atr_multiplier: float = 2.5,
        minimum_rsi: float = 55.0,
        maximum_rsi: float = 75.0,
        maximum_ema_distance_percent: float = 0.30,
        minimum_volume_ratio: float = 1.0,
        pullback_lookback_candles: int = 5,
    ):
        super().__init__()

        self.stop_atr_multiplier = float(
            stop_atr_multiplier
        )

        self.target_atr_multiplier = float(
            target_atr_multiplier
        )

        self.minimum_rsi = float(
            minimum_rsi
        )

        self.maximum_rsi = float(
            maximum_rsi
        )

        self.maximum_ema_distance_percent = float(
            maximum_ema_distance_percent
        )

        self.minimum_volume_ratio = float(
            minimum_volume_ratio
        )

        self.pullback_lookback_candles = int(
            pullback_lookback_candles
        )

    def required_columns(self) -> set:
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
            "rsi",
            "volume_ratio",
        }

    def should_enter(
        self,
        row_index,
        row,
        day_data,
    ) -> bool:

        if row_index < self.pullback_lookback_candles:
            return False

        if (
            row["ema_20"] != row["ema_20"]
            or row["ema_50"] != row["ema_50"]
            or row["atr"] != row["atr"]
            or row["rsi"] != row["rsi"]
        ):
            return False

        # Uptrend
        if row["ema_20"] <= row["ema_50"]:
            return False

        # Price must be above EMA20
        if row["close"] <= row["ema_20"]:
            return False

        # RSI filter
        if (
            row["rsi"] < self.minimum_rsi
            or row["rsi"] > self.maximum_rsi
        ):
            return False

        # Volume confirmation
        if (
            row["volume_ratio"]
            < self.minimum_volume_ratio
        ):
            return False

        # Price should still be close to EMA20
        ema_distance = (
            abs(
                row["close"]
                - row["ema_20"]
            )
            / row["ema_20"]
            * 100
        )

        if (
            ema_distance
            > self.maximum_ema_distance_percent
        ):
            return False

        # Recent candles must have touched EMA20
        recent = day_data.iloc[
            row_index
            - self.pullback_lookback_candles:
            row_index
        ]

        if (
            recent["low"].min()
            > row["ema_20"]
        ):
            return False

        return True

    def calculate_stop_loss(
        self,
        row,
        entry_price,
    ) -> float:
        """
        ATR-based stop loss.
        """

        return (
            entry_price
            - (
                row["atr"]
                * self.stop_atr_multiplier
            )
        )

    def calculate_target(
        self,
        row,
        entry_price,
        stop_loss,
    ) -> float:
        """
        ATR-based risk-reward target.
        """

        risk = (
            entry_price
            - stop_loss
        )

        return (
            entry_price
            + (
                risk
                * self.target_atr_multiplier
            )
        )

    def additional_trade_metadata(
        self,
        row,
    ) -> dict:

        return {
            "ema_20": float(
                row["ema_20"]
            ),
            "ema_50": float(
                row["ema_50"]
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
            "ema_pullback_lookback_candles":
                self.pullback_lookback_candles,
            "maximum_ema_distance_percent":
                self.maximum_ema_distance_percent,
        }
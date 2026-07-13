from typing import Any, Dict

import pandas as pd

from strategies.base_strategy import BaseStrategy


class VWAPPullbackStrategy(BaseStrategy):
    """
    Long-only VWAP pullback strategy.

    Looks for:
    - an overall bullish trend;
    - price pulling back close to VWAP;
    - price closing back above VWAP;
    - RSI in a healthy bullish range;
    - valid ATR for stop placement.
    """

    name = "VWAP_PULLBACK"

    def analyze(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict[str, Any]:
        if dataframe.empty:
            return self.wait_signal(
                "No market data."
            )

        required_columns = {
            "close",
            "low",
            "ema_20",
            "ema_50",
            "vwap",
            "rsi",
            "atr",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:
            return self.wait_signal(
                "Missing required indicators.",
                metadata={
                    "missing_columns": sorted(
                        missing_columns
                    ),
                },
            )

        if len(dataframe) < 2:
            return self.wait_signal(
                "Not enough candles."
            )

        previous = dataframe.iloc[-2]
        latest = dataframe.iloc[-1]

        required_values = [
            latest.get("close"),
            latest.get("low"),
            latest.get("ema_20"),
            latest.get("ema_50"),
            latest.get("vwap"),
            latest.get("rsi"),
            latest.get("atr"),
            previous.get("close"),
            previous.get("vwap"),
        ]

        if any(
            pd.isna(value)
            for value in required_values
        ):
            return self.wait_signal(
                "Indicator values unavailable."
            )

        bullish_trend = (
            latest["ema_20"]
            > latest["ema_50"]
        )

        previous_near_or_below_vwap = (
            previous["close"]
            <= previous["vwap"] * 1.002
        )

        reclaimed_vwap = (
            latest["close"]
            > latest["vwap"]
        )

        healthy_rsi = (
            50
            <= latest["rsi"]
            <= 68
        )

        if not bullish_trend:
            return self.wait_signal(
                "EMA trend is not bullish."
            )

        if not previous_near_or_below_vwap:
            return self.wait_signal(
                "No VWAP pullback detected."
            )

        if not reclaimed_vwap:
            return self.wait_signal(
                "Price has not reclaimed VWAP."
            )

        if not healthy_rsi:
            return self.wait_signal(
                "RSI is outside the preferred range."
            )

        entry_price = float(
            latest["close"]
        )

        atr = float(
            latest["atr"]
        )

        if atr <= 0:
            return self.wait_signal(
                "Invalid ATR."
            )

        stop_loss = min(
            float(latest["low"]),
            float(latest["vwap"]) - atr,
        )

        risk_per_share = (
            entry_price - stop_loss
        )

        if risk_per_share <= 0:
            return self.wait_signal(
                "Invalid risk distance."
            )

        target = (
            entry_price
            + risk_per_share * 2
        )

        score = 70

        if latest["close"] > latest["ema_20"]:
            score += 10

        if 55 <= latest["rsi"] <= 65:
            score += 10

        if latest["close"] > latest["vwap"] * 1.001:
            score += 10

        return self.trade_signal(
            action="BUY",
            score=min(score, 100),
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            reason=(
                "Bullish trend with VWAP "
                "pullback and reclaim."
            ),
            metadata={
                "vwap": round(
                    float(latest["vwap"]),
                    2,
                ),
                "rsi": round(
                    float(latest["rsi"]),
                    2,
                ),
                "atr": round(
                    atr,
                    2,
                ),
            },
        )
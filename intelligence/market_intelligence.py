from typing import Any, Dict

import pandas as pd


class MarketIntelligence:
    """
    Produces a higher-level summary of the market.

    This class does not decide which strategy to trade.
    It simply converts raw indicators into market states
    that every strategy can use.
    """

    def analyze(
        self,
        dataframe: pd.DataFrame,
        regime: Dict[str, Any],
    ) -> Dict[str, Any]:

        if dataframe.empty:
            raise ValueError(
                "DataFrame cannot be empty."
            )

        latest = dataframe.iloc[-1]

        intelligence = {
            "trend": regime.get("trend"),
            "trend_strength": regime.get(
                "trend_strength"
            ),
            "volatility": regime.get(
                "volatility"
            ),
            "gap": regime.get("gap"),
        }

        intelligence["rsi_state"] = (
            self._rsi_state(
                float(latest["rsi"])
            )
        )

        intelligence["macd_state"] = (
            self._macd_state(
                float(latest["macd"]),
                float(latest["macd_signal"]),
            )
        )

        intelligence["vwap_state"] = (
            self._vwap_state(
                float(latest["close"]),
                float(latest["vwap"]),
            )
        )

        intelligence["volume_state"] = (
            self._volume_state(
                dataframe
            )
        )

        intelligence["market_quality"] = (
            self._quality_score(
                intelligence
            )
        )

        return intelligence

    # -------------------------------------

    def _rsi_state(
        self,
        rsi: float,
    ) -> str:

        if rsi >= 70:
            return "OVERBOUGHT"

        if rsi >= 55:
            return "BULLISH"

        if rsi >= 45:
            return "NEUTRAL"

        if rsi >= 30:
            return "BEARISH"

        return "OVERSOLD"

    # -------------------------------------

    def _macd_state(
        self,
        macd: float,
        signal: float,
    ) -> str:

        if macd > signal:
            return "BULLISH"

        if macd < signal:
            return "BEARISH"

        return "NEUTRAL"

    # -------------------------------------

    def _vwap_state(
        self,
        close: float,
        vwap: float,
    ) -> str:

        difference = (
            abs(close - vwap)
            / close
        ) * 100

        if difference < 0.15:
            return "NEAR"

        if close > vwap:
            return "ABOVE"

        return "BELOW"

    # -------------------------------------

    def _volume_state(
        self,
        dataframe: pd.DataFrame,
    ) -> str:

        if len(dataframe) < 20:
            return "UNKNOWN"

        latest = float(
            dataframe.iloc[-1]["volume"]
        )

        average = float(
            dataframe["volume"]
            .tail(20)
            .mean()
        )

        if average <= 0:
            return "UNKNOWN"

        ratio = latest / average

        if ratio >= 1.5:
            return "HIGH"

        if ratio >= 0.8:
            return "NORMAL"

        return "LOW"

    # -------------------------------------

    def _quality_score(
        self,
        intelligence: Dict[str, Any],
    ) -> int:

        score = 0

        if intelligence["trend"] == "TRENDING":
            score += 20

        if intelligence["trend_strength"] in (
            "STRONG",
            "VERY_STRONG",
        ):
            score += 20

        if intelligence["rsi_state"] == "BULLISH":
            score += 15

        if intelligence["macd_state"] == "BULLISH":
            score += 15

        if intelligence["vwap_state"] == "ABOVE":
            score += 15

        if intelligence["volume_state"] == "HIGH":
            score += 15

        if intelligence["volatility"] == "LOW":
            score += 10

        if score > 100:
            score = 100

        return score
    
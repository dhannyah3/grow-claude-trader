from typing import Dict, Optional


class MarketRegime:
    """
    Determines the current market regime.

    Initial version:
    - Trend
    - Volatility
    - Gap

    Future versions:
    - ADX
    - News sentiment
    - Sector strength
    - India VIX
    """
    
    def analyze(
        self,
        latest: Dict,
        previous_close: Optional[float] = None,
    ) -> Dict:

        ema20 = float(latest["ema_20"])
        ema50 = float(latest["ema_50"])

        close = float(latest["close"])

        atr = float(latest["atr"])

        open_price = float(latest["open"])

        # -------------------
        # Trend
        # -------------------

        if ema20 > ema50:
            trend = "TRENDING"

        elif ema20 < ema50:
            trend = "DOWNTREND"

        else:
            trend = "RANGE"

        # -------------------
        # Volatility
        # -------------------

        atr_percent = (
            atr / close
        ) * 100

        if atr_percent > 1.5:
            volatility = "HIGH"

        elif atr_percent > 0.8:
            volatility = "MEDIUM"

        else:
            volatility = "LOW"

        # -------------------
        # Gap
        # -------------------

        if (
            previous_close is None
            or previous_close <= 0
        ):
            gap_percent = 0.0
            gap = "UNKNOWN"

        else:
            gap_percent = (
                (open_price - previous_close)
                / previous_close
            ) * 100

            if gap_percent > 1:
                gap = "GAP_UP"

            elif gap_percent < -1:
                gap = "GAP_DOWN"

            else:
                gap = "NO_GAP"
        return {
            "trend": trend,
            "volatility": volatility,
            "gap": gap,
            "gap_percent": round(
                gap_percent,
                2,
            ),
            "atr_percent": round(
                atr_percent,
                2,
            ),
        }
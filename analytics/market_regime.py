from typing import Any, Dict, Optional


class MarketRegime:
    """
    Detects the current market regime using:

    - EMA trend
    - ATR-based volatility
    - Opening gap
    """

    def analyze(
        self,
        latest: Dict[str, Any],
        previous_close: Optional[float] = None,
    ) -> Dict[str, Any]:
        required_fields = {
            "open",
            "close",
            "ema_20",
            "ema_50",
            "atr",
        }

        missing_fields = (
            required_fields
            - set(latest.keys())
        )

        if missing_fields:
            raise ValueError(
                "Missing market-regime fields: "
                + ", ".join(
                    sorted(missing_fields)
                )
            )

        open_price = float(
            latest["open"]
        )

        close = float(
            latest["close"]
        )

        ema20 = float(
            latest["ema_20"]
        )

        ema50 = float(
            latest["ema_50"]
        )

        atr = float(
            latest["atr"]
        )

        if close <= 0:
            raise ValueError(
                "Close price must be positive."
            )

        if open_price <= 0:
            raise ValueError(
                "Open price must be positive."
            )

        if atr < 0:
            raise ValueError(
                "ATR cannot be negative."
            )

        # -------------------------
        # Trend classification
        # -------------------------

        ema_difference_percent = (
            abs(ema20 - ema50)
            / close
            * 100
        )

        if ema_difference_percent < 0.10:
            trend = "RANGE_BOUND"

        elif ema20 > ema50:
            trend = "TRENDING"

        else:
            trend = "DOWNTREND"

        # -------------------------
        # Volatility classification
        # -------------------------

        atr_percent = (
            atr / close
            * 100
        )

        if atr_percent >= 1.50:
            volatility = "HIGH"

        elif atr_percent >= 0.80:
            volatility = "MEDIUM"

        else:
            volatility = "LOW"

        # -------------------------
        # Opening-gap classification
        # -------------------------

        if (
            previous_close is None
            or previous_close <= 0
        ):
            gap_percent = 0.0
            gap = "UNKNOWN"

        else:
            raw_gap_percent = (
                (
                    open_price
                    - previous_close
                )
                / previous_close
                * 100
            )

            gap_percent = round(
                raw_gap_percent,
                2,
            )

            if gap_percent >= 1.0:
                gap = "GAP_UP"

            elif gap_percent <= -1.0:
                gap = "GAP_DOWN"

            else:
                gap = "NO_GAP"

        return {
            "trend": trend,
            "volatility": volatility,
            "gap": gap,
            "gap_percent": gap_percent,
            "atr_percent": round(
                atr_percent,
                2,
            ),
            "ema_difference_percent": round(
                ema_difference_percent,
                3,
            ),
        }

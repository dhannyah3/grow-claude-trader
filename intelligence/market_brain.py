from typing import Any, Dict


class MarketBrain:
    """
    Selects a trading strategy and risk level
    from the detected market regime.

    Version 1 uses:
    - Trend
    - Volatility
    - Opening gap
    """

    def decide(
        self,
        regime_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        trend = str(
            regime_data.get(
                "trend",
                "UNKNOWN",
            )
        ).upper()

        volatility = str(
            regime_data.get(
                "volatility",
                "UNKNOWN",
            )
        ).upper()

        gap = str(
            regime_data.get(
                "gap",
                "UNKNOWN",
            )
        ).upper()

        strategy = "VWAP_PULLBACK"
        confidence = 50
        risk_multiplier = 1.0
        reasons = []

        # -------------------------
        # Strategy selection
        # -------------------------

        if trend == "TRENDING":
            strategy = "ORB_BREAKOUT"
            confidence += 20

            reasons.append(
                "Trending conditions favor "
                "breakout trading."
            )

        elif trend == "RANGE_BOUND":
            strategy = "VWAP_PULLBACK"
            confidence += 20

            reasons.append(
                "Range-bound conditions favor "
                "VWAP pullbacks."
            )

        elif trend == "DOWNTREND":
            strategy = "VWAP_PULLBACK"
            confidence -= 10
            risk_multiplier *= 0.5

            reasons.append(
                "Downtrend detected. Long-only "
                "trading risk reduced."
            )

        else:
            strategy = "VWAP_PULLBACK"

            reasons.append(
                "Trend is unclear. Using the "
                "more conservative VWAP strategy."
            )

        # -------------------------
        # Volatility adjustment
        # -------------------------

        if volatility == "HIGH":
            risk_multiplier *= 0.5
            confidence -= 10

            reasons.append(
                "High volatility detected; "
                "risk reduced by 50%."
            )

        elif volatility == "MEDIUM":
            reasons.append(
                "Volatility is within a "
                "moderate range."
            )

        elif volatility == "LOW":
            risk_multiplier *= 0.75

            reasons.append(
                "Low volatility detected; "
                "risk reduced by 25%."
            )

        else:
            confidence -= 5

            reasons.append(
                "Volatility information "
                "is unavailable."
            )

        # -------------------------
        # Gap adjustment
        # -------------------------

        if gap in {
            "GAP_UP",
            "GAP_DOWN",
        }:
            risk_multiplier *= 0.75
            confidence -= 5

            reasons.append(
                f"{gap} detected; risk reduced "
                "by an additional 25%."
            )

        elif gap == "NO_GAP":
            reasons.append(
                "No significant opening "
                "gap detected."
            )

        else:
            reasons.append(
                "Gap information is unavailable."
            )

        # -------------------------
        # Final limits
        # -------------------------

        risk_multiplier = max(
            0.25,
            min(
                risk_multiplier,
                1.0,
            ),
        )

        confidence = max(
            0,
            min(
                confidence,
                100,
            ),
        )

        should_trade = (
            confidence >= 50
            and trend != "DOWNTREND"
        )

        return {
            "should_trade": should_trade,
            "recommended_strategy": strategy,
            "confidence": confidence,
            "risk_multiplier": round(
                risk_multiplier,
                2,
            ),
            "reasons": reasons,
            "regime": {
                "trend": trend,
                "volatility": volatility,
                "gap": gap,
            },
        }

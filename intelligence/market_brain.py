from typing import Any, Dict


class MarketBrain:
    """
    Selects a strategy and risk level from market conditions.

    Version 1 uses measurable market-regime data only.
    News and economic-calendar analysis will be added later.
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

        if trend == "TRENDING":
            strategy = "ORB_BREAKOUT"
            confidence += 20
            reasons.append(
                "Trending conditions favor breakout trading."
            )

        elif trend == "RANGE_BOUND":
            strategy = "VWAP_PULLBACK"
            confidence += 20
            reasons.append(
                "Range-bound conditions favor VWAP pullbacks."
            )

        else:
            reasons.append(
                "Trend is unclear; using the more conservative "
                "VWAP pullback strategy."
            )

        if volatility == "HIGH":
            risk_multiplier *= 0.5
            confidence -= 10
            reasons.append(
                "High volatility detected; risk reduced by 50%."
            )

        elif volatility == "LOW":
            risk_multiplier *= 0.75
            reasons.append(
                "Low volatility detected; risk reduced by 25%."
            )

        else:
            reasons.append(
                "Volatility is within a normal range."
            )

        if gap in {
            "GAP_UP",
            "GAP_DOWN",
        }:
            risk_multiplier *= 0.75
            confidence -= 5
            reasons.append(
                f"{gap} detected; risk reduced by an "
                "additional 25%."
            )

        elif gap == "NO_GAP":
            reasons.append(
                "No significant opening gap detected."
            )

        else:
            reasons.append(
                "Gap information is unavailable."
            )

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

        should_trade = confidence >= 50

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
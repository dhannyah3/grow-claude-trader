from typing import Any, Dict

from intelligence.strategy_ranker import StrategyRanker


class MarketBrain:
    """
    Chooses the highest-ranked strategy and
    determines whether the bot should trade.
    """

    def __init__(
        self,
        minimum_strategy_score: int = 55,
    ) -> None:
        self.minimum_strategy_score = int(
            minimum_strategy_score
        )

        self.strategy_ranker = (
            StrategyRanker()
        )

    def decide(
        self,
        regime_data: Dict[str, Any],
        intelligence: Dict[str, Any],
    ) -> Dict[str, Any]:
        rankings = self.strategy_ranker.rank(
            regime_data=regime_data,
            intelligence=intelligence,
        )

        if not rankings:
            return {
                "should_trade": False,
                "recommended_strategy": (
                    "VWAP_PULLBACK"
                ),
                "confidence": 0,
                "risk_multiplier": 0.25,
                "reasons": [
                    "No strategies were available "
                    "for ranking."
                ],
                "strategy_rankings": [],
                "regime": regime_data,
            }

        best = rankings[0]

        selected_strategy = str(
            best["strategy"]
        )

        strategy_score = int(
            best["score"]
        )

        volatility = str(
            regime_data.get(
                "volatility",
                "UNKNOWN",
            )
        ).upper()

        trend = str(
            regime_data.get(
                "trend",
                "UNKNOWN",
            )
        ).upper()

        risk_multiplier = 1.0
        reasons = list(
            best.get(
                "reasons",
                [],
            )
        )

        if volatility == "HIGH":
            risk_multiplier *= 0.5
            reasons.append(
                "High volatility reduced risk by 50%."
            )

        elif volatility == "LOW":
            risk_multiplier *= 0.75
            reasons.append(
                "Low volatility reduced risk by 25%."
            )

        if trend == "DOWNTREND":
            risk_multiplier *= 0.5
            reasons.append(
                "Downtrend reduced long-only exposure."
            )

        market_quality = int(
            intelligence.get(
                "market_quality",
                0,
            )
            or 0
        )

        if market_quality < 50:
            risk_multiplier *= 0.5
            reasons.append(
                "Weak market quality reduced risk."
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
                strategy_score,
                100,
            ),
        )

        should_trade = (
            strategy_score
            >= self.minimum_strategy_score
            and trend != "DOWNTREND"
        )

        if not should_trade:
            reasons.append(
                "Best strategy did not meet "
                "the minimum trading threshold."
            )

        return {
            "should_trade": should_trade,
            "recommended_strategy": (
                selected_strategy
            ),
            "confidence": confidence,
            "risk_multiplier": round(
                risk_multiplier,
                2,
            ),
            "reasons": reasons,
            "strategy_rankings": rankings,
            "regime": {
                "trend": trend,
                "volatility": volatility,
                "gap": str(
                    regime_data.get(
                        "gap",
                        "UNKNOWN",
                    )
                ).upper(),
            },
            "market_quality": market_quality,
        }
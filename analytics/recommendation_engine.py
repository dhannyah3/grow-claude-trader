"""
Recommendation Engine

Version 6.3.3

Uses MarketLearning statistics to score,
rank, and evaluate trading strategies.

Current version supports:

- Reading strategy statistics
- Calculating a quality score from 0 to 100
- Confidence-weighted scoring
- Win-rate scoring
- Average-R scoring
- Expectancy scoring
- Profit-factor scoring
- Sorting strategies by score
- Assigning strategy ranks
- Identifying the best strategy
- Returning one of:
  - TAKE_TRADE
  - WATCH
  - SKIP
  - INSUFFICIENT_DATA
- Building human-readable decision reasons
- Calculating decision confidence

Future versions will add:

- Risk level
- Strategy-regime recommendations
- Position-size recommendations
- Trading-workflow integration
"""

from typing import Any, Dict, List, Optional


class RecommendationEngine:
    """
    Generates strategy recommendations from
    MarketLearning statistics.
    """

    def __init__(self) -> None:
        self.confidence_weight = 30.0
        self.win_rate_weight = 25.0
        self.average_r_weight = 20.0
        self.expectancy_weight = 15.0
        self.profit_factor_weight = 10.0

        self.maximum_average_r = 3.0
        self.maximum_expectancy = 500.0
        self.maximum_profit_factor = 5.0

        self.take_trade_score = 75.0
        self.watch_score = 50.0

    def rank_strategies(
        self,
        strategy_statistics: Dict[
            str,
            Dict[str, Any],
        ],
    ) -> List[Dict[str, Any]]:
        """
        Calculate a quality score for every
        strategy, sort highest first, and assign
        ranks beginning at one.
        """
        ranked: List[
            Dict[str, Any]
        ] = []

        if not isinstance(
            strategy_statistics,
            dict,
        ):
            return ranked

        for strategy, statistics in (
            strategy_statistics.items()
        ):
            if not isinstance(
                statistics,
                dict,
            ):
                continue

            normalized_strategy = str(
                strategy
            ).strip().upper()

            if not normalized_strategy:
                continue

            score = (
                self._calculate_strategy_score(
                    statistics
                )
            )

            ranked.append(
                {
                    "strategy": (
                        normalized_strategy
                    ),
                    "score": score,
                    "statistics": dict(
                        statistics
                    ),
                }
            )

        ranked.sort(
            key=lambda item: (
                self._to_float(
                    item.get(
                        "score",
                        0.0,
                    )
                )
            ),
            reverse=True,
        )

        for index, strategy_result in (
            enumerate(
                ranked,
                start=1,
            )
        ):
            strategy_result[
                "rank"
            ] = index

        return ranked

    def recommend(
        self,
        strategy_statistics: Dict[
            str,
            Dict[str, Any],
        ],
    ) -> Dict[str, Any]:
        """
        Rank strategies and make a decision
        using the highest-ranked strategy.
        """
        ranked = self.rank_strategies(
            strategy_statistics
        )

        best_strategy: Optional[
            Dict[str, Any]
        ] = (
            ranked[0]
            if ranked
            else None
        )

        if best_strategy is None:
            reasons = [
                (
                    "No valid strategy statistics "
                    "were available."
                ),
                (
                    "The engine cannot make an "
                    "actionable recommendation."
                ),
            ]

            return {
                "decision": (
                    "INSUFFICIENT_DATA"
                ),
                "recommendation": (
                    "INSUFFICIENT_DATA"
                ),
                "decision_confidence": 0.0,
                "reasons": reasons,
                "best_strategy": None,
                "strategies": [],
                "strategy_count": 0,
            }

        decision = self._make_decision(
            best_strategy
        )

        decision_confidence = (
            self._calculate_decision_confidence(
                best_strategy
            )
        )

        reasons = self._build_reasons(
            strategy_result=best_strategy,
            decision=decision,
        )

        return {
            "decision": decision,
            "recommendation": decision,
            "decision_confidence": (
                decision_confidence
            ),
            "reasons": reasons,
            "best_strategy": (
                best_strategy
            ),
            "strategies": ranked,
            "strategy_count": len(
                ranked
            ),
        }

    def _make_decision(
        self,
        strategy_result: Dict[
            str,
            Any,
        ],
    ) -> str:
        """
        Convert the highest-ranked strategy
        into an actionable trading decision.
        """
        if not isinstance(
            strategy_result,
            dict,
        ):
            return (
                "INSUFFICIENT_DATA"
            )

        statistics = (
            strategy_result.get(
                "statistics",
                {},
            )
        )

        if not isinstance(
            statistics,
            dict,
        ):
            return (
                "INSUFFICIENT_DATA"
            )

        learning_active = bool(
            statistics.get(
                "learning_active",
                False,
            )
        )

        if not learning_active:
            return (
                "INSUFFICIENT_DATA"
            )

        score = self._to_float(
            strategy_result.get(
                "score",
                0.0,
            )
        )

        expectancy = self._to_float(
            statistics.get(
                "expectancy",
                0.0,
            )
        )

        average_r = self._to_float(
            statistics.get(
                "average_r",
                0.0,
            )
        )

        if (
            score
            >= self.take_trade_score
            and expectancy > 0
            and average_r > 0
        ):
            return "TAKE_TRADE"

        if (
            score
            >= self.watch_score
            and expectancy >= 0
        ):
            return "WATCH"

        return "SKIP"

    def _build_reasons(
        self,
        strategy_result: Dict[
            str,
            Any,
        ],
        decision: str,
    ) -> List[str]:
        """
        Explain why the recommendation engine
        produced its final decision.
        """
        reasons: List[str] = []

        if not isinstance(
            strategy_result,
            dict,
        ):
            return [
                (
                    "No valid strategy result "
                    "was available."
                )
            ]

        statistics = (
            strategy_result.get(
                "statistics",
                {},
            )
        )

        if not isinstance(
            statistics,
            dict,
        ):
            return [
                (
                    "Strategy statistics were "
                    "unavailable."
                )
            ]

        strategy = str(
            strategy_result.get(
                "strategy",
                "UNKNOWN",
            )
        ).strip().upper()

        rank = int(
            self._to_float(
                strategy_result.get(
                    "rank",
                    0,
                )
            )
        )

        score = self._to_float(
            strategy_result.get(
                "score",
                0.0,
            )
        )

        confidence_score = self._clamp(
            self._to_float(
                statistics.get(
                    "confidence_score",
                    0.0,
                )
            ),
            minimum=0.0,
            maximum=1.0,
        )

        confidence_label = str(
            statistics.get(
                "confidence_label",
                "UNKNOWN",
            )
        ).strip().upper()

        expectancy = self._to_float(
            statistics.get(
                "expectancy",
                0.0,
            )
        )

        average_r = self._to_float(
            statistics.get(
                "average_r",
                0.0,
            )
        )

        win_rate = self._to_float(
            statistics.get(
                "win_rate",
                0.0,
            )
        )

        sample_size = int(
            self._to_float(
                statistics.get(
                    "sample_size",
                    statistics.get(
                        "trades",
                        0,
                    ),
                )
            )
        )

        learning_active = bool(
            statistics.get(
                "learning_active",
                False,
            )
        )

        reasons.append(
            (
                f"{strategy} is ranked #{rank} "
                f"with a score of {score:.2f}."
            )
        )

        reasons.append(
            (
                f"The historical sample contains "
                f"{sample_size} trades."
            )
        )

        if learning_active:
            reasons.append(
                (
                    "Learning is active because "
                    "the minimum sample threshold "
                    "has been reached."
                )
            )
        else:
            reasons.append(
                (
                    "Historical sample is not large "
                    "enough for active learning."
                )
            )

        reasons.append(
            (
                f"Confidence is {confidence_label} "
                f"({confidence_score:.0%})."
            )
        )

        if expectancy > 0:
            reasons.append(
                (
                    "Historical expectancy is "
                    f"positive at ₹{expectancy:.2f} "
                    "per trade."
                )
            )

        elif expectancy < 0:
            reasons.append(
                (
                    "Historical expectancy is "
                    f"negative at ₹{expectancy:.2f} "
                    "per trade."
                )
            )

        else:
            reasons.append(
                (
                    "Historical expectancy is "
                    "neutral."
                )
            )

        if average_r >= 2.0:
            reasons.append(
                (
                    "Average R multiple is strong "
                    f"at {average_r:.2f}R."
                )
            )

        elif average_r > 0:
            reasons.append(
                (
                    "Average R multiple is positive "
                    f"at {average_r:.2f}R."
                )
            )

        else:
            reasons.append(
                (
                    "Average R multiple is not "
                    "positive."
                )
            )

        reasons.append(
            (
                f"Historical win rate is "
                f"{win_rate:.2f}%."
            )
        )

        if decision == "TAKE_TRADE":
            reasons.append(
                (
                    "The strategy passed all "
                    "take-trade thresholds."
                )
            )

        elif decision == "WATCH":
            reasons.append(
                (
                    "The strategy is promising but "
                    "did not meet the full "
                    "take-trade threshold."
                )
            )

        elif decision == "SKIP":
            reasons.append(
                (
                    "The strategy did not meet the "
                    "required quality thresholds."
                )
            )

        elif decision == (
            "INSUFFICIENT_DATA"
        ):
            reasons.append(
                (
                    "The available sample is "
                    "insufficient for an actionable "
                    "recommendation."
                )
            )

        return reasons

    def _calculate_decision_confidence(
        self,
        strategy_result: Dict[
            str,
            Any,
        ],
    ) -> float:
        """
        Calculate confidence in the final
        recommendation from zero to 100.

        This is different from historical
        confidence because it combines the
        strategy score, historical confidence,
        win rate, and profit factor.
        """
        if not isinstance(
            strategy_result,
            dict,
        ):
            return 0.0

        statistics = (
            strategy_result.get(
                "statistics",
                {},
            )
        )

        if not isinstance(
            statistics,
            dict,
        ):
            return 0.0

        score = self._clamp(
            self._to_float(
                strategy_result.get(
                    "score",
                    0.0,
                )
            ),
            minimum=0.0,
            maximum=100.0,
        )

        historical_confidence = (
            self._clamp(
                self._to_float(
                    statistics.get(
                        "confidence_score",
                        0.0,
                    )
                ),
                minimum=0.0,
                maximum=1.0,
            )
            * 100.0
        )

        win_rate = self._clamp(
            self._to_float(
                statistics.get(
                    "win_rate",
                    0.0,
                )
            ),
            minimum=0.0,
            maximum=100.0,
        )

        normalized_profit_factor = (
            self._normalize_profit_factor(
                statistics.get(
                    "profit_factor",
                    0.0,
                )
            )
            / self.maximum_profit_factor
            * 100.0
        )

        decision_confidence = (
            score * 0.50
            + historical_confidence * 0.30
            + win_rate * 0.10
            + normalized_profit_factor * 0.10
        )

        return round(
            self._clamp(
                decision_confidence,
                minimum=0.0,
                maximum=100.0,
            ),
            2,
        )

    def _calculate_strategy_score(
        self,
        statistics: Dict[str, Any],
    ) -> float:
        """
        Convert strategy-performance metrics
        into a score between zero and 100.
        """
        if not isinstance(
            statistics,
            dict,
        ):
            return 0.0

        confidence_score = self._clamp(
            self._to_float(
                statistics.get(
                    "confidence_score",
                    0.0,
                )
            ),
            minimum=0.0,
            maximum=1.0,
        )

        win_rate = self._clamp(
            self._to_float(
                statistics.get(
                    "win_rate",
                    0.0,
                )
            ),
            minimum=0.0,
            maximum=100.0,
        )

        average_r = self._clamp(
            self._to_float(
                statistics.get(
                    "average_r",
                    0.0,
                )
            ),
            minimum=0.0,
            maximum=(
                self.maximum_average_r
            ),
        )

        expectancy = self._clamp(
            self._to_float(
                statistics.get(
                    "expectancy",
                    0.0,
                )
            ),
            minimum=0.0,
            maximum=(
                self.maximum_expectancy
            ),
        )

        profit_factor = (
            self._normalize_profit_factor(
                statistics.get(
                    "profit_factor",
                    0.0,
                )
            )
        )

        confidence_component = (
            confidence_score
            * self.confidence_weight
        )

        win_rate_component = (
            win_rate
            / 100.0
            * self.win_rate_weight
        )

        average_r_component = (
            average_r
            / self.maximum_average_r
            * self.average_r_weight
        )

        expectancy_component = (
            expectancy
            / self.maximum_expectancy
            * self.expectancy_weight
        )

        profit_factor_component = (
            profit_factor
            / self.maximum_profit_factor
            * self.profit_factor_weight
        )

        final_score = (
            confidence_component
            + win_rate_component
            + average_r_component
            + expectancy_component
            + profit_factor_component
        )

        return round(
            self._clamp(
                final_score,
                minimum=0.0,
                maximum=100.0,
            ),
            2,
        )

    def _normalize_profit_factor(
        self,
        value: Any,
    ) -> float:
        """
        Convert profit factor into a safe
        numeric value.

        Infinite profit factor is capped at the
        configured maximum.
        """
        if isinstance(
            value,
            str,
        ):
            normalized_value = (
                value.strip().upper()
            )

            if normalized_value in {
                "INFINITY",
                "INF",
            }:
                return (
                    self.maximum_profit_factor
                )

        profit_factor = self._to_float(
            value
        )

        return self._clamp(
            profit_factor,
            minimum=0.0,
            maximum=(
                self.maximum_profit_factor
            ),
        )

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(
            minimum,
            min(
                value,
                maximum,
            ),
        )

    @staticmethod
    def _to_float(
        value: Any,
    ) -> float:
        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0.0


if __name__ == "__main__":
    engine = RecommendationEngine()

    statistics = {
        "VWAP_PULLBACK": {
            "trades": 15,
            "sample_size": 15,
            "win_rate": 54.0,
            "expectancy": 80.0,
            "average_r": 1.1,
            "profit_factor": 1.8,
            "confidence_score": 0.45,
            "confidence_label": (
                "MEDIUM"
            ),
            "learning_active": False,
        },
        "EMA_PULLBACK": {
            "trades": 5,
            "sample_size": 5,
            "win_rate": 40.0,
            "expectancy": -20.0,
            "average_r": -0.2,
            "profit_factor": 0.8,
            "confidence_score": 0.25,
            "confidence_label": "LOW",
            "learning_active": False,
        },
        "ORB_BREAKOUT": {
            "trades": 80,
            "sample_size": 80,
            "win_rate": 68.0,
            "expectancy": 240.0,
            "average_r": 2.4,
            "profit_factor": 5.0,
            "confidence_score": 0.95,
            "confidence_label": "HIGH",
            "learning_active": True,
        },
    }

    result = engine.recommend(
        statistics
    )

    print(
        "\nRECOMMENDATION RESULT:"
    )

    print(
        result
    )

    print(
        "\nDECISION:"
    )

    print(
        result[
            "decision"
        ]
    )

    print(
        "\nDECISION CONFIDENCE:"
    )

    print(
        f"{result['decision_confidence']:.2f}%"
    )

    print(
        "\nBEST STRATEGY:"
    )

    best_strategy = result.get(
        "best_strategy"
    )

    if best_strategy is None:
        print(
            "No strategy available."
        )

    else:
        print(
            f"{best_strategy['strategy']} | "
            f"Score: "
            f"{best_strategy['score']} | "
            f"Rank: "
            f"{best_strategy['rank']}"
        )

    print(
        "\nREASONS:"
    )

    for reason in result.get(
        "reasons",
        [],
    ):
        print(
            f"- {reason}"
        )

    print(
        "\nRANKINGS:"
    )

    for strategy_result in result[
        "strategies"
    ]:
        print(
            f"#{strategy_result['rank']} | "
            f"{strategy_result['strategy']} | "
            f"Score: "
            f"{strategy_result['score']}"
        )
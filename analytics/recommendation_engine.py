"""
Recommendation Engine

Version 6.2.2

Uses MarketLearning statistics to score and
rank trading strategies.

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

Future versions will add:

- TAKE_TRADE / WATCH / SKIP decisions
- Minimum-confidence protection
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
                float(
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
            strategy_result["rank"] = (
                index
            )

        return ranked

    def recommend(
        self,
        strategy_statistics: Dict[
            str,
            Dict[str, Any],
        ],
    ) -> Dict[str, Any]:
        """
        Return ranked strategies and identify
        the highest-scoring strategy.

        Trade-decision logic will be added in
        the next version.
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

        return {
            "recommendation": (
                "NO_DECISION"
            ),
            "best_strategy": (
                best_strategy
            ),
            "strategies": ranked,
            "strategy_count": len(
                ranked
            ),
        }

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
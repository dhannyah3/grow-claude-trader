from typing import Any, Dict


class AdaptiveTradeFilter:
    """
    Filters proposed trades using historical performance data.
    """

    def __init__(
        self,
        minimum_confidence: int = 80,
        minimum_win_rate: float = 50.0,
        minimum_sample_size: int = 5,
        weak_market_multiplier: float = 0.5,
    ) -> None:
        self.minimum_confidence = minimum_confidence
        self.minimum_win_rate = minimum_win_rate
        self.minimum_sample_size = minimum_sample_size
        self.weak_market_multiplier = weak_market_multiplier

    def evaluate(
        self,
        strategy: str,
        confidence: int,
        market_condition: str,
        performance_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        reasons = []
        position_multiplier = 1.0

        if confidence < self.minimum_confidence:
            return {
                "take_trade": False,
                "position_multiplier": 0.0,
                "reasons": [
                    (
                        f"Confidence {confidence} is below "
                        f"the minimum of {self.minimum_confidence}."
                    )
                ],
            }

        reasons.append(
            (
                f"Confidence {confidence} meets the "
                f"minimum requirement."
            )
        )

        strategy_performance = performance_report.get(
            "strategy_performance",
            {},
        )

        strategy_stats = strategy_performance.get(strategy)

        if strategy_stats:
            strategy_trades = int(
                strategy_stats.get("trades", 0)
            )

            strategy_win_rate = float(
                strategy_stats.get("win_rate", 0.0)
            )

            if strategy_trades >= self.minimum_sample_size:
                if strategy_win_rate < self.minimum_win_rate:
                    return {
                        "take_trade": False,
                        "position_multiplier": 0.0,
                        "reasons": [
                            (
                                f"{strategy} has a "
                                f"{strategy_win_rate}% win rate "
                                f"across {strategy_trades} trades."
                            ),
                            (
                                f"The required win rate is "
                                f"{self.minimum_win_rate}%."
                            ),
                        ],
                    }

                reasons.append(
                    (
                        f"{strategy} has a "
                        f"{strategy_win_rate}% win rate "
                        f"across {strategy_trades} trades."
                    )
                )

            else:
                reasons.append(
                    (
                        f"{strategy} has only "
                        f"{strategy_trades} historical trades. "
                        f"More data is required before blocking it."
                    )
                )

        else:
            reasons.append(
                (
                    f"No historical data exists for "
                    f"{strategy}. The trade is allowed "
                    f"for data collection."
                )
            )

        market_performance = performance_report.get(
            "market_condition_performance",
            {},
        )

        market_stats = market_performance.get(
            market_condition
        )

        if market_stats:
            market_trades = int(
                market_stats.get("trades", 0)
            )

            market_total_pnl = float(
                market_stats.get("total_pnl", 0.0)
            )

            if (
                market_trades >= self.minimum_sample_size
                and market_total_pnl < 0
            ):
                position_multiplier *= (
                    self.weak_market_multiplier
                )

                reasons.append(
                    (
                        f"{market_condition} has produced "
                        f"₹{market_total_pnl:.2f} across "
                        f"{market_trades} trades. "
                        f"Position size reduced."
                    )
                )

            elif market_trades < self.minimum_sample_size:
                reasons.append(
                    (
                        f"{market_condition} has only "
                        f"{market_trades} historical trades. "
                        f"Normal position size is retained."
                    )
                )

            else:
                reasons.append(
                    (
                        f"{market_condition} historical "
                        f"performance supports normal sizing."
                    )
                )

        else:
            reasons.append(
                (
                    f"No historical market data exists for "
                    f"{market_condition}."
                )
            )

        return {
            "take_trade": True,
            "position_multiplier": round(
                position_multiplier,
                2,
            ),
            "reasons": reasons,
        }
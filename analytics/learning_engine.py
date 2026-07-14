from typing import Any, Dict

from analytics.performance_coach import PerformanceCoach


class LearningEngine:
    """
    Converts historical strategy performance into
    small, controlled score adjustments.
    """

    def __init__(
        self,
        journal_file: str = "logs/trade_journal.json",
        minimum_sample_size: int = 20,
        maximum_adjustment: int = 10,
    ) -> None:
        self.performance_coach = PerformanceCoach(
            journal_file=journal_file,
        )

        self.minimum_sample_size = int(
            minimum_sample_size
        )

        self.maximum_adjustment = int(
            maximum_adjustment
        )

    def get_strategy_adjustment(
        self,
        strategy: str,
    ) -> Dict[str, Any]:
        report = self.performance_coach.analyze()

        strategy_performance = report.get(
            "strategy_performance",
            {},
        )

        stats = strategy_performance.get(
            strategy,
            {},
        )

        trades = int(
            stats.get(
                "trades",
                0,
            )
            or 0
        )

        if trades < self.minimum_sample_size:
            return {
                "adjustment": 0,
                "active": False,
                "sample_size": trades,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "reason": (
                    "Historical learning inactive: "
                    f"{trades}/"
                    f"{self.minimum_sample_size} "
                    "required trades."
                ),
            }

        win_rate = float(
            stats.get(
                "win_rate",
                0.0,
            )
            or 0.0
        )

        profit_factor_raw = stats.get(
            "profit_factor",
            0.0,
        )

        if profit_factor_raw == "Infinity":
            profit_factor = 3.0

        else:
            try:
                profit_factor = float(
                    profit_factor_raw
                )

            except (
                TypeError,
                ValueError,
            ):
                profit_factor = 0.0

        adjustment = 0

        if win_rate >= 60:
            adjustment += 6

        elif win_rate >= 55:
            adjustment += 3

        elif win_rate < 40:
            adjustment -= 6

        elif win_rate < 45:
            adjustment -= 3

        if profit_factor >= 1.5:
            adjustment += 4

        elif profit_factor >= 1.2:
            adjustment += 2

        elif profit_factor < 0.8:
            adjustment -= 4

        elif profit_factor < 1.0:
            adjustment -= 2

        adjustment = max(
            -self.maximum_adjustment,
            min(
                adjustment,
                self.maximum_adjustment,
            ),
        )

        return {
            "adjustment": adjustment,
            "active": True,
            "sample_size": trades,
            "win_rate": round(
                win_rate,
                2,
            ),
            "profit_factor": round(
                profit_factor,
                2,
            ),
            "reason": (
                f"Historical adjustment {adjustment:+d} "
                f"from {trades} trades, "
                f"{win_rate:.1f}% win rate, "
                f"{profit_factor:.2f} profit factor."
            ),
        }


if __name__ == "__main__":
    engine = LearningEngine()

    print(
        engine.get_strategy_adjustment(
            "ORB_BREAKOUT"
        )
    )

    print(
        engine.get_strategy_adjustment(
            "VWAP_PULLBACK"
        )
    )
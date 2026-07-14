from typing import Any, Dict, Optional

from analytics.performance_coach import PerformanceCoach


class LearningEngine:
    """
    Converts historical performance into small,
    controlled strategy-score adjustments.

    Learning priority:
    1. Strategy + market regime
    2. Overall strategy performance
    3. No adjustment
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
        regime: Optional[str] = None,
    ) -> Dict[str, Any]:
        report = self.performance_coach.analyze()

        strategy_performance = report.get(
            "strategy_performance",
            {},
        )

        strategy_regime_performance = report.get(
            "strategy_regime_performance",
            {},
        )

        normalized_strategy = str(
            strategy
        ).upper()

        normalized_regime = str(
            regime or "UNKNOWN"
        ).upper()

        regime_key = (
            f"{normalized_strategy}|"
            f"{normalized_regime}"
        )

        regime_stats = (
            strategy_regime_performance.get(
                regime_key,
                {},
            )
        )

        regime_trades = int(
            regime_stats.get(
                "trades",
                0,
            )
            or 0
        )

        if regime_trades >= self.minimum_sample_size:
            return self._build_adjustment_result(
                stats=regime_stats,
                source="STRATEGY_REGIME",
                label=regime_key,
            )

        strategy_stats = strategy_performance.get(
            normalized_strategy,
            {},
        )

        strategy_trades = int(
            strategy_stats.get(
                "trades",
                0,
            )
            or 0
        )

        if strategy_trades >= self.minimum_sample_size:
            result = self._build_adjustment_result(
                stats=strategy_stats,
                source="OVERALL_STRATEGY",
                label=normalized_strategy,
            )

            result["fallback_used"] = True
            result["regime_sample_size"] = (
                regime_trades
            )
            result["reason"] = (
                f"Regime sample {regime_trades}/"
                f"{self.minimum_sample_size} was too small. "
                f"{result['reason']}"
            )

            return result

        return {
            "adjustment": 0,
            "active": False,
            "source": "NONE",
            "sample_size": max(
                regime_trades,
                strategy_trades,
            ),
            "regime_sample_size": regime_trades,
            "strategy_sample_size": strategy_trades,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "fallback_used": False,
            "reason": (
                "Historical learning inactive. "
                f"Regime sample: {regime_trades}/"
                f"{self.minimum_sample_size}; "
                f"strategy sample: {strategy_trades}/"
                f"{self.minimum_sample_size}."
            ),
        }

    def _build_adjustment_result(
        self,
        stats: Dict[str, Any],
        source: str,
        label: str,
    ) -> Dict[str, Any]:
        trades = int(
            stats.get(
                "trades",
                0,
            )
            or 0
        )

        win_rate = float(
            stats.get(
                "win_rate",
                0.0,
            )
            or 0.0
        )

        profit_factor = self._to_profit_factor(
            stats.get(
                "profit_factor",
                0.0,
            )
        )

        adjustment = self._calculate_adjustment(
            win_rate=win_rate,
            profit_factor=profit_factor,
        )

        return {
            "adjustment": adjustment,
            "active": True,
            "source": source,
            "label": label,
            "sample_size": trades,
            "win_rate": round(
                win_rate,
                2,
            ),
            "profit_factor": round(
                profit_factor,
                2,
            ),
            "fallback_used": False,
            "reason": (
                f"{source} adjustment "
                f"{adjustment:+d} for {label} "
                f"from {trades} trades, "
                f"{win_rate:.1f}% win rate, "
                f"{profit_factor:.2f} "
                "profit factor."
            ),
        }

    def _calculate_adjustment(
        self,
        win_rate: float,
        profit_factor: float,
    ) -> int:
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

        return max(
            -self.maximum_adjustment,
            min(
                adjustment,
                self.maximum_adjustment,
            ),
        )

    @staticmethod
    def _to_profit_factor(
        value: Any,
    ) -> float:
        if value == "Infinity":
            return 3.0

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
    engine = LearningEngine()

    print(
        engine.get_strategy_adjustment(
            strategy="ORB_BREAKOUT",
            regime="TRENDING",
        )
    )

    print(
        engine.get_strategy_adjustment(
            strategy="VWAP_PULLBACK",
            regime="RANGE_BOUND",
        )
    )
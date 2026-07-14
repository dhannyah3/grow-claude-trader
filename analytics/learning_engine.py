from typing import Any, Dict, Optional

from analytics.performance_coach import PerformanceCoach


class LearningEngine:
    """
    Converts historical performance into small,
    controlled strategy-score adjustments.

    Learning priority:
    1. Strategy + market regime
    2. Strategy + volatility
    3. Strategy + gap type
    4. Overall strategy performance
    5. No adjustment
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
        volatility: Optional[str] = None,
        gap: Optional[str] = None,
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

        strategy_volatility_performance = report.get(
            "strategy_volatility_performance",
            {},
        )

        strategy_gap_performance = report.get(
            "strategy_gap_performance",
            {},
        )

        normalized_strategy = str(
            strategy
        ).upper()

        normalized_regime = str(
            regime or "UNKNOWN"
        ).upper()

        normalized_volatility = str(
            volatility or "UNKNOWN"
        ).upper()

        normalized_gap = str(
            gap or "UNKNOWN"
        ).upper()

        regime_key = (
            f"{normalized_strategy}|"
            f"{normalized_regime}"
        )

        volatility_key = (
            f"{normalized_strategy}|"
            f"{normalized_volatility}"
        )

        gap_key = (
            f"{normalized_strategy}|"
            f"{normalized_gap}"
        )

        regime_stats = (
            strategy_regime_performance.get(
                regime_key,
                {},
            )
        )

        volatility_stats = (
            strategy_volatility_performance.get(
                volatility_key,
                {},
            )
        )

        gap_stats = (
            strategy_gap_performance.get(
                gap_key,
                {},
            )
        )

        strategy_stats = strategy_performance.get(
            normalized_strategy,
            {},
        )

        regime_trades = self._get_trades(
            regime_stats
        )

        volatility_trades = self._get_trades(
            volatility_stats
        )

        gap_trades = self._get_trades(
            gap_stats
        )

        strategy_trades = self._get_trades(
            strategy_stats
        )

        candidates = [
            (
                "STRATEGY_REGIME",
                regime_key,
                regime_stats,
                regime_trades,
            ),
            (
                "STRATEGY_VOLATILITY",
                volatility_key,
                volatility_stats,
                volatility_trades,
            ),
            (
                "STRATEGY_GAP",
                gap_key,
                gap_stats,
                gap_trades,
            ),
            (
                "OVERALL_STRATEGY",
                normalized_strategy,
                strategy_stats,
                strategy_trades,
            ),
        ]

        for index, (
            source,
            label,
            stats,
            trades,
        ) in enumerate(candidates):
            if trades < self.minimum_sample_size:
                continue

            result = self._build_adjustment_result(
                stats=stats,
                source=source,
                label=label,
            )

            result["fallback_used"] = (
                index > 0
            )

            result["regime_sample_size"] = (
                regime_trades
            )

            result["volatility_sample_size"] = (
                volatility_trades
            )

            result["gap_sample_size"] = (
                gap_trades
            )

            result["strategy_sample_size"] = (
                strategy_trades
            )

            if index > 0:
                result["reason"] = (
                    "Higher-priority context samples "
                    "were too small. "
                    f"{result['reason']}"
                )

            return result

        return {
            "adjustment": 0,
            "active": False,
            "source": "NONE",
            "sample_size": max(
                regime_trades,
                volatility_trades,
                gap_trades,
                strategy_trades,
            ),
            "regime_sample_size": regime_trades,
            "volatility_sample_size": (
                volatility_trades
            ),
            "gap_sample_size": gap_trades,
            "strategy_sample_size": (
                strategy_trades
            ),
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "fallback_used": False,
            "reason": (
                "Historical learning inactive. "
                f"Regime: {regime_trades}/"
                f"{self.minimum_sample_size}; "
                f"volatility: {volatility_trades}/"
                f"{self.minimum_sample_size}; "
                f"gap: {gap_trades}/"
                f"{self.minimum_sample_size}; "
                f"strategy: {strategy_trades}/"
                f"{self.minimum_sample_size}."
            ),
        }

    @staticmethod
    def _get_trades(
        stats: Dict[str, Any],
    ) -> int:
        return int(
            stats.get(
                "trades",
                0,
            )
            or 0
        )

    def _build_adjustment_result(
        self,
        stats: Dict[str, Any],
        source: str,
        label: str,
    ) -> Dict[str, Any]:
        trades = self._get_trades(
            stats
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
            volatility="MEDIUM",
            gap="NO_GAP",
        )
    )

    print(
        engine.get_strategy_adjustment(
            strategy="VWAP_PULLBACK",
            regime="RANGE_BOUND",
            volatility="LOW",
            gap="NO_GAP",
        )
    )
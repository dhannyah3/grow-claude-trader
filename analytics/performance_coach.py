import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


class PerformanceCoach:
    def __init__(
        self,
        journal_file: str = "logs/trade_journal.json",
    ) -> None:
        self.journal_file = Path(journal_file)

    def load_entries(self) -> List[Dict[str, Any]]:
        if (
            not self.journal_file.exists()
            or self.journal_file.stat().st_size == 0
        ):
            return []

        try:
            raw_text = self.journal_file.read_text(
                encoding="utf-8",
            ).strip()

            if not raw_text:
                return []

            data = json.loads(raw_text)

            if not isinstance(data, list):
                return []

            return data

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            print(
                f"Could not load trade journal: {error}"
            )
            return []

    def analyze(self) -> Dict[str, Any]:
        entries = self.load_entries()

        if not entries:
            return {
                "total_trades": 0,
                "strategy_performance": {},
                "confidence_performance": {},
                "market_condition_performance": {},
                "strategy_regime_performance": {},
                "volatility_performance": {},
                "strategy_volatility_performance": {},
                "gap_performance": {},
                "strategy_gap_performance": {},
                "market_quality_performance": {},
                "brain_confidence_performance": {},
                "best_strategy": None,
                "worst_strategy": None,
                "recommendations": [
                    "Not enough journal data yet."
                ],
            }

        strategy_stats = self._create_stats_group()
        confidence_stats = self._create_stats_group()
        market_stats = self._create_stats_group()
        strategy_regime_stats = self._create_stats_group()
        volatility_stats = self._create_stats_group()
        strategy_volatility_stats = (
            self._create_stats_group()
        )
        gap_stats = self._create_stats_group()
        strategy_gap_stats = self._create_stats_group()
        market_quality_stats = self._create_stats_group()
        brain_confidence_stats = (
            self._create_stats_group()
        )

        for entry in entries:
            pnl = float(
                entry.get(
                    "pnl",
                    0.0,
                )
                or 0.0
            )

            result = str(
                entry.get(
                    "result",
                    "",
                )
            ).upper()

            strategy = str(
                entry.get(
                    "strategy",
                    "UNKNOWN",
                )
            ).upper()

            market_condition = str(
                entry.get(
                    "market_condition",
                    "UNKNOWN",
                )
            ).upper()

            claude_data = entry.get(
                "claude",
                {},
            )

            if not isinstance(
                claude_data,
                dict,
            ):
                claude_data = {}

            market_regime = entry.get(
                "market_regime",
                {},
            )

            if not isinstance(
                market_regime,
                dict,
            ):
                market_regime = {}

            volatility = str(
                market_regime.get(
                    "volatility",
                    "UNKNOWN",
                )
            ).upper()

            gap = str(
                market_regime.get(
                    "gap",
                    "UNKNOWN",
                )
            ).upper()

            strategy_regime_key = (
                f"{strategy}|"
                f"{market_condition}"
            )

            strategy_volatility_key = (
                f"{strategy}|"
                f"{volatility}"
            )

            strategy_gap_key = (
                f"{strategy}|"
                f"{gap}"
            )

            confidence = int(
                claude_data.get(
                    "confidence",
                    0,
                )
                or 0
            )

            confidence_bucket = (
                "90-100"
                if confidence >= 90
                else "80-89"
                if confidence >= 80
                else "70-79"
                if confidence >= 70
                else "Below 70"
            )

            market_quality = int(
                entry.get(
                    "market_quality",
                    0,
                )
                or 0
            )

            if market_quality >= 80:
                quality_bucket = "80-100"

            elif market_quality >= 60:
                quality_bucket = "60-79"

            elif market_quality >= 40:
                quality_bucket = "40-59"

            else:
                quality_bucket = "0-39"

            brain_confidence = int(
                entry.get(
                    "brain_confidence",
                    0,
                )
                or 0
            )

            brain_bucket = (
                "90-100"
                if brain_confidence >= 90
                else "80-89"
                if brain_confidence >= 80
                else "70-79"
                if brain_confidence >= 70
                else "Below 70"
            )

            self._update_group(
                strategy_stats[strategy],
                result,
                pnl,
            )

            self._update_group(
                confidence_stats[
                    confidence_bucket
                ],
                result,
                pnl,
            )

            self._update_group(
                market_stats[
                    market_condition
                ],
                result,
                pnl,
            )

            self._update_group(
                strategy_regime_stats[
                    strategy_regime_key
                ],
                result,
                pnl,
            )

            self._update_group(
                volatility_stats[
                    volatility
                ],
                result,
                pnl,
            )

            self._update_group(
                strategy_volatility_stats[
                    strategy_volatility_key
                ],
                result,
                pnl,
            )

            self._update_group(
                gap_stats[
                    gap
                ],
                result,
                pnl,
            )

            self._update_group(
                strategy_gap_stats[
                    strategy_gap_key
                ],
                result,
                pnl,
            )

            self._update_group(
                market_quality_stats[
                    quality_bucket
                ],
                result,
                pnl,
            )

            self._update_group(
                brain_confidence_stats[
                    brain_bucket
                ],
                result,
                pnl,
            )

        strategy_performance = (
            self._finalize_groups(
                strategy_stats
            )
        )

        confidence_performance = (
            self._finalize_groups(
                confidence_stats
            )
        )

        market_condition_performance = (
            self._finalize_groups(
                market_stats
            )
        )

        strategy_regime_performance = (
            self._finalize_groups(
                strategy_regime_stats
            )
        )

        volatility_performance = (
            self._finalize_groups(
                volatility_stats
            )
        )

        strategy_volatility_performance = (
            self._finalize_groups(
                strategy_volatility_stats
            )
        )

        gap_performance = (
            self._finalize_groups(
                gap_stats
            )
        )

        strategy_gap_performance = (
            self._finalize_groups(
                strategy_gap_stats
            )
        )

        market_quality_performance = (
            self._finalize_groups(
                market_quality_stats
            )
        )

        brain_confidence_performance = (
            self._finalize_groups(
                brain_confidence_stats
            )
        )

        best_strategy = self._best_group(
            strategy_performance
        )

        worst_strategy = self._worst_group(
            strategy_performance
        )

        recommendations = self._build_recommendations(
            strategy_performance=strategy_performance,
            confidence_performance=confidence_performance,
            market_condition_performance=(
                market_condition_performance
            ),
        )

        return {
            "total_trades": len(entries),
            "strategy_performance": (
                strategy_performance
            ),
            "confidence_performance": (
                confidence_performance
            ),
            "market_condition_performance": (
                market_condition_performance
            ),
            "strategy_regime_performance": (
                strategy_regime_performance
            ),
            "volatility_performance": (
                volatility_performance
            ),
            "strategy_volatility_performance": (
                strategy_volatility_performance
            ),
            "gap_performance": (
                gap_performance
            ),
            "strategy_gap_performance": (
                strategy_gap_performance
            ),
            "market_quality_performance": (
                market_quality_performance
            ),
            "brain_confidence_performance": (
                brain_confidence_performance
            ),
            "best_strategy": best_strategy,
            "worst_strategy": worst_strategy,
            "recommendations": recommendations,
        }

    @staticmethod
    def _create_stats_group():
        return defaultdict(
            lambda: {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "total_pnl": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
            }
        )

    @staticmethod
    def _update_group(
        group: Dict[str, float],
        result: str,
        pnl: float,
    ) -> None:
        group["trades"] += 1
        group["total_pnl"] += pnl

        if result == "WIN":
            group["wins"] += 1
            group["gross_profit"] += pnl

        elif result == "LOSS":
            group["losses"] += 1
            group["gross_loss"] += abs(
                pnl
            )

        else:
            group["breakeven"] += 1

    @staticmethod
    def _finalize_groups(
        groups: Dict[
            str,
            Dict[str, float],
        ],
    ) -> Dict[str, Dict[str, Any]]:
        finalized: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for name, stats in groups.items():
            trades = int(
                stats["trades"]
            )

            wins = int(
                stats["wins"]
            )

            losses = int(
                stats["losses"]
            )

            breakeven = int(
                stats["breakeven"]
            )

            total_pnl = float(
                stats["total_pnl"]
            )

            gross_profit = float(
                stats["gross_profit"]
            )

            gross_loss = float(
                stats["gross_loss"]
            )

            win_rate = (
                wins / trades * 100
                if trades > 0
                else 0.0
            )

            average_pnl = (
                total_pnl / trades
                if trades > 0
                else 0.0
            )

            average_win = (
                gross_profit / wins
                if wins > 0
                else 0.0
            )

            average_loss = (
                gross_loss / losses
                if losses > 0
                else 0.0
            )

            if gross_loss > 0:
                profit_factor = (
                    gross_profit
                    / gross_loss
                )

            elif gross_profit > 0:
                profit_factor = float(
                    "inf"
                )

            else:
                profit_factor = 0.0

            finalized[name] = {
                "trades": trades,
                "wins": wins,
                "losses": losses,
                "breakeven": breakeven,
                "win_rate": round(
                    win_rate,
                    2,
                ),
                "total_pnl": round(
                    total_pnl,
                    2,
                ),
                "gross_profit": round(
                    gross_profit,
                    2,
                ),
                "gross_loss": round(
                    gross_loss,
                    2,
                ),
                "average_pnl": round(
                    average_pnl,
                    2,
                ),
                "average_win": round(
                    average_win,
                    2,
                ),
                "average_loss": round(
                    average_loss,
                    2,
                ),
                "profit_factor": (
                    round(
                        profit_factor,
                        2,
                    )
                    if profit_factor
                    != float("inf")
                    else "Infinity"
                ),
                "expectancy": round(
                    average_pnl,
                    2,
                ),
            }

        return finalized

    @staticmethod
    def _best_group(
        groups: Dict[
            str,
            Dict[str, Any],
        ],
    ) -> str:
        if not groups:
            return ""

        return max(
            groups,
            key=lambda name: groups[name][
                "total_pnl"
            ],
        )

    @staticmethod
    def _worst_group(
        groups: Dict[
            str,
            Dict[str, Any],
        ],
    ) -> str:
        if not groups:
            return ""

        return min(
            groups,
            key=lambda name: groups[name][
                "total_pnl"
            ],
        )

    def _build_recommendations(
        self,
        strategy_performance,
        confidence_performance,
        market_condition_performance,
    ):
        recommendations = []

        if strategy_performance:
            best = max(
                strategy_performance.items(),
                key=lambda item: item[1][
                    "win_rate"
                ],
            )

            recommendations.append(
                f"Best strategy: {best[0]} "
                f"({best[1]['win_rate']}% win rate)."
            )

            worst = min(
                strategy_performance.items(),
                key=lambda item: item[1][
                    "win_rate"
                ],
            )

            if worst[1]["trades"] >= 3:
                recommendations.append(
                    f"Review {worst[0]} "
                    f"({worst[1]['win_rate']}% win rate)."
                )

        if confidence_performance:
            best_bucket = max(
                confidence_performance.items(),
                key=lambda item: item[1][
                    "win_rate"
                ],
            )

            recommendations.append(
                "Highest-performing confidence "
                f"range: {best_bucket[0]} "
                f"({best_bucket[1]['win_rate']}%)."
            )

        if market_condition_performance:
            best_market = max(
                market_condition_performance.items(),
                key=lambda item: item[1][
                    "win_rate"
                ],
            )

            recommendations.append(
                "Best market condition: "
                f"{best_market[0]}."
            )

        if not recommendations:
            recommendations.append(
                "Collect more journal data."
            )

        return recommendations


if __name__ == "__main__":
    coach = PerformanceCoach()

    report = coach.analyze()

    print(
        "\n===== AI PERFORMANCE COACH =====\n"
    )

    print(
        f"Total Trades: "
        f"{report['total_trades']}"
    )

    print(
        f"Best Strategy: "
        f"{report['best_strategy']}"
    )

    print(
        f"Worst Strategy: "
        f"{report['worst_strategy']}"
    )

    print("\nStrategy Performance:")
    print(
        report["strategy_performance"]
    )

    print("\nConfidence Performance:")
    print(
        report["confidence_performance"]
    )

    print("\nMarket Condition Performance:")
    print(
        report[
            "market_condition_performance"
        ]
    )

    print("\nStrategy + Regime Performance:")
    print(
        report[
            "strategy_regime_performance"
        ]
    )

    print("\nVolatility Performance:")
    print(
        report[
            "volatility_performance"
        ]
    )

    print("\nStrategy + Volatility Performance:")
    print(
        report[
            "strategy_volatility_performance"
        ]
    )

    print("\nGap Performance:")
    print(
        report[
            "gap_performance"
        ]
    )

    print("\nStrategy + Gap Performance:")
    print(
        report[
            "strategy_gap_performance"
        ]
    )

    print("\nMarket Quality Performance:")
    print(
        report[
            "market_quality_performance"
        ]
    )

    print("\nMarketBrain Confidence Performance:")
    print(
        report[
            "brain_confidence_performance"
        ]
    )

    print("\nRecommendations:")

    for recommendation in report[
        "recommendations"
    ]:
        print(
            f"- {recommendation}"
        )
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
                "best_strategy": None,
                "worst_strategy": None,
                "recommendations": [
                    "Not enough journal data yet."
                ],
            }

        strategy_stats: Dict[str, Dict[str, float]] = (
            defaultdict(
                lambda: {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0.0,
                }
            )
        )

        confidence_stats: Dict[str, Dict[str, float]] = (
            defaultdict(
                lambda: {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0.0,
                }
            )
        )

        market_stats: Dict[str, Dict[str, float]] = (
            defaultdict(
                lambda: {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "total_pnl": 0.0,
                }
            )
        )

        for entry in entries:
            pnl = float(
                entry.get("pnl", 0.0)
            )

            result = str(
                entry.get("result", "")
            )

            strategy = str(
                entry.get(
                    "strategy",
                    "UNKNOWN",
                )
            )

            market_condition = str(
                entry.get(
                    "market_condition",
                    "UNKNOWN",
                )
            )

            claude_data = entry.get(
                "claude",
                {},
            )

            confidence = int(
                claude_data.get(
                    "confidence",
                    0,
                )
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
            "best_strategy": best_strategy,
            "worst_strategy": worst_strategy,
            "recommendations": recommendations,
        }

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
        elif result == "LOSS":
            group["losses"] += 1

    @staticmethod
    def _finalize_groups(
        groups: Dict[
            str,
            Dict[str, float],
        ],
    ) -> Dict[str, Dict[str, float]]:
        finalized: Dict[
            str,
            Dict[str, float],
        ] = {}

        for name, stats in groups.items():
            trades = int(stats["trades"])
            wins = int(stats["wins"])
            losses = int(stats["losses"])
            total_pnl = float(
                stats["total_pnl"]
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

            finalized[name] = {
                "trades": trades,
                "wins": wins,
                "losses": losses,
                "win_rate": round(
                    win_rate,
                    2,
                ),
                "total_pnl": round(
                    total_pnl,
                    2,
                ),
                "average_pnl": round(
                    average_pnl,
                    2,
                ),
            }

        return finalized

    @staticmethod
    def _best_group(
        groups: Dict[
            str,
            Dict[str, float],
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
            Dict[str, float],
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

        # -------------------------
        # Best Strategy
        # -------------------------

        if strategy_performance:

            best = max(
                strategy_performance.items(),
                key=lambda x: x[1]["win_rate"],
            )

            recommendations.append(
                f"Best strategy: {best[0]} "
                f"({best[1]['win_rate']}% win rate)."
            )

            worst = min(
                strategy_performance.items(),
                key=lambda x: x[1]["win_rate"],
            )

            if worst[1]["trades"] >= 3:
                recommendations.append(
                    f"Review {worst[0]} "
                    f"({worst[1]['win_rate']}% win rate)."
                )

        # -------------------------
        # Confidence
        # -------------------------

        if confidence_performance:

            best_bucket = max(
                confidence_performance.items(),
                key=lambda x: x[1]["win_rate"],
            )

            recommendations.append(
                f"Highest-performing confidence range: "
                f"{best_bucket[0]} "
                f"({best_bucket[1]['win_rate']}%)."
            )

        # -------------------------
        # Market Condition
        # -------------------------

        if market_condition_performance:

            best_market = max(
                market_condition_performance.items(),
                key=lambda x: x[1]["win_rate"],
            )

            recommendations.append(
                f"Best market condition: "
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

    print("\n===== AI PERFORMANCE COACH =====\n")

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

    print("\nRecommendations:")

    for recommendation in report[
        "recommendations"
    ]:
        print(f"- {recommendation}")
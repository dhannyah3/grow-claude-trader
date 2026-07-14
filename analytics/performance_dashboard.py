from typing import Any, Dict

from analytics.performance_coach import PerformanceCoach


class PerformanceDashboard:
    def __init__(
        self,
        journal_file: str = "logs/trade_journal.json",
    ) -> None:
        self.coach = PerformanceCoach(
            journal_file=journal_file,
        )

    def display(self) -> None:
        report = self.coach.analyze()

        print(
            "\n========================================="
        )
        print(
            "        AI PERFORMANCE DASHBOARD"
        )
        print(
            "=========================================\n"
        )

        self._display_overall(report)
        self._display_best_strategy(report)
        self._display_best_group(
            title="BEST MARKET CONDITION",
            groups=report.get(
                "market_condition_performance",
                {},
            ),
        )
        self._display_best_group(
            title="BEST CLAUDE CONFIDENCE",
            groups=report.get(
                "confidence_performance",
                {},
            ),
        )
        self._display_best_group(
            title="BEST MARKETBRAIN CONFIDENCE",
            groups=report.get(
                "brain_confidence_performance",
                {},
            ),
        )
        self._display_best_group(
            title="BEST MARKET QUALITY",
            groups=report.get(
                "market_quality_performance",
                {},
            ),
        )
        self._display_best_group(
            title="BEST VOLATILITY",
            groups=report.get(
                "volatility_performance",
                {},
            ),
        )
        self._display_best_group(
            title="BEST GAP TYPE",
            groups=report.get(
                "gap_performance",
                {},
            ),
        )
        self._display_recommendations(report)

    def _display_overall(
        self,
        report: Dict[str, Any],
    ) -> None:
        strategy_performance = report.get(
            "strategy_performance",
            {},
        )

        total_trades = int(
            report.get(
                "total_trades",
                0,
            )
        )

        total_pnl = sum(
            float(
                stats.get(
                    "total_pnl",
                    0.0,
                )
            )
            for stats in strategy_performance.values()
        )

        total_wins = sum(
            int(
                stats.get(
                    "wins",
                    0,
                )
            )
            for stats in strategy_performance.values()
        )

        win_rate = (
            total_wins / total_trades * 100
            if total_trades > 0
            else 0.0
        )

        gross_profit = sum(
            float(
                stats.get(
                    "gross_profit",
                    0.0,
                )
            )
            for stats in strategy_performance.values()
        )

        gross_loss = sum(
            float(
                stats.get(
                    "gross_loss",
                    0.0,
                )
            )
            for stats in strategy_performance.values()
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf")
            if gross_profit > 0
            else 0.0
        )

        expectancy = (
            total_pnl / total_trades
            if total_trades > 0
            else 0.0
        )

        print("OVERALL")
        print("-----------------------------------------")
        print(
            f"Total Trades          : {total_trades}"
        )
        print(
            f"Win Rate              : {win_rate:.2f}%"
        )
        print(
            f"Net P&L               : ₹{total_pnl:.2f}"
        )
        print(
            "Profit Factor         : "
            f"{self._format_profit_factor(profit_factor)}"
        )
        print(
            f"Expectancy            : ₹{expectancy:.2f}"
        )
        print()

    def _display_best_strategy(
        self,
        report: Dict[str, Any],
    ) -> None:
        groups = report.get(
            "strategy_performance",
            {},
        )

        self._display_best_group(
            title="BEST STRATEGY",
            groups=groups,
        )

    @staticmethod
    def _best_group(
        groups: Dict[str, Dict[str, Any]],
    ):
        if not groups:
            return None

        return max(
            groups.items(),
            key=lambda item: (
                float(
                    item[1].get(
                        "total_pnl",
                        0.0,
                    )
                ),
                float(
                    item[1].get(
                        "win_rate",
                        0.0,
                    )
                ),
            ),
        )

    def _display_best_group(
        self,
        title: str,
        groups: Dict[str, Dict[str, Any]],
    ) -> None:
        print(title)
        print("-----------------------------------------")

        best = self._best_group(groups)

        if best is None:
            print("Not enough data.")
            print()
            return

        name, stats = best

        print(name)
        print(
            f"Trades               : "
            f"{stats.get('trades', 0)}"
        )
        print(
            f"Win Rate             : "
            f"{stats.get('win_rate', 0.0)}%"
        )
        print(
            f"Net P&L              : "
            f"₹{stats.get('total_pnl', 0.0)}"
        )
        print(
            f"Profit Factor        : "
            f"{stats.get('profit_factor', 0.0)}"
        )
        print()

    @staticmethod
    def _format_profit_factor(
        value: float,
    ) -> str:
        if value == float("inf"):
            return "Infinity"

        return f"{value:.2f}"

    @staticmethod
    def _display_recommendations(
        report: Dict[str, Any],
    ) -> None:
        print("RECOMMENDATIONS")
        print("-----------------------------------------")

        recommendations = report.get(
            "recommendations",
            [],
        )

        if not recommendations:
            print("- Collect more journal data.")
            return

        for recommendation in recommendations:
            print(f"- {recommendation}")


if __name__ == "__main__":
    dashboard = PerformanceDashboard()
    dashboard.display()
    
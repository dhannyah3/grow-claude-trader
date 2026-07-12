import csv
from pathlib import Path
from typing import Any, Dict, List


class PerformanceAnalyzer:
    def __init__(
        self,
        trade_log: str = "logs/paper_trades.csv",
    ) -> None:
        self.trade_log = Path(trade_log)

    def load_trades(self) -> List[Dict[str, Any]]:
        if (
            not self.trade_log.exists()
            or self.trade_log.stat().st_size == 0
        ):
            return []

        trades: List[Dict[str, Any]] = []

        try:
            with self.trade_log.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as file:
                reader = csv.DictReader(file)

                for row in reader:
                    if not row.get("symbol"):
                        continue

                    try:
                        trades.append(
                            {
                                "symbol": row["symbol"],
                                "quantity": int(
                                    float(row["quantity"])
                                ),
                                "entry_price": float(
                                    row["entry_price"]
                                ),
                                "exit_price": float(
                                    row["exit_price"]
                                ),
                                "pnl": float(row["pnl"]),
                                "exit_reason": row.get(
                                    "exit_reason",
                                    "",
                                ),
                            }
                        )

                    except (
                        KeyError,
                        TypeError,
                        ValueError,
                    ):
                        continue

        except OSError as error:
            print(
                f"Could not read trade log: {error}"
            )
            return []

        return trades

    def calculate_metrics(self) -> Dict[str, Any]:
        trades = self.load_trades()

        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "average_win": 0.0,
                "average_loss": 0.0,
                "profit_factor": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
            }

        pnl_values = [
            trade["pnl"]
            for trade in trades
        ]

        wins = [
            pnl
            for pnl in pnl_values
            if pnl > 0
        ]

        losses = [
            pnl
            for pnl in pnl_values
            if pnl < 0
        ]

        total_trades = len(trades)
        winning_trades = len(wins)
        losing_trades = len(losses)

        total_pnl = sum(pnl_values)

        win_rate = (
            winning_trades
            / total_trades
            * 100
        )

        average_win = (
            sum(wins) / len(wins)
            if wins
            else 0.0
        )

        average_loss = (
            sum(losses) / len(losses)
            if losses
            else 0.0
        )

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0.0
        )

        largest_win = (
            max(wins)
            if wins
            else 0.0
        )

        largest_loss = (
            min(losses)
            if losses
            else 0.0
        )

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "average_win": round(
                average_win,
                2,
            ),
            "average_loss": round(
                average_loss,
                2,
            ),
            "profit_factor": round(
                profit_factor,
                2,
            ),
            "largest_win": round(
                largest_win,
                2,
            ),
            "largest_loss": round(
                largest_loss,
                2,
            ),
        }


if __name__ == "__main__":
    analyzer = PerformanceAnalyzer()

    metrics = analyzer.calculate_metrics()

    print("\n===== PERFORMANCE SUMMARY =====\n")

    for key, value in metrics.items():
        print(f"{key}: {value}")
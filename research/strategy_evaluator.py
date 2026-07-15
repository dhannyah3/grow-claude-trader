"""
Strategy evaluator for historical research.

Runs a simple long-only ORB strategy over a prepared
feature dataset and calculates core performance metrics.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from research.dataset_builder import DatasetBuilder


class StrategyEvaluator:
    def __init__(
        self,
        initial_balance: float = 100000.0,
    ) -> None:
        self.initial_balance = float(initial_balance)

    def evaluate_orb(
        self,
        dataframe: pd.DataFrame,
        opening_range_minutes: int = 15,
        stop_atr_multiplier: float = 1.0,
        target_atr_multiplier: float = 2.0,
        minimum_rsi: float = 50.0,
        maximum_rsi: float = 70.0,
        minimum_volume_ratio: float = 1.0,
    ) -> Dict[str, Any]:
        if dataframe.empty:
            return self._empty_result()

        required_columns = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "atr",
            "rsi",
            "ema_20",
            "ema_50",
            "vwap",
            "volume_ratio",
        }

        missing = required_columns.difference(dataframe.columns)

        if missing:
            raise ValueError(
                "Dataset is missing columns: "
                + ", ".join(sorted(missing))
            )

        df = dataframe.copy()
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "atr",
            "rsi",
            "ema_20",
            "ema_50",
            "vwap",
            "volume_ratio",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df = df.dropna(
            subset=["timestamp", *numeric_columns]
        )

        df = df.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        df["trade_date"] = df["timestamp"].dt.date

        trades: List[Dict[str, Any]] = []

        for trade_date, day_data in df.groupby(
            "trade_date"
        ):
            day_data = (
                day_data.sort_values("timestamp")
                .reset_index(drop=True)
            )

            if day_data.empty:
                continue

            market_open = day_data.iloc[0]["timestamp"]
            opening_range_end = (
                market_open
                + pd.Timedelta(
                    minutes=opening_range_minutes
                )
            )

            opening_data = day_data[
                day_data["timestamp"]
                < opening_range_end
            ]

            trading_data = day_data[
                day_data["timestamp"]
                >= opening_range_end
            ]

            if (
                opening_data.empty
                or trading_data.empty
            ):
                continue

            opening_high = float(
                opening_data["high"].max()
            )

            position: Optional[
                Dict[str, Any]
            ] = None

            for _, row in trading_data.iterrows():
                if position is None:
                    entry_allowed = (
                        float(row["close"]) > opening_high
                        and float(row["ema_20"])
                        > float(row["ema_50"])
                        and float(row["close"])
                        > float(row["vwap"])
                        and minimum_rsi
                        <= float(row["rsi"])
                        <= maximum_rsi
                        and float(row["volume_ratio"])
                        >= minimum_volume_ratio
                        and float(row["atr"]) > 0
                    )

                    if not entry_allowed:
                        continue

                    entry_price = float(row["close"])
                    atr = float(row["atr"])

                    stop_loss = (
                        entry_price
                        - atr * stop_atr_multiplier
                    )

                    target = (
                        entry_price
                        + atr * target_atr_multiplier
                    )

                    if not (
                        0 < stop_loss
                        < entry_price
                        < target
                    ):
                        continue

                    position = {
                        "entry_time": row["timestamp"],
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target": target,
                    }
                    continue

                low = float(row["low"])
                high = float(row["high"])

                exit_price: Optional[float] = None
                exit_reason = ""

                if low <= float(
                    position["stop_loss"]
                ):
                    exit_price = float(
                        position["stop_loss"]
                    )
                    exit_reason = "STOP_LOSS"

                elif high >= float(
                    position["target"]
                ):
                    exit_price = float(
                        position["target"]
                    )
                    exit_reason = "TARGET"

                if exit_price is None:
                    continue

                trades.append(
                    self._build_trade(
                        trade_date=trade_date,
                        position=position,
                        exit_time=row["timestamp"],
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                    )
                )

                position = None
                break

            if position is not None:
                last_row = day_data.iloc[-1]

                trades.append(
                    self._build_trade(
                        trade_date=trade_date,
                        position=position,
                        exit_time=last_row[
                            "timestamp"
                        ],
                        exit_price=float(
                            last_row["close"]
                        ),
                        exit_reason="DAY_END_EXIT",
                    )
                )

        return self._summarize(trades)

    def _build_trade(
        self,
        trade_date: Any,
        position: Dict[str, Any],
        exit_time: Any,
        exit_price: float,
        exit_reason: str,
    ) -> Dict[str, Any]:
        entry_price = float(
            position["entry_price"]
        )

        stop_loss = float(
            position["stop_loss"]
        )

        initial_risk = (
            entry_price - stop_loss
        )

        pnl = (
            float(exit_price) - entry_price
        )

        r_multiple = (
            pnl / initial_risk
            if initial_risk > 0
            else 0.0
        )

        return {
            "trade_date": str(trade_date),
            "entry_time": position["entry_time"],
            "exit_time": exit_time,
            "entry_price": entry_price,
            "exit_price": float(exit_price),
            "stop_loss": stop_loss,
            "target": float(position["target"]),
            "exit_reason": exit_reason,
            "pnl": float(pnl),
            "r_multiple": float(r_multiple),
        }

    def _summarize(
        self,
        trades: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not trades:
            return self._empty_result()

        trade_df = pd.DataFrame(trades)

        wins = trade_df[
            trade_df["pnl"] > 0
        ]
        losses = trade_df[
            trade_df["pnl"] < 0
        ]
        breakeven = trade_df[
            trade_df["pnl"] == 0
        ]

        total_trades = len(trade_df)

        gross_profit = float(
            wins["pnl"].sum()
        )

        gross_loss = abs(
            float(losses["pnl"].sum())
        )

        total_pnl = float(
            trade_df["pnl"].sum()
        )

        win_rate = (
            len(wins)
            / total_trades
            * 100
        )

        loss_rate = (
            len(losses)
            / total_trades
            * 100
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf")
        )

        expectancy = (
            total_pnl / total_trades
        )

        average_win = (
            float(wins["pnl"].mean())
            if not wins.empty
            else 0.0
        )

        average_loss = (
            float(losses["pnl"].mean())
            if not losses.empty
            else 0.0
        )

        equity = pd.concat(
            [
                pd.Series(
                    [self.initial_balance]
                ),
                (
                    self.initial_balance
                    + trade_df["pnl"].cumsum()
                ),
            ],
            ignore_index=True,
        )

        running_peak = equity.cummax()

        drawdown = (
            equity - running_peak
        )

        max_drawdown = abs(
            float(drawdown.min())
        )

        return {
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "win_rate": round(win_rate, 2),
            "loss_rate": round(loss_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "gross_profit": round(
                gross_profit,
                2,
            ),
            "gross_loss": round(
                gross_loss,
                2,
            ),
            "average_win": round(
                average_win,
                4,
            ),
            "average_loss": round(
                average_loss,
                4,
            ),
            "profit_factor": (
                round(profit_factor, 4)
                if profit_factor
                != float("inf")
                else float("inf")
            ),
            "expectancy": round(
                expectancy,
                4,
            ),
            "average_r": round(
                float(
                    trade_df[
                        "r_multiple"
                    ].mean()
                ),
                4,
            ),
            "max_drawdown": round(
                max_drawdown,
                2,
            ),
            "ending_balance": round(
                float(equity.iloc[-1]),
                2,
            ),
            "trades": trades,
        }

    def _empty_result(
        self,
    ) -> Dict[str, Any]:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "breakeven": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "total_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "average_r": 0.0,
            "max_drawdown": 0.0,
            "ending_balance": round(
                self.initial_balance,
                2,
            ),
            "trades": [],
        }


if __name__ == "__main__":
    builder = DatasetBuilder()

    dataset = builder.build_dataset(
        symbol="RELIANCE",
        interval_name="5m",
        year=2026,
    )

    evaluator = StrategyEvaluator()

    result = evaluator.evaluate_orb(
        dataframe=dataset,
        opening_range_minutes=15,
        stop_atr_multiplier=1.0,
        target_atr_multiplier=2.0,
        minimum_rsi=50.0,
        maximum_rsi=70.0,
        minimum_volume_ratio=1.0,
    )

    print()
    print("=" * 60)
    print("ORB STRATEGY EVALUATION")
    print("=" * 60)

    for key, value in result.items():
        if key == "trades":
            continue

        print(f"{key}: {value}")

    print()
    print("Trades:")

    for trade in result["trades"]:
        print(trade)
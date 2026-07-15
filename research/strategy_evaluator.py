"""
Strategy evaluator for historical research.

Runs a long-only ORB strategy using:

- adverse entry and exit slippage;
- Indian intraday trading costs;
- risk-based position sizing;
- capital-based position limits;
- dynamic account balance;
- net P&L and net R-multiple;
- rupee and percentage drawdown.

This evaluator is reused by the optimizer, multi-symbol
evaluator, multi-year evaluator, and walk-forward validator.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from core.trading_costs import calculate_intraday_costs
from research.dataset_builder import DatasetBuilder


class StrategyEvaluator:
    def __init__(
        self,
        initial_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_position_percent: float = 20.0,
        slippage_bps: float = 5.0,
    ) -> None:
        self.initial_balance = float(initial_balance)
        self.risk_per_trade_percent = float(
            risk_per_trade_percent
        )
        self.max_position_percent = float(
            max_position_percent
        )
        self.slippage_bps = float(slippage_bps)

        if self.initial_balance <= 0:
            raise ValueError(
                "Initial balance must be greater than zero."
            )

        if not (
            0 < self.risk_per_trade_percent <= 100
        ):
            raise ValueError(
                "Risk per trade must be between 0 and 100."
            )

        if not (
            0 < self.max_position_percent <= 100
        ):
            raise ValueError(
                "Maximum position percent must be "
                "between 0 and 100."
            )

        if self.slippage_bps < 0:
            raise ValueError(
                "Slippage cannot be negative."
            )

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

        if opening_range_minutes <= 0:
            raise ValueError(
                "Opening range must be greater than zero."
            )

        if stop_atr_multiplier <= 0:
            raise ValueError(
                "Stop ATR multiplier must be greater than zero."
            )

        if target_atr_multiplier <= 0:
            raise ValueError(
                "Target ATR multiplier must be greater than zero."
            )

        if minimum_rsi > maximum_rsi:
            raise ValueError(
                "Minimum RSI cannot exceed maximum RSI."
            )

        if minimum_volume_ratio < 0:
            raise ValueError(
                "Minimum volume ratio cannot be negative."
            )

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

        missing = required_columns.difference(
            dataframe.columns
        )

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
            subset=[
                "timestamp",
                *numeric_columns,
            ]
        )

        df = df.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        df["trade_date"] = (
            df["timestamp"].dt.date
        )

        slippage_rate = (
            self.slippage_bps / 10000.0
        )

        trades: List[
            Dict[str, Any]
        ] = []

        current_balance = float(
            self.initial_balance
        )

        skipped_for_quantity = 0

        for trade_date, day_data in (
            df.groupby("trade_date")
        ):
            day_data = (
                day_data.sort_values("timestamp")
                .reset_index(drop=True)
            )

            if day_data.empty:
                continue

            market_open = (
                day_data.iloc[0]["timestamp"]
            )

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
                    raw_entry_price = float(
                        row["close"]
                    )

                    entry_allowed = (
                        raw_entry_price > opening_high
                        and float(row["ema_20"])
                        > float(row["ema_50"])
                        and raw_entry_price
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

                    entry_price = (
                        raw_entry_price
                        * (1.0 + slippage_rate)
                    )

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

                    risk_per_share = (
                        entry_price - stop_loss
                    )

                    quantity_details = (
                        self._calculate_quantity(
                            account_balance=current_balance,
                            entry_price=entry_price,
                            risk_per_share=risk_per_share,
                        )
                    )

                    quantity = int(
                        quantity_details["quantity"]
                    )

                    if quantity <= 0:
                        skipped_for_quantity += 1
                        continue

                    position = {
                        "entry_time": row["timestamp"],
                        "raw_entry_price": raw_entry_price,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "target": target,
                        "quantity": quantity,
                        "risk_budget": (
                            quantity_details[
                                "risk_budget"
                            ]
                        ),
                        "position_capital_limit": (
                            quantity_details[
                                "position_capital_limit"
                            ]
                        ),
                        "risk_based_quantity": (
                            quantity_details[
                                "risk_based_quantity"
                            ]
                        ),
                        "capital_based_quantity": (
                            quantity_details[
                                "capital_based_quantity"
                            ]
                        ),
                        "account_balance_before": (
                            current_balance
                        ),
                    }

                    continue

                low = float(row["low"])
                high = float(row["high"])

                raw_exit_price: Optional[
                    float
                ] = None

                exit_reason = ""

                # Conservative intrabar assumption:
                # if stop and target are both touched,
                # stop is counted first.
                if low <= float(
                    position["stop_loss"]
                ):
                    raw_exit_price = float(
                        position["stop_loss"]
                    )
                    exit_reason = "STOP_LOSS"

                elif high >= float(
                    position["target"]
                ):
                    raw_exit_price = float(
                        position["target"]
                    )
                    exit_reason = "TARGET"

                if raw_exit_price is None:
                    continue

                exit_price = (
                    raw_exit_price
                    * (1.0 - slippage_rate)
                )

                trade = self._build_trade(
                    trade_date=trade_date,
                    position=position,
                    exit_time=row["timestamp"],
                    raw_exit_price=raw_exit_price,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                )

                current_balance = float(
                    trade[
                        "account_balance_after"
                    ]
                )

                trades.append(trade)

                position = None
                break

            if position is not None:
                last_row = day_data.iloc[-1]

                raw_exit_price = float(
                    last_row["close"]
                )

                exit_price = (
                    raw_exit_price
                    * (1.0 - slippage_rate)
                )

                trade = self._build_trade(
                    trade_date=trade_date,
                    position=position,
                    exit_time=last_row["timestamp"],
                    raw_exit_price=raw_exit_price,
                    exit_price=exit_price,
                    exit_reason="DAY_END_EXIT",
                )

                current_balance = float(
                    trade[
                        "account_balance_after"
                    ]
                )

                trades.append(trade)

        return self._summarize(
            trades=trades,
            skipped_for_quantity=(
                skipped_for_quantity
            ),
        )

    def _calculate_quantity(
        self,
        account_balance: float,
        entry_price: float,
        risk_per_share: float,
    ) -> Dict[str, Any]:
        if (
            account_balance <= 0
            or entry_price <= 0
            or risk_per_share <= 0
        ):
            return {
                "quantity": 0,
                "risk_budget": 0.0,
                "position_capital_limit": 0.0,
                "risk_based_quantity": 0,
                "capital_based_quantity": 0,
            }

        risk_budget = (
            account_balance
            * (
                self.risk_per_trade_percent
                / 100.0
            )
        )

        position_capital_limit = (
            account_balance
            * (
                self.max_position_percent
                / 100.0
            )
        )

        risk_based_quantity = int(
            risk_budget / risk_per_share
        )

        capital_based_quantity = int(
            position_capital_limit
            / entry_price
        )

        quantity = max(
            0,
            min(
                risk_based_quantity,
                capital_based_quantity,
            ),
        )

        return {
            "quantity": quantity,
            "risk_budget": float(
                risk_budget
            ),
            "position_capital_limit": float(
                position_capital_limit
            ),
            "risk_based_quantity": int(
                risk_based_quantity
            ),
            "capital_based_quantity": int(
                capital_based_quantity
            ),
        }

    def _build_trade(
        self,
        trade_date: Any,
        position: Dict[str, Any],
        exit_time: Any,
        raw_exit_price: float,
        exit_price: float,
        exit_reason: str,
    ) -> Dict[str, Any]:
        raw_entry_price = float(
            position["raw_entry_price"]
        )

        entry_price = float(
            position["entry_price"]
        )

        stop_loss = float(
            position["stop_loss"]
        )

        quantity = int(
            position["quantity"]
        )

        account_balance_before = float(
            position[
                "account_balance_before"
            ]
        )

        initial_risk_per_share = (
            entry_price - stop_loss
        )

        initial_risk_amount = (
            initial_risk_per_share
            * quantity
        )

        gross_pnl = (
            float(exit_price)
            - entry_price
        ) * quantity

        cost_breakdown = (
            calculate_intraday_costs(
                buy_price=entry_price,
                sell_price=float(exit_price),
                quantity=quantity,
            )
        )

        transaction_costs = float(
            cost_breakdown["total_costs"]
        )

        net_pnl = (
            gross_pnl
            - transaction_costs
        )

        account_balance_after = (
            account_balance_before
            + net_pnl
        )

        gross_pnl_per_share = (
            gross_pnl / quantity
            if quantity > 0
            else 0.0
        )

        net_pnl_per_share = (
            net_pnl / quantity
            if quantity > 0
            else 0.0
        )

        r_multiple = (
            net_pnl
            / initial_risk_amount
            if initial_risk_amount > 0
            else 0.0
        )

        return_percent = (
            net_pnl
            / account_balance_before
            * 100.0
            if account_balance_before > 0
            else 0.0
        )

        actual_risk_percent = (
            initial_risk_amount
            / account_balance_before
            * 100.0
            if account_balance_before > 0
            else 0.0
        )

        return {
            "trade_date": str(trade_date),
            "entry_time": position["entry_time"],
            "exit_time": exit_time,
            "quantity": quantity,
            "raw_entry_price": raw_entry_price,
            "entry_price": entry_price,
            "raw_exit_price": float(
                raw_exit_price
            ),
            "exit_price": float(exit_price),
            "stop_loss": stop_loss,
            "target": float(
                position["target"]
            ),
            "exit_reason": exit_reason,
            "risk_budget": float(
                position["risk_budget"]
            ),
            "position_capital_limit": float(
                position[
                    "position_capital_limit"
                ]
            ),
            "risk_based_quantity": int(
                position[
                    "risk_based_quantity"
                ]
            ),
            "capital_based_quantity": int(
                position[
                    "capital_based_quantity"
                ]
            ),
            "initial_risk_per_share": float(
                initial_risk_per_share
            ),
            "initial_risk_amount": float(
                initial_risk_amount
            ),
            "actual_risk_percent": float(
                actual_risk_percent
            ),
            "gross_pnl": float(gross_pnl),
            "gross_pnl_per_share": float(
                gross_pnl_per_share
            ),
            "brokerage": float(
                cost_breakdown["brokerage"]
            ),
            "stt": float(
                cost_breakdown["stt"]
            ),
            "exchange_charges": float(
                cost_breakdown[
                    "exchange_charges"
                ]
            ),
            "sebi_charges": float(
                cost_breakdown[
                    "sebi_charges"
                ]
            ),
            "stamp_duty": float(
                cost_breakdown["stamp_duty"]
            ),
            "gst": float(
                cost_breakdown["gst"]
            ),
            "transaction_costs": (
                transaction_costs
            ),
            "net_pnl": float(net_pnl),
            "net_pnl_per_share": float(
                net_pnl_per_share
            ),
            # Existing modules expect "pnl".
            # It intentionally means net P&L.
            "pnl": float(net_pnl),
            "r_multiple": float(
                r_multiple
            ),
            "return_percent": float(
                return_percent
            ),
            "account_balance_before": float(
                account_balance_before
            ),
            "account_balance_after": float(
                account_balance_after
            ),
            "slippage_bps": float(
                self.slippage_bps
            ),
        }

    def _summarize(
        self,
        trades: List[Dict[str, Any]],
        skipped_for_quantity: int = 0,
    ) -> Dict[str, Any]:
        if not trades:
            result = self._empty_result()
            result[
                "skipped_for_quantity"
            ] = int(
                skipped_for_quantity
            )
            return result

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

        gross_strategy_pnl = float(
            trade_df["gross_pnl"].sum()
        )

        total_transaction_costs = float(
            trade_df[
                "transaction_costs"
            ].sum()
        )

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
            len(wins) / total_trades * 100
        )

        loss_rate = (
            len(losses) / total_trades * 100
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

        average_quantity = float(
            trade_df["quantity"].mean()
        )

        average_cost_per_trade = float(
            trade_df[
                "transaction_costs"
            ].mean()
        )

        ending_balance = float(
            trade_df.iloc[-1][
                "account_balance_after"
            ]
        )

        total_return_percent = (
            ending_balance
            / self.initial_balance
            - 1.0
        ) * 100.0

        equity = pd.concat(
            [
                pd.Series(
                    [self.initial_balance]
                ),
                trade_df[
                    "account_balance_after"
                ].reset_index(drop=True),
            ],
            ignore_index=True,
        )

        running_peak = equity.cummax()

        drawdown_rupees = (
            equity - running_peak
        )

        drawdown_percent = (
            drawdown_rupees
            / running_peak.replace(0, pd.NA)
            * 100.0
        )

        max_drawdown = abs(
            float(drawdown_rupees.min())
        )

        max_drawdown_percent = abs(
            float(drawdown_percent.min())
        )

        return {
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "win_rate": round(
                win_rate,
                2,
            ),
            "loss_rate": round(
                loss_rate,
                2,
            ),
            "gross_strategy_pnl": round(
                gross_strategy_pnl,
                2,
            ),
            "transaction_costs": round(
                total_transaction_costs,
                2,
            ),
            "average_cost_per_trade": round(
                average_cost_per_trade,
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
            "max_drawdown_percent": round(
                max_drawdown_percent,
                4,
            ),
            "total_return_percent": round(
                total_return_percent,
                4,
            ),
            "ending_balance": round(
                ending_balance,
                2,
            ),
            "average_quantity": round(
                average_quantity,
                2,
            ),
            "risk_per_trade_percent": float(
                self.risk_per_trade_percent
            ),
            "max_position_percent": float(
                self.max_position_percent
            ),
            "slippage_bps": float(
                self.slippage_bps
            ),
            "skipped_for_quantity": int(
                skipped_for_quantity
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
            "gross_strategy_pnl": 0.0,
            "transaction_costs": 0.0,
            "average_cost_per_trade": 0.0,
            "total_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "average_r": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_percent": 0.0,
            "total_return_percent": 0.0,
            "ending_balance": round(
                self.initial_balance,
                2,
            ),
            "average_quantity": 0.0,
            "risk_per_trade_percent": float(
                self.risk_per_trade_percent
            ),
            "max_position_percent": float(
                self.max_position_percent
            ),
            "slippage_bps": float(
                self.slippage_bps
            ),
            "skipped_for_quantity": 0,
            "trades": [],
        }


if __name__ == "__main__":
    builder = DatasetBuilder()

    dataset = builder.build_dataset(
        symbol="RELIANCE",
        interval_name="5m",
        year=2026,
    )

    evaluator = StrategyEvaluator(
        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,
    )

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
    print(
        "ORB STRATEGY EVALUATION "
        "WITH RISK-BASED SIZING"
    )
    print("=" * 60)

    for key, value in result.items():
        if key == "trades":
            continue

        print(f"{key}: {value}")

    print()
    print("Trades:")

    for trade in result["trades"]:
        print(trade)
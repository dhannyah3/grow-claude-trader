"""
Base Strategy Evaluator

Shared historical execution engine for all research strategies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from core.trading_costs import calculate_intraday_costs
from research.base_strategy import BaseStrategy


class BaseStrategyEvaluator:
    """Shared evaluator used by every research strategy."""

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_position_percent: float = 20.0,
        slippage_bps: float = 5.0,
    ) -> None:
        self.strategy = strategy
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.risk_per_trade_percent = float(risk_per_trade_percent)
        self.max_position_percent = float(max_position_percent)
        self.slippage_bps = float(slippage_bps)
        self.trades: List[Dict[str, Any]] = []
        self.skipped_for_quantity = 0

        if self.initial_balance <= 0:
            raise ValueError("Initial balance must be greater than zero.")
        if not (0 < self.risk_per_trade_percent <= 100):
            raise ValueError("Risk per trade must be between 0 and 100.")
        if not (0 < self.max_position_percent <= 100):
            raise ValueError("Maximum position percent must be between 0 and 100.")
        if self.slippage_bps < 0:
            raise ValueError("Slippage cannot be negative.")

    def _calculate_quantity(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> Dict[str, Any]:
        risk_per_share = entry_price - stop_loss

        if (
            self.balance <= 0
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
            self.balance
            * (self.risk_per_trade_percent / 100.0)
        )
        position_capital_limit = (
            self.balance
            * (self.max_position_percent / 100.0)
        )
        risk_based_quantity = int(risk_budget / risk_per_share)
        capital_based_quantity = int(position_capital_limit / entry_price)
        quantity = max(
            0,
            min(risk_based_quantity, capital_based_quantity),
        )

        return {
            "quantity": int(quantity),
            "risk_budget": float(risk_budget),
            "position_capital_limit": float(position_capital_limit),
            "risk_based_quantity": int(risk_based_quantity),
            "capital_based_quantity": int(capital_based_quantity),
        }

    def _apply_entry_slippage(
        self,
        raw_entry_price: float,
    ) -> float:
        return raw_entry_price * (
            1.0 + self.slippage_bps / 10000.0
        )

    def _apply_exit_slippage(
        self,
        raw_exit_price: float,
    ) -> float:
        return raw_exit_price * (
            1.0 - self.slippage_bps / 10000.0
        )

    def _open_position(
        self,
        row: pd.Series,
    ) -> Dict[str, Any]:
        raw_entry_price = float(row["close"])
        entry_price = self._apply_entry_slippage(raw_entry_price)
        stop_loss = float(
            self.strategy.calculate_stop_loss(
                row=row,
                entry_price=entry_price,
            )
        )
        target = float(
            self.strategy.calculate_target(
                row=row,
                entry_price=entry_price,
                stop_loss=stop_loss,
            )
        )

        if not (0 < stop_loss < entry_price < target):
            return {}

        quantity_details = self._calculate_quantity(
            entry_price=entry_price,
            stop_loss=stop_loss,
        )
        quantity = int(quantity_details["quantity"])

        if quantity <= 0:
            self.skipped_for_quantity += 1
            return {}

        initial_risk_per_share = entry_price - stop_loss
        initial_risk_amount = initial_risk_per_share * quantity

        return {
            "entry_time": row["timestamp"],
            "raw_entry_price": raw_entry_price,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "quantity": quantity,
            "initial_risk_per_share": initial_risk_per_share,
            "initial_risk_amount": initial_risk_amount,
            "account_balance_before": self.balance,
            "risk_budget": quantity_details["risk_budget"],
            "position_capital_limit": quantity_details[
                "position_capital_limit"
            ],
            "risk_based_quantity": quantity_details[
                "risk_based_quantity"
            ],
            "capital_based_quantity": quantity_details[
                "capital_based_quantity"
            ],
            "metadata": self.strategy.additional_trade_metadata(row),
        }

    def _close_trade(
        self,
        position: Dict[str, Any],
        row: pd.Series,
        raw_exit_price: float,
        exit_reason: str,
    ) -> Dict[str, Any]:
        exit_price = self._apply_exit_slippage(raw_exit_price)
        quantity = int(position["quantity"])
        entry_price = float(position["entry_price"])
        gross_pnl = (exit_price - entry_price) * quantity

        cost_breakdown = calculate_intraday_costs(
            buy_price=entry_price,
            sell_price=exit_price,
            quantity=quantity,
        )
        transaction_costs = float(cost_breakdown["total_costs"])
        net_pnl = gross_pnl - transaction_costs
        balance_before = float(position["account_balance_before"])
        balance_after = balance_before + net_pnl
        initial_risk_amount = float(position["initial_risk_amount"])
        r_multiple = (
            net_pnl / initial_risk_amount
            if initial_risk_amount > 0
            else 0.0
        )

        trade = {
            "strategy": self.strategy.name,
            "trade_date": str(row["timestamp"].date()),
            "entry_time": position["entry_time"],
            "exit_time": row["timestamp"],
            "quantity": quantity,
            "raw_entry_price": float(position["raw_entry_price"]),
            "entry_price": entry_price,
            "raw_exit_price": float(raw_exit_price),
            "exit_price": float(exit_price),
            "stop_loss": float(position["stop_loss"]),
            "target": float(position["target"]),
            "exit_reason": exit_reason,
            "risk_budget": float(position["risk_budget"]),
            "position_capital_limit": float(
                position["position_capital_limit"]
            ),
            "risk_based_quantity": int(
                position["risk_based_quantity"]
            ),
            "capital_based_quantity": int(
                position["capital_based_quantity"]
            ),
            "initial_risk_per_share": float(
                position["initial_risk_per_share"]
            ),
            "initial_risk_amount": initial_risk_amount,
            "gross_pnl": float(gross_pnl),
            "transaction_costs": transaction_costs,
            "net_pnl": float(net_pnl),
            "pnl": float(net_pnl),
            "r_multiple": float(r_multiple),
            "account_balance_before": balance_before,
            "account_balance_after": balance_after,
            "slippage_bps": float(self.slippage_bps),
            **cost_breakdown,
            **position.get("metadata", {}),
        }

        self.balance = float(balance_after)
        self.trades.append(trade)
        return trade

    def evaluate(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict[str, Any]:
        if dataframe.empty:
            return self._empty_summary()

        df = self.strategy.prepare_dataframe(dataframe)
        self.strategy.validate_dataframe(df)

        df = df.copy()
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        for column in ["open", "high", "low", "close"]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df = df.dropna(
            subset=["timestamp", "open", "high", "low", "close"]
        )
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["trade_date"] = df["timestamp"].dt.date

        self.balance = float(self.initial_balance)
        self.trades = []
        self.skipped_for_quantity = 0

        for _, day_data in df.groupby("trade_date", sort=True):
            day_data = (
                day_data.sort_values("timestamp")
                .reset_index(drop=True)
            )
            position: Optional[Dict[str, Any]] = None

            for row_index, row in day_data.iterrows():
                if position is None:
                    if not self.strategy.can_open_new_position(row):
                        continue
                    if not self.strategy.should_enter(
                        row_index=row_index,
                        row=row,
                        day_data=day_data,
                    ):
                        continue

                    candidate = self._open_position(row)
                    if candidate:
                        position = candidate
                    continue

                exit_signal = self.strategy.get_exit_signal(
                    row=row,
                    position=position,
                )
                if exit_signal is None:
                    continue

                self._close_trade(
                    position=position,
                    row=row,
                    raw_exit_price=float(
                        exit_signal["raw_exit_price"]
                    ),
                    exit_reason=str(exit_signal["exit_reason"]),
                )
                position = None
                break

            if position is not None:
                exit_candidates = day_data[
                    day_data["timestamp"].dt.time
                    <= self.strategy.force_exit_time
                ]
                exit_candidates = exit_candidates[
                    exit_candidates["timestamp"]
                    >= position["entry_time"]
                ]

                if exit_candidates.empty:
                    continue

                last_row = exit_candidates.iloc[-1]
                self._close_trade(
                    position=position,
                    row=last_row,
                    raw_exit_price=float(last_row["close"]),
                    exit_reason="DAY_END_EXIT",
                )

        return self._summarize()

    def _empty_summary(self) -> Dict[str, Any]:
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
            "ending_balance": round(self.initial_balance, 2),
            "average_quantity": 0.0,
            "risk_per_trade_percent": float(
                self.risk_per_trade_percent
            ),
            "max_position_percent": float(
                self.max_position_percent
            ),
            "slippage_bps": float(self.slippage_bps),
            "skipped_for_quantity": int(self.skipped_for_quantity),
            "trades": [],
        }

    def _summarize(self) -> Dict[str, Any]:
        if not self.trades:
            return self._empty_summary()

        trade_df = pd.DataFrame(self.trades)
        total_trades = len(trade_df)
        wins_df = trade_df[trade_df["net_pnl"] > 0]
        losses_df = trade_df[trade_df["net_pnl"] < 0]
        breakeven_df = trade_df[trade_df["net_pnl"] == 0]

        wins = len(wins_df)
        losses = len(losses_df)
        breakeven = len(breakeven_df)
        gross_strategy_pnl = float(trade_df["gross_pnl"].sum())
        transaction_costs = float(
            trade_df["transaction_costs"].sum()
        )
        total_pnl = float(trade_df["net_pnl"].sum())
        gross_profit = float(wins_df["net_pnl"].sum())
        gross_loss = abs(float(losses_df["net_pnl"].sum()))
        average_win = (
            float(wins_df["net_pnl"].mean())
            if not wins_df.empty
            else 0.0
        )
        average_loss = (
            float(losses_df["net_pnl"].mean())
            if not losses_df.empty
            else 0.0
        )
        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else (float("inf") if gross_profit > 0 else 0.0)
        )
        expectancy = total_pnl / total_trades
        average_r = float(trade_df["r_multiple"].mean())

        equity = pd.concat(
            [
                pd.Series([self.initial_balance]),
                trade_df["account_balance_after"].reset_index(drop=True),
            ],
            ignore_index=True,
        )
        running_peak = equity.cummax()
        drawdown_rupees = equity - running_peak
        drawdown_percent = (
            drawdown_rupees
            / running_peak.replace(0, pd.NA)
            * 100.0
        )
        max_drawdown = abs(float(drawdown_rupees.min()))
        max_drawdown_percent = abs(float(drawdown_percent.min()))
        ending_balance = float(self.balance)
        total_return_percent = (
            ending_balance / self.initial_balance - 1.0
        ) * 100.0

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": round(wins / total_trades * 100.0, 2),
            "loss_rate": round(losses / total_trades * 100.0, 2),
            "gross_strategy_pnl": round(gross_strategy_pnl, 2),
            "transaction_costs": round(transaction_costs, 2),
            "average_cost_per_trade": round(
                transaction_costs / total_trades,
                2,
            ),
            "total_pnl": round(total_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "average_win": round(average_win, 4),
            "average_loss": round(average_loss, 4),
            "profit_factor": (
                round(profit_factor, 4)
                if profit_factor != float("inf")
                else float("inf")
            ),
            "expectancy": round(expectancy, 4),
            "average_r": round(average_r, 4),
            "max_drawdown": round(max_drawdown, 2),
            "max_drawdown_percent": round(max_drawdown_percent, 4),
            "total_return_percent": round(total_return_percent, 4),
            "ending_balance": round(ending_balance, 2),
            "average_quantity": round(
                float(trade_df["quantity"].mean()),
                2,
            ),
            "risk_per_trade_percent": float(
                self.risk_per_trade_percent
            ),
            "max_position_percent": float(
                self.max_position_percent
            ),
            "slippage_bps": float(self.slippage_bps),
            "skipped_for_quantity": int(self.skipped_for_quantity),
            "trades": self.trades,
        }
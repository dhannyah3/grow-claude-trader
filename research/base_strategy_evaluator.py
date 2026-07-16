"""
Base Strategy Evaluator

Shared execution engine for all research strategies.

Responsibilities:
- Position sizing
- Slippage
- Trading costs
- Trade execution
- Balance tracking
- Statistics
- Reporting

Each strategy only supplies entry, stop-loss,
target, and optional metadata.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from core.trading_costs import calculate_intraday_costs
from research.base_strategy import BaseStrategy


class BaseStrategyEvaluator:
    """
    Shared evaluator used by every strategy.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_position_percent: float = 20.0,
        slippage_bps: float = 5.0,
    ):

        self.strategy = strategy

        self.initial_balance = float(initial_balance)

        self.balance = float(initial_balance)

        self.risk_per_trade_percent = float(
            risk_per_trade_percent
        )

        self.max_position_percent = float(
            max_position_percent
        )

        self.slippage_bps = float(slippage_bps)

        self.trades: List[Dict] = []

    def _calculate_quantity(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> Dict[str, float]:
        risk_per_share = (
            entry_price
            - stop_loss
        )

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
            * (
                self.risk_per_trade_percent
                / 100.0
            )
        )

        position_capital_limit = (
            self.balance
            * (
                self.max_position_percent
                / 100.0
            )
        )

        risk_based_quantity = int(
            risk_budget
            / risk_per_share
        )

        capital_based_quantity = int(
            position_capital_limit
            / entry_price
        )

        quantity = min(
            risk_based_quantity,
            capital_based_quantity,
        )

        return {
            "quantity": max(
                quantity,
                0,
            ),
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
    def _apply_entry_slippage(
        self,
        raw_entry_price: float,
    ) -> float:
        """
        Apply adverse slippage to entry.
        """
        return (
            raw_entry_price
            * (
                1
                + self.slippage_bps / 10000
            )
        )

    def _apply_exit_slippage(
        self,
        raw_exit_price: float,
    ) -> float:
        """
        Apply adverse slippage to exit.
        """
        return (
            raw_exit_price
            * (
                1
                - self.slippage_bps / 10000
            )
        ) 
    
    def _close_trade(
        self,
        position: Dict,
        row: pd.Series,
        raw_exit_price: float,
        exit_reason: str,
    ) -> Dict:
        exit_price = self._apply_exit_slippage(
            raw_exit_price
        )

        quantity = int(
            position["quantity"]
        )

        entry_price = float(
            position["entry_price"]
        )

        gross_pnl = (
            exit_price - entry_price
        ) * quantity

        cost_breakdown = calculate_intraday_costs(
            buy_price=entry_price,
            sell_price=exit_price,
            quantity=quantity,
        )

        transaction_costs = float(
            cost_breakdown["total_costs"]
        )

        net_pnl = (
            gross_pnl
            - transaction_costs
        )

        balance_before = float(
            position["account_balance_before"]
        )

        balance_after = (
            balance_before
            + net_pnl
        )

        initial_risk_amount = float(
            position["initial_risk_amount"]
        )

        r_multiple = (
            net_pnl
            / initial_risk_amount
            if initial_risk_amount > 0
            else 0.0
        )

        trade = {
            "strategy": self.strategy.name,
            "trade_date": str(
                row["timestamp"].date()
            ),
            "entry_time": position[
                "entry_time"
            ],
            "exit_time": row["timestamp"],
            "quantity": quantity,
            "raw_entry_price": position[
                "raw_entry_price"
            ],
            "entry_price": entry_price,
            "raw_exit_price": float(
                raw_exit_price
            ),
            "exit_price": float(
                exit_price
            ),
            "stop_loss": position[
                "stop_loss"
            ],
            "target": position[
                "target"
            ],
            "exit_reason": exit_reason,
            "gross_pnl": float(
                gross_pnl
            ),
            "transaction_costs": (
                transaction_costs
            ),
            "net_pnl": float(
                net_pnl
            ),
            "pnl": float(
                net_pnl
            ),
            "r_multiple": float(
                r_multiple
            ),
            "account_balance_before": (
                balance_before
            ),
            "account_balance_after": (
                balance_after
            ),
            **cost_breakdown,
            **position.get(
                "metadata",
                {},
            ),
        }

        self.balance = balance_after
        self.trades.append(trade)

        return trade
    
    def _open_position(
        self,
        row: pd.Series,
    ) -> Dict:
        raw_entry_price = float(
            row["close"]
        )

        entry_price = (
            self._apply_entry_slippage(
                raw_entry_price
            )
        )

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

        if not (
            0
            < stop_loss
            < entry_price
            < target
        ):
            return {}

        quantity_details = (
            self._calculate_quantity(
                entry_price=entry_price,
                stop_loss=stop_loss,
            )
        )

        quantity = int(
            quantity_details["quantity"]
        )

        if quantity <= 0:
            return {}

        initial_risk_per_share = (
            entry_price
            - stop_loss
        )

        initial_risk_amount = (
            initial_risk_per_share
            * quantity
        )

        metadata = (
            self.strategy
            .additional_trade_metadata(
                row
            )
        )

        return {
            "entry_time": row["timestamp"],
            "raw_entry_price": (
                raw_entry_price
            ),
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            "quantity": quantity,
            "initial_risk_per_share": (
                initial_risk_per_share
            ),
            "initial_risk_amount": (
                initial_risk_amount
            ),
            "account_balance_before": (
                self.balance
            ),
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
            "metadata": metadata,
        }

    def evaluate(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict:
        if dataframe.empty:
            return {
                "total_trades": 0,
                "trades": [],
            }

        self.strategy.validate_dataframe(
            dataframe
        )

        df = dataframe.copy()

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        df = df.dropna(
            subset=["timestamp"]
        )

        df = df.sort_values(
            "timestamp"
        ).reset_index(
            drop=True
        )

        df["trade_date"] = (
            df["timestamp"].dt.date
        )

        self.balance = float(
            self.initial_balance
        )

        self.trades = []

        for _, day_data in df.groupby(
            "trade_date"
        ):
            day_data = (
                day_data.sort_values(
                    "timestamp"
                )
                .reset_index(
                    drop=True
                )
            )

            position = None

            for row_index, row in (
                day_data.iterrows()
            ):
                current_time = (
                    row["timestamp"].time()
                )

                if position is None:
                    if not (
                        self.strategy
                        .can_open_new_position(
                            row
                        )
                    ):
                        continue

                    if not (
                        self.strategy.should_enter(
                            row_index=row_index,
                            row=row,
                            day_data=day_data,
                        )
                    ):
                        continue

                    candidate = (
                        self._open_position(
                            row
                        )
                    )

                    if candidate:
                        position = candidate

                    continue

                exit_signal = (
                    self.strategy.get_exit_signal(
                        row=row,
                        position=position,
                    )
                )

                if exit_signal is None:
                    continue

                self._close_trade(
                    position=position,
                    row=row,
                    raw_exit_price=float(
                        exit_signal[
                            "raw_exit_price"
                        ]
                    ),
                    exit_reason=str(
                        exit_signal[
                            "exit_reason"
                        ]
                    ),
                )

                position = None
                break

            if position is not None:
                exit_candidates = day_data[
                    day_data[
                        "timestamp"
                    ].dt.time
                    <= (
                        self.strategy
                        .force_exit_time
                    )
                ]

                exit_candidates = (
                    exit_candidates[
                        exit_candidates[
                            "timestamp"
                        ]
                        >= position[
                            "entry_time"
                        ]
                    ]
                )

                if exit_candidates.empty:
                    continue

                last_row = (
                    exit_candidates.iloc[-1]
                )

                self._close_trade(
                    position=position,
                    row=last_row,
                    raw_exit_price=float(
                        last_row["close"]
                    ),
                    exit_reason=(
                        "DAY_END_EXIT"
                    ),
                )

        return self._summarize()
    
    def _summarize(self) -> Dict:
        """
        Build the final performance summary.
        """

        if not self.trades:
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
                    self.balance,
                    2,
                ),
                "average_quantity": 0.0,
                "risk_per_trade_percent": self.risk_per_trade_percent,
                "max_position_percent": self.max_position_percent,
                "slippage_bps": self.slippage_bps,
                "trades": [],
            }

        trade_df = pd.DataFrame(self.trades)

        total_trades = len(trade_df)

        wins = int(
            (trade_df["net_pnl"] > 0).sum()
        )

        losses = int(
            (trade_df["net_pnl"] < 0).sum()
        )

        breakeven = int(
            (trade_df["net_pnl"] == 0).sum()
        )

        gross_strategy_pnl = float(
            trade_df["gross_pnl"].sum()
        )

        transaction_costs = float(
            trade_df["transaction_costs"].sum()
        )

        total_pnl = float(
            trade_df["net_pnl"].sum()
        )

        gross_profit = float(
            trade_df.loc[
                trade_df["net_pnl"] > 0,
                "net_pnl",
            ].sum()
        )

        gross_loss = abs(
            float(
                trade_df.loc[
                    trade_df["net_pnl"] < 0,
                    "net_pnl",
                ].sum()
            )
        )

        average_win = (
            gross_profit / wins
            if wins
            else 0.0
        )

        average_loss = (
            -gross_loss / losses
            if losses
            else 0.0
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0.0
        )

        expectancy = (
            total_pnl / total_trades
        )

        average_r = float(
            trade_df["r_multiple"].mean()
        )

        equity_curve = (
            self.initial_balance
            + trade_df["net_pnl"].cumsum()
        )

        rolling_peak = (
            equity_curve.cummax()
        )

        drawdown = (
            rolling_peak
            - equity_curve
        )

        max_drawdown = float(
            drawdown.max()
        )

        max_drawdown_percent = (
            max_drawdown
            / self.initial_balance
            * 100
        )

        total_return_percent = (
            (
                self.balance
                - self.initial_balance
            )
            / self.initial_balance
            * 100
        )

        return {
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": round(
                wins / total_trades * 100,
                2,
            ),
            "loss_rate": round(
                losses / total_trades * 100,
                2,
            ),
            "gross_strategy_pnl": round(
                gross_strategy_pnl,
                2,
            ),
            "transaction_costs": round(
                transaction_costs,
                2,
            ),
            "average_cost_per_trade": round(
                transaction_costs
                / total_trades,
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
            "profit_factor": round(
                profit_factor,
                4,
            ),
            "expectancy": round(
                expectancy,
                4,
            ),
            "average_r": round(
                average_r,
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
                self.balance,
                2,
            ),
            "average_quantity": round(
                trade_df["quantity"].mean(),
                2,
            ),
            "risk_per_trade_percent": self.risk_per_trade_percent,
            "max_position_percent": self.max_position_percent,
            "slippage_bps": self.slippage_bps,
            "trades": self.trades,
        }
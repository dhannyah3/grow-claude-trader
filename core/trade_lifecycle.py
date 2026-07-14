from datetime import datetime
from typing import Any, Dict, Optional


class TradeLifecycle:
    """
    Manages the complete lifecycle of every trade.

    Version 2 supports:
    - Opening trades
    - Preventing duplicate trades
    - Updating live prices
    - Calculating unrealized P&L
    - Tracking highest and lowest prices
    - Moving stop loss to breakeven
    - Detecting stop-loss and target exits
    - Closing trades
    """

    def __init__(self) -> None:
        self.active_trades: Dict[
            str,
            Dict[str, Any],
        ] = {}

    def open_trade(
        self,
        symbol: str,
        strategy: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:
        symbol = str(
            symbol
        ).strip().upper()

        if not symbol:
            print(
                "Lifecycle trade requires a symbol."
            )
            return False

        if symbol in self.active_trades:
            print(
                f"{symbol}: lifecycle trade "
                "already exists."
            )
            return False

        if quantity <= 0:
            print(
                f"{symbol}: quantity must "
                "be positive."
            )
            return False

        if not (
            0 < stop_loss
            < entry_price
            < target
        ):
            print(
                f"{symbol}: invalid entry, "
                "stop, or target."
            )
            return False

        trade = {
            "symbol": symbol,
            "strategy": str(
                strategy
            ),
            "status": "ACTIVE",
            "quantity": int(
                quantity
            ),
            "entry_price": float(
                entry_price
            ),
            "current_price": float(
                entry_price
            ),
            "stop_loss": float(
                stop_loss
            ),
            "initial_stop_loss": float(
                stop_loss
            ),
            "breakeven_activated": False,
            "target": float(
                target
            ),
            "highest_price": float(
                entry_price
            ),
            "lowest_price": float(
                entry_price
            ),
            "entry_time": datetime.now(),
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "metadata": metadata or {},
        }

        self.active_trades[
            symbol
        ] = trade

        print(
            f"Lifecycle OPEN: {symbol} | "
            f"Qty: {quantity} | "
            f"Entry: ₹{entry_price:.2f}"
        )

        return True

    def has_open_trade(
        self,
        symbol: str,
    ) -> bool:
        normalized_symbol = str(
            symbol
        ).strip().upper()

        return (
            normalized_symbol
            in self.active_trades
        )

    def update_price(
        self,
        symbol: str,
        current_price: float,
    ) -> Dict[str, Any]:
        normalized_symbol = str(
            symbol
        ).strip().upper()

        trade = self.active_trades.get(
            normalized_symbol
        )

        if trade is None:
            return {
                "updated": False,
                "reason": (
                    f"{normalized_symbol}: no active "
                    "lifecycle trade."
                ),
            }

        if current_price <= 0:
            return {
                "updated": False,
                "reason": (
                    f"{normalized_symbol}: current "
                    "price must be positive."
                ),
            }

        current_price = float(
            current_price
        )

        entry_price = float(
            trade["entry_price"]
        )

        quantity = int(
            trade["quantity"]
        )

        trade["current_price"] = (
            current_price
        )

        trade["highest_price"] = max(
            float(
                trade["highest_price"]
            ),
            current_price,
        )

        trade["lowest_price"] = min(
            float(
                trade["lowest_price"]
            ),
            current_price,
        )

        unrealized_pnl = (
            current_price
            - entry_price
        ) * quantity

        trade["unrealized_pnl"] = float(
            unrealized_pnl
        )

        initial_stop_loss = float(
            trade["initial_stop_loss"]
        )

        initial_risk = (
            entry_price
            - initial_stop_loss
        )

        breakeven_trigger = (
            entry_price
            + initial_risk
        )

        breakeven_activated_now = False

        if (
            initial_risk > 0
            and not bool(
                trade[
                    "breakeven_activated"
                ]
            )
            and current_price
            >= breakeven_trigger
        ):
            trade["stop_loss"] = float(
                entry_price
            )

            trade[
                "breakeven_activated"
            ] = True

            breakeven_activated_now = True

            print(
                f"{normalized_symbol}: stop "
                f"moved to breakeven "
                f"₹{entry_price:.2f}"
            )

        exit_signal = None

        if current_price <= float(
            trade["stop_loss"]
        ):
            if bool(
                trade[
                    "breakeven_activated"
                ]
            ):
                exit_signal = "BREAKEVEN_STOP"
            else:
                exit_signal = "STOP_LOSS"

        elif current_price >= float(
            trade["target"]
        ):
            exit_signal = "TARGET"

        return {
            "updated": True,
            "symbol": normalized_symbol,
            "current_price": current_price,
            "unrealized_pnl": round(
                unrealized_pnl,
                2,
            ),
            "highest_price": float(
                trade["highest_price"]
            ),
            "lowest_price": float(
                trade["lowest_price"]
            ),
            "stop_loss": float(
                trade["stop_loss"]
            ),
            "initial_stop_loss": (
                initial_stop_loss
            ),
            "breakeven_trigger": round(
                breakeven_trigger,
                2,
            ),
            "breakeven_activated": bool(
                trade[
                    "breakeven_activated"
                ]
            ),
            "breakeven_activated_now": (
                breakeven_activated_now
            ),
            "exit_signal": exit_signal,
        }

    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
    ) -> Dict[str, Any]:
        normalized_symbol = str(
            symbol
        ).strip().upper()

        trade = self.active_trades.get(
            normalized_symbol
        )

        if trade is None:
            return {
                "closed": False,
                "reason": (
                    f"{normalized_symbol}: no active "
                    "lifecycle trade."
                ),
            }

        if exit_price <= 0:
            return {
                "closed": False,
                "reason": (
                    f"{normalized_symbol}: exit "
                    "price must be positive."
                ),
            }

        exit_price = float(
            exit_price
        )

        entry_price = float(
            trade["entry_price"]
        )

        quantity = int(
            trade["quantity"]
        )

        realized_pnl = (
            exit_price
            - entry_price
        ) * quantity

        trade["status"] = "COMPLETED"
        trade["exit_price"] = exit_price
        trade["exit_reason"] = str(
            exit_reason
        )
        trade["exit_time"] = datetime.now()
        trade["realized_pnl"] = float(
            realized_pnl
        )
        trade["unrealized_pnl"] = 0.0
        trade["current_price"] = (
            exit_price
        )

        completed_trade = dict(
            trade
        )

        del self.active_trades[
            normalized_symbol
        ]

        print(
            f"Lifecycle CLOSE: "
            f"{normalized_symbol} | "
            f"Exit: ₹{exit_price:.2f} | "
            f"P&L: ₹{realized_pnl:.2f} | "
            f"Reason: {exit_reason}"
        )

        return {
            "closed": True,
            "trade": completed_trade,
        }

    def get_trade(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        normalized_symbol = str(
            symbol
        ).strip().upper()

        trade = self.active_trades.get(
            normalized_symbol
        )

        if trade is None:
            return {}

        return dict(
            trade
        )

    def get_all_open_trades(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        return {
            symbol: dict(
                trade
            )
            for symbol, trade
            in self.active_trades.items()
        }
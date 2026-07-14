from datetime import datetime
from typing import Any, Dict


class TradeLifecycle:
    """
    Manages the complete lifecycle of every trade.

    Version 1 supports:
    - Opening trades
    - Updating prices
    - Calculating unrealized P&L
    - Closing trades
    """

    def __init__(self) -> None:
        # Active trades indexed by symbol
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
        metadata: Dict[str, Any] = None,
    ) -> bool:
        if symbol in self.active_trades:
            print(
                f"{symbol}: lifecycle trade already exists."
            )
            return False

        if quantity <= 0:
            print(
                f"{symbol}: quantity must be positive."
            )
            return False

        if not (
            0 < stop_loss
            < entry_price
            < target
        ):
            print(
                f"{symbol}: invalid entry, stop, or target."
            )
            return False

        trade = {
            "symbol": symbol,
            "strategy": strategy,
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

        self.active_trades[symbol] = trade

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
        return symbol in self.active_trades
    
    def update_price(
        self,
        symbol: str,
        current_price: float,
    ) -> Dict[str, Any]:
        trade = self.active_trades.get(
            symbol
        )

        if trade is None:
            return {
                "updated": False,
                "reason": (
                    f"{symbol}: no active lifecycle trade."
                ),
            }

        if current_price <= 0:
            return {
                "updated": False,
                "reason": (
                    f"{symbol}: current price must "
                    "be positive."
                ),
            }

        entry_price = float(
            trade["entry_price"]
        )

        quantity = int(
            trade["quantity"]
        )

        trade["current_price"] = float(
            current_price
        )

        trade["highest_price"] = max(
            float(
                trade["highest_price"]
            ),
            float(
                current_price
            ),
        )

        trade["lowest_price"] = min(
            float(
                trade["lowest_price"]
            ),
            float(
                current_price
            ),
        )

        unrealized_pnl = (
            float(current_price)
            - entry_price
        ) * quantity

        trade["unrealized_pnl"] = float(
            unrealized_pnl
        )

        exit_signal = None

        if current_price <= float(
            trade["stop_loss"]
        ):
            exit_signal = "STOP_LOSS"

        elif current_price >= float(
            trade["target"]
        ):
            exit_signal = "TARGET"

        return {
            "updated": True,
            "symbol": symbol,
            "current_price": float(
                current_price
            ),
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
            "exit_signal": exit_signal,
        }
    
    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
    ) -> Dict[str, Any]:
        trade = self.active_trades.get(
            symbol
        )

        if trade is None:
            return {
                "closed": False,
                "reason": (
                    f"{symbol}: no active lifecycle trade."
                ),
            }

        if exit_price <= 0:
            return {
                "closed": False,
                "reason": (
                    f"{symbol}: exit price must be positive."
                ),
            }

        entry_price = float(
            trade["entry_price"]
        )

        quantity = int(
            trade["quantity"]
        )

        realized_pnl = (
            float(exit_price)
            - entry_price
        ) * quantity

        trade["status"] = "COMPLETED"
        trade["exit_price"] = float(
            exit_price
        )
        trade["exit_reason"] = str(
            exit_reason
        )
        trade["exit_time"] = datetime.now()
        trade["realized_pnl"] = float(
            realized_pnl
        )
        trade["unrealized_pnl"] = 0.0
        trade["current_price"] = float(
            exit_price
        )

        completed_trade = dict(
            trade
        )

        del self.active_trades[symbol]

        print(
            f"Lifecycle CLOSE: {symbol} | "
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
        return self.active_trades.get(
            symbol,
            {},
        )

    def get_all_open_trades(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        return dict(
            self.active_trades
        )
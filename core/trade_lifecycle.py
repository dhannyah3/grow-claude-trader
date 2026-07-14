from datetime import datetime
from math import floor
from typing import Any, Dict, Optional


class TradeLifecycle:
    """
    Manages the complete lifecycle of every trade.

    Version 3 supports:
    - Opening trades
    - Preventing duplicate trades
    - Updating live prices
    - Calculating unrealized P&L
    - Tracking highest and lowest prices
    - Moving stop loss to breakeven at 1R
    - Risk-based trailing stops from 2R onward
    - Detecting stop-loss, breakeven, trailing,
      and target exits
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
        normalized_symbol = str(
            symbol
        ).strip().upper()

        if not normalized_symbol:
            print(
                "Lifecycle trade requires a symbol."
            )
            return False

        if normalized_symbol in self.active_trades:
            print(
                f"{normalized_symbol}: lifecycle "
                "trade already exists."
            )
            return False

        if quantity <= 0:
            print(
                f"{normalized_symbol}: quantity "
                "must be positive."
            )
            return False

        if not (
            0 < stop_loss
            < entry_price
            < target
        ):
            print(
                f"{normalized_symbol}: invalid "
                "entry, stop, or target."
            )
            return False

        entry_price = float(
            entry_price
        )

        stop_loss = float(
            stop_loss
        )

        target = float(
            target
        )

        risk_per_share = (
            entry_price
            - stop_loss
        )

        trade = {
            "symbol": normalized_symbol,
            "strategy": str(
                strategy
            ),
            "status": "ACTIVE",
            "quantity": int(
                quantity
            ),
            "entry_price": entry_price,
            "current_price": entry_price,
            "stop_loss": stop_loss,
            "initial_stop_loss": stop_loss,
            "target": target,
            "risk_per_share": (
                risk_per_share
            ),
            "highest_price": entry_price,
            "lowest_price": entry_price,
            "highest_r_multiple": 0,
            "breakeven_trigger": (
                entry_price
                + risk_per_share
            ),
            "breakeven_activated": False,
            "trailing_active": False,
            "entry_time": datetime.now(),
            "exit_time": None,
            "exit_price": None,
            "exit_reason": None,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "metadata": metadata or {},
        }

        self.active_trades[
            normalized_symbol
        ] = trade

        print(
            f"Lifecycle OPEN: "
            f"{normalized_symbol} | "
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
                    f"{normalized_symbol}: no "
                    "active lifecycle trade."
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

        trailing_result = (
            self.update_trailing_stop(
                symbol=normalized_symbol,
                current_price=current_price,
            )
        )

        exit_signal = None

        if current_price <= float(
            trade["stop_loss"]
        ):
            if bool(
                trade["trailing_active"]
            ):
                exit_signal = "TRAILING_STOP"

            elif bool(
                trade["breakeven_activated"]
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
            "initial_stop_loss": float(
                trade["initial_stop_loss"]
            ),
            "risk_per_share": float(
                trade["risk_per_share"]
            ),
            "breakeven_trigger": float(
                trade["breakeven_trigger"]
            ),
            "breakeven_activated": bool(
                trade["breakeven_activated"]
            ),
            "breakeven_activated_now": bool(
                trailing_result.get(
                    "breakeven_activated_now",
                    False,
                )
            ),
            "trailing_active": bool(
                trade["trailing_active"]
            ),
            "trailing_updated": bool(
                trailing_result.get(
                    "trailing_updated",
                    False,
                )
            ),
            "highest_r_multiple": int(
                trade["highest_r_multiple"]
            ),
            "current_r_multiple": float(
                trailing_result.get(
                    "current_r_multiple",
                    0.0,
                )
            ),
            "exit_signal": exit_signal,
        }

    def update_trailing_stop(
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
                    f"{normalized_symbol}: no "
                    "active lifecycle trade."
                ),
            }

        entry_price = float(
            trade["entry_price"]
        )

        risk_per_share = float(
            trade["risk_per_share"]
        )

        if risk_per_share <= 0:
            return {
                "updated": False,
                "reason": (
                    f"{normalized_symbol}: invalid "
                    "risk per share."
                ),
            }

        current_r_multiple = (
            float(current_price)
            - entry_price
        ) / risk_per_share

        reached_r_level = max(
            0,
            floor(
                current_r_multiple
            ),
        )

        breakeven_activated_now = False
        trailing_updated = False
        previous_stop = float(
            trade["stop_loss"]
        )

        if (
            reached_r_level >= 1
            and not bool(
                trade["breakeven_activated"]
            )
        ):
            trade["stop_loss"] = (
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

        if reached_r_level >= 2:
            new_stop_loss = (
                entry_price
                + (
                    reached_r_level - 1
                )
                * risk_per_share
            )

            if new_stop_loss > float(
                trade["stop_loss"]
            ):
                trade["stop_loss"] = float(
                    new_stop_loss
                )

                trade["trailing_active"] = (
                    True
                )

                trade[
                    "highest_r_multiple"
                ] = reached_r_level

                trailing_updated = True

                print(
                    f"{normalized_symbol}: "
                    f"trailing stop moved to "
                    f"₹{new_stop_loss:.2f} "
                    f"at {reached_r_level}R"
                )

        return {
            "updated": True,
            "current_r_multiple": round(
                current_r_multiple,
                4,
            ),
            "reached_r_level": (
                reached_r_level
            ),
            "previous_stop_loss": (
                previous_stop
            ),
            "stop_loss": float(
                trade["stop_loss"]
            ),
            "breakeven_activated_now": (
                breakeven_activated_now
            ),
            "trailing_updated": (
                trailing_updated
            ),
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
                    f"{normalized_symbol}: no "
                    "active lifecycle trade."
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
    ) -> Dict[
        str,
        Dict[str, Any],
    ]:
        return {
            symbol: dict(
                trade
            )
            for symbol, trade
            in self.active_trades.items()
        }
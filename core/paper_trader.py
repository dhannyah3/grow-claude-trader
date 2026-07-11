import csv
import json
import os

from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional


class PaperTrader:
    def __init__(
        self,
        starting_balance: float = 100000.0,
        log_file: str = "logs/paper_trades.csv",
    ):
        self.starting_balance = starting_balance
        self.cash_balance = starting_balance
        self.log_file = log_file

        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades = []

        self._prepare_log_file()
        self._save_open_positions()

    # ----------------------------------------------------
    # CREATE LOG FILE
    # ----------------------------------------------------

    def _prepare_log_file(self) -> None:
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

        if os.path.exists(self.log_file):
            return

        with open(
            self.log_file,
            "w",
            newline="",
            encoding="utf-8",
        ) as file:
            writer = csv.writer(file)

            writer.writerow(
                [
                    "entry_time",
                    "exit_time",
                    "symbol",
                    "quantity",
                    "entry_price",
                    "exit_price",
                    "stop_loss",
                    "target",
                    "pnl",
                    "exit_reason",
                ]
            )

    # ----------------------------------------------------
    # SAVE OPEN POSITIONS
    # ----------------------------------------------------

    def _save_open_positions(self) -> None:

        data = {}

        for symbol, position in self.open_positions.items():

            data[symbol] = {
                "symbol": position["symbol"],
                "quantity": position["quantity"],
                "entry_price": position["entry_price"],
                "stop_loss": position["stop_loss"],
                "target": position["target"],
                "entry_time": position["entry_time"].isoformat(),
            }

        Path("logs/open_positions.json").write_text(
            json.dumps(data, indent=4),
            encoding="utf-8",
        )

    # ----------------------------------------------------
    # OPEN TRADE
    # ----------------------------------------------------

    def open_trade(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        target: float,
    ) -> bool:

        if symbol in self.open_positions:
            print(f"{symbol}: position already open.")
            return False

        if quantity <= 0:
            print("Quantity must be greater than zero.")
            return False

        trade_value = quantity * entry_price

        if trade_value > self.cash_balance:
            print(
                f"Insufficient virtual balance. "
                f"Required: ₹{trade_value:.2f}, "
                f"Available: ₹{self.cash_balance:.2f}"
            )
            return False

        position = {
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "target": float(target),
            "entry_time": datetime.now(),
        }

        self.open_positions[symbol] = position

        self.cash_balance -= trade_value

        self._save_open_positions()

        print(
            f"Paper BUY: {symbol} | "
            f"Qty: {quantity} | "
            f"Entry: ₹{entry_price:.2f}"
        )

        return True

    # ----------------------------------------------------
    # CLOSE TRADE
    # ----------------------------------------------------

    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
    ) -> Optional[Dict[str, Any]]:

        position = self.open_positions.get(symbol)

        if position is None:
            print(f"{symbol}: no open paper position.")
            return None

        quantity = position["quantity"]
        entry_price = position["entry_price"]

        exit_value = quantity * exit_price

        pnl = (exit_price - entry_price) * quantity

        self.cash_balance += exit_value

        trade = {
            "entry_time": position["entry_time"],
            "exit_time": datetime.now(),
            "symbol": symbol,
            "quantity": quantity,
            "entry_price": entry_price,
            "exit_price": float(exit_price),
            "stop_loss": position["stop_loss"],
            "target": position["target"],
            "pnl": float(pnl),
            "exit_reason": exit_reason,
        }

        self.closed_trades.append(trade)

        del self.open_positions[symbol]

        self._save_open_positions()

        self._write_trade_to_log(trade)

        print(
            f"Paper SELL: {symbol} | "
            f"Qty: {quantity} | "
            f"Exit: ₹{exit_price:.2f} | "
            f"P&L: ₹{pnl:.2f}"
        )

        return trade

    # ----------------------------------------------------
    # CHECK EXIT
    # ----------------------------------------------------

    def check_exit(
        self,
        symbol: str,
        current_price: float,
    ) -> Optional[Dict[str, Any]]:

        position = self.open_positions.get(symbol)

        if position is None:
            return None

        if current_price <= position["stop_loss"]:

            return self.close_trade(
                symbol=symbol,
                exit_price=current_price,
                exit_reason="STOP_LOSS",
            )

        if current_price >= position["target"]:

            return self.close_trade(
                symbol=symbol,
                exit_price=current_price,
                exit_reason="TARGET",
            )

        return None

    # ----------------------------------------------------
    # WRITE CSV
    # ----------------------------------------------------

    def _write_trade_to_log(
        self,
        trade: Dict[str, Any],
    ) -> None:

        with open(
            self.log_file,
            "a",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.writer(file)

            writer.writerow(
                [
                    trade["entry_time"].isoformat(),
                    trade["exit_time"].isoformat(),
                    trade["symbol"],
                    trade["quantity"],
                    trade["entry_price"],
                    trade["exit_price"],
                    trade["stop_loss"],
                    trade["target"],
                    trade["pnl"],
                    trade["exit_reason"],
                ]
            )

    # ----------------------------------------------------

    def get_open_position(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:

        return self.open_positions.get(symbol)

    def total_realized_pnl(self) -> float:

        return sum(
            trade["pnl"]
            for trade in self.closed_trades
        )

    def account_summary(self) -> Dict[str, Any]:

        return {
            "starting_balance": self.starting_balance,
            "cash_balance": round(self.cash_balance, 2),
            "open_positions": len(self.open_positions),
            "closed_trades": len(self.closed_trades),
            "realized_pnl": round(
                self.total_realized_pnl(),
                2,
            ),
        }


if __name__ == "__main__":

    trader = PaperTrader()

    trader.open_trade(
        symbol="RELIANCE",
        quantity=10,
        entry_price=1300,
        stop_loss=1290,
        target=1320,
    )

    trader.check_exit(
        "RELIANCE",
        1321,
    )

    print(trader.account_summary())
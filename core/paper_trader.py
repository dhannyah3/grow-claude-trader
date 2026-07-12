import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class PaperTrader:
    def __init__(
        self,
        starting_balance: float = 100000.0,
        log_file: str = "logs/paper_trades.csv",
        positions_file: str = "logs/open_positions.json",
    ) -> None:
        self.starting_balance = float(starting_balance)
        self.cash_balance = float(starting_balance)

        self.log_file = Path(log_file)
        self.positions_file = Path(positions_file)

        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []

        self._prepare_files()
        self._load_closed_trades()
        self._load_open_positions()
        self._recalculate_cash_balance()

    def _prepare_files(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.positions_file.parent.mkdir(parents=True, exist_ok=True)

        if not self.log_file.exists():
            with self.log_file.open(
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

        if not self.positions_file.exists():
            self.positions_file.write_text(
                "{}",
                encoding="utf-8",
            )

    def _load_closed_trades(self) -> None:
        self.closed_trades = []

        try:
            with self.log_file.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as file:
                reader = csv.DictReader(file)

                for row in reader:
                    if not row.get("symbol"):
                        continue

                    try:
                        trade = {
                            "entry_time": datetime.fromisoformat(
                                row["entry_time"]
                            ),
                            "exit_time": datetime.fromisoformat(
                                row["exit_time"]
                            ),
                            "symbol": row["symbol"],
                            "quantity": int(float(row["quantity"])),
                            "entry_price": float(row["entry_price"]),
                            "exit_price": float(row["exit_price"]),
                            "stop_loss": float(row["stop_loss"]),
                            "target": float(row["target"]),
                            "pnl": float(row["pnl"]),
                            "exit_reason": row["exit_reason"],
                        }
                        self.closed_trades.append(trade)

                    except (
                        KeyError,
                        TypeError,
                        ValueError,
                    ) as error:
                        print(
                            "Skipping invalid trade-log row: "
                            f"{error}"
                        )

        except OSError as error:
            print(f"Could not load closed trades: {error}")

    def _load_open_positions(self) -> None:
        self.open_positions = {}

        if (
            not self.positions_file.exists()
            or self.positions_file.stat().st_size == 0
        ):
            return

        try:
            raw_text = self.positions_file.read_text(
                encoding="utf-8"
            ).strip()

            if not raw_text:
                return

            saved_positions = json.loads(raw_text)

            if not isinstance(saved_positions, dict):
                print("Open positions file has an invalid format.")
                return

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            print(f"Could not load open positions: {error}")
            return

        for symbol, position in saved_positions.items():
            try:
                entry_time_text = position.get("entry_time")

                entry_time = (
                    datetime.fromisoformat(entry_time_text)
                    if entry_time_text
                    else datetime.now()
                )

                stop_loss = float(position["stop_loss"])

                self.open_positions[symbol] = {
                    "symbol": str(
                        position.get("symbol", symbol)
                    ),
                    "quantity": int(position["quantity"]),
                    "entry_price": float(
                        position["entry_price"]
                    ),
                    "stop_loss": stop_loss,
                    "initial_stop_loss": float(
                        position.get(
                            "initial_stop_loss",
                            stop_loss,
                        )
                    ),
                    "target": float(position["target"]),
                    "entry_time": entry_time,
                }

            except (
                KeyError,
                TypeError,
                ValueError,
            ) as error:
                print(
                    f"Skipping invalid position "
                    f"{symbol}: {error}"
                )

    def _save_open_positions(self) -> None:
        data: Dict[str, Dict[str, Any]] = {}

        for symbol, position in self.open_positions.items():
            data[symbol] = {
                "symbol": position["symbol"],
                "quantity": position["quantity"],
                "entry_price": position["entry_price"],
                "stop_loss": position["stop_loss"],
                "initial_stop_loss": position[
                    "initial_stop_loss"
                ],
                "target": position["target"],
                "entry_time": position[
                    "entry_time"
                ].isoformat(),
            }

        temporary_file = self.positions_file.with_suffix(".tmp")

        temporary_file.write_text(
            json.dumps(data, indent=4),
            encoding="utf-8",
        )

        temporary_file.replace(self.positions_file)

    def _recalculate_cash_balance(self) -> None:
        realized_pnl = self.total_realized_pnl()

        invested_amount = sum(
            position["quantity"] * position["entry_price"]
            for position in self.open_positions.values()
        )

        self.cash_balance = (
            self.starting_balance
            + realized_pnl
            - invested_amount
        )

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

        if entry_price <= 0:
            print("Entry price must be greater than zero.")
            return False

        if stop_loss >= entry_price:
            print(
                "Stop loss must be below entry price "
                "for a long trade."
            )
            return False

        if target <= entry_price:
            print(
                "Target must be above entry price "
                "for a long trade."
            )
            return False

        trade_value = quantity * entry_price

        if trade_value > self.cash_balance:
            print(
                "Insufficient virtual balance. "
                f"Required: ₹{trade_value:.2f}, "
                f"Available: ₹{self.cash_balance:.2f}"
            )
            return False

        position = {
            "symbol": symbol,
            "quantity": int(quantity),
            "entry_price": float(entry_price),
            "stop_loss": float(stop_loss),
            "initial_stop_loss": float(stop_loss),
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

        if exit_price <= 0:
            print("Exit price must be greater than zero.")
            return None

        quantity = int(position["quantity"])
        entry_price = float(position["entry_price"])

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
            "stop_loss": float(position["stop_loss"]),
            "target": float(position["target"]),
            "pnl": float(pnl),
            "exit_reason": str(exit_reason),
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

    def check_exit(
        self,
        symbol: str,
        current_price: float,
    ) -> Optional[Dict[str, Any]]:
        position = self.open_positions.get(symbol)

        if position is None:
            return None

        current_price = float(current_price)

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

        risk_per_share = (
            position["entry_price"]
            - position["initial_stop_loss"]
        )

        if risk_per_share <= 0:
            return None

        new_stop = current_price - risk_per_share

        if new_stop > position["stop_loss"]:
            position["stop_loss"] = float(new_stop)
            self._save_open_positions()

            print(
                f"{symbol}: Trailing Stop moved to "
                f"₹{new_stop:.2f}"
            )

        return None

    def _write_trade_to_log(
        self,
        trade: Dict[str, Any],
    ) -> None:
        with self.log_file.open(
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

    def get_open_position(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        position = self.open_positions.get(symbol)

        if position is None:
            return None

        return position.copy()

    def get_open_positions(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        return {
            symbol: position.copy()
            for symbol, position
            in self.open_positions.items()
        }

    def total_realized_pnl(self) -> float:
        return sum(
            float(trade["pnl"])
            for trade in self.closed_trades
        )

    def account_summary(self) -> Dict[str, Any]:
        return {
            "starting_balance": round(
                self.starting_balance,
                2,
            ),
            "cash_balance": round(
                self.cash_balance,
                2,
            ),
            "open_positions": len(self.open_positions),
            "closed_trades": len(self.closed_trades),
            "realized_pnl": round(
                self.total_realized_pnl(),
                2,
            ),
        }


if __name__ == "__main__":
    trader = PaperTrader()

    print("\nAccount summary:")
    print(trader.account_summary())

    print("\nOpen positions:")
    print(trader.get_open_positions())
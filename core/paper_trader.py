import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from analytics.trade_journal import TradeJournal


class PaperTrader:
    def __init__(
        self,
        starting_balance: float = 100000.0,
        log_file: str = "logs/paper_trades.csv",
        positions_file: str = "logs/open_positions.json",
        journal_file: str = "logs/trade_journal.json",
    ) -> None:
        self.starting_balance = float(
            starting_balance
        )
        self.cash_balance = float(
            starting_balance
        )

        self.log_file = Path(
            log_file
        )
        self.positions_file = Path(
            positions_file
        )

        self.trade_journal = TradeJournal(
            journal_file=journal_file,
        )

        self.open_positions: Dict[
            str,
            Dict[str, Any],
        ] = {}

        self.closed_trades: List[
            Dict[str, Any]
        ] = []

        self._prepare_files()
        self._load_closed_trades()
        self._load_open_positions()
        self._recalculate_cash_balance()

    def _prepare_files(
        self,
    ) -> None:
        self.log_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.positions_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.log_file.exists():
            with self.log_file.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as file:
                writer = csv.writer(
                    file
                )

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

    def _load_closed_trades(
        self,
    ) -> None:
        self.closed_trades = []

        try:
            with self.log_file.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as file:
                reader = csv.DictReader(
                    file
                )

                for row in reader:
                    if not row.get(
                        "symbol"
                    ):
                        continue

                    try:
                        trade = {
                            "entry_time": (
                                datetime.fromisoformat(
                                    row[
                                        "entry_time"
                                    ]
                                )
                            ),
                            "exit_time": (
                                datetime.fromisoformat(
                                    row[
                                        "exit_time"
                                    ]
                                )
                            ),
                            "symbol": row[
                                "symbol"
                            ],
                            "quantity": int(
                                float(
                                    row[
                                        "quantity"
                                    ]
                                )
                            ),
                            "entry_price": float(
                                row[
                                    "entry_price"
                                ]
                            ),
                            "exit_price": float(
                                row[
                                    "exit_price"
                                ]
                            ),
                            "stop_loss": float(
                                row[
                                    "stop_loss"
                                ]
                            ),
                            "target": float(
                                row[
                                    "target"
                                ]
                            ),
                            "pnl": float(
                                row[
                                    "pnl"
                                ]
                            ),
                            "exit_reason": row[
                                "exit_reason"
                            ],
                        }

                        self.closed_trades.append(
                            trade
                        )

                    except (
                        KeyError,
                        TypeError,
                        ValueError,
                    ) as error:
                        print(
                            "Skipping invalid "
                            "trade-log row: "
                            f"{error}"
                        )

        except OSError as error:
            print(
                "Could not load closed "
                f"trades: {error}"
            )

    def _load_open_positions(
        self,
    ) -> None:
        self.open_positions = {}

        if (
            not self.positions_file.exists()
            or self.positions_file.stat().st_size
            == 0
        ):
            return

        try:
            raw_text = (
                self.positions_file.read_text(
                    encoding="utf-8"
                ).strip()
            )

            if not raw_text:
                return

            saved_positions = json.loads(
                raw_text
            )

            if not isinstance(
                saved_positions,
                dict,
            ):
                print(
                    "Open positions file has "
                    "an invalid format."
                )
                return

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            print(
                "Could not load open "
                f"positions: {error}"
            )
            return

        for symbol, position in (
            saved_positions.items()
        ):
            try:
                entry_time_text = (
                    position.get(
                        "entry_time"
                    )
                )

                entry_time = (
                    datetime.fromisoformat(
                        entry_time_text
                    )
                    if entry_time_text
                    else datetime.now()
                )

                stop_loss = float(
                    position[
                        "stop_loss"
                    ]
                )

                current_quantity = int(
                    position[
                        "quantity"
                    ]
                )

                initial_quantity = int(
                    position.get(
                        "initial_quantity",
                        current_quantity,
                    )
                )

                partial_exits = (
                    position.get(
                        "partial_exits",
                        [],
                    )
                )

                if not isinstance(
                    partial_exits,
                    list,
                ):
                    partial_exits = []

                self.open_positions[
                    str(symbol).upper()
                ] = {
                    "symbol": str(
                        position.get(
                            "symbol",
                            symbol,
                        )
                    ).upper(),
                    "quantity": (
                        current_quantity
                    ),
                    "initial_quantity": (
                        initial_quantity
                    ),
                    "entry_price": float(
                        position[
                            "entry_price"
                        ]
                    ),
                    "stop_loss": (
                        stop_loss
                    ),
                    "initial_stop_loss": float(
                        position.get(
                            "initial_stop_loss",
                            stop_loss,
                        )
                    ),
                    "target": float(
                        position[
                            "target"
                        ]
                    ),
                    "entry_time": (
                        entry_time
                    ),
                    "partial_realized_pnl": float(
                        position.get(
                            "partial_realized_pnl",
                            0.0,
                        )
                        or 0.0
                    ),
                    "partial_exit_done": bool(
                        position.get(
                            "partial_exit_done",
                            False,
                        )
                    ),
                    "partial_exits": (
                        partial_exits
                    ),
                    "metadata": position.get(
                        "metadata",
                        {},
                    ),
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

    def _save_open_positions(
        self,
    ) -> None:
        data: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for symbol, position in (
            self.open_positions.items()
        ):
            data[symbol] = {
                "symbol": position[
                    "symbol"
                ],
                "quantity": position[
                    "quantity"
                ],
                "initial_quantity": (
                    position.get(
                        "initial_quantity",
                        position[
                            "quantity"
                        ],
                    )
                ),
                "entry_price": position[
                    "entry_price"
                ],
                "stop_loss": position[
                    "stop_loss"
                ],
                "initial_stop_loss": (
                    position[
                        "initial_stop_loss"
                    ]
                ),
                "target": position[
                    "target"
                ],
                "entry_time": position[
                    "entry_time"
                ].isoformat(),
                "partial_realized_pnl": (
                    position.get(
                        "partial_realized_pnl",
                        0.0,
                    )
                ),
                "partial_exit_done": (
                    position.get(
                        "partial_exit_done",
                        False,
                    )
                ),
                "partial_exits": (
                    position.get(
                        "partial_exits",
                        [],
                    )
                ),
                "metadata": position.get(
                    "metadata",
                    {},
                ),
            }

        temporary_file = (
            self.positions_file.with_suffix(
                ".tmp"
            )
        )

        temporary_file.write_text(
            json.dumps(
                data,
                indent=4,
            ),
            encoding="utf-8",
        )

        temporary_file.replace(
            self.positions_file
        )

    def _recalculate_cash_balance(
        self,
    ) -> None:
        realized_pnl = (
            self.total_realized_pnl()
        )

        partial_realized_pnl = sum(
            float(
                position.get(
                    "partial_realized_pnl",
                    0.0,
                )
                or 0.0
            )
            for position in (
                self.open_positions.values()
            )
        )

        invested_amount = sum(
            int(
                position[
                    "quantity"
                ]
            )
            * float(
                position[
                    "entry_price"
                ]
            )
            for position in (
                self.open_positions.values()
            )
        )

        self.cash_balance = (
            self.starting_balance
            + realized_pnl
            + partial_realized_pnl
            - invested_amount
        )

    def open_trade(
        self,
        symbol: str,
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
                "Paper trade requires "
                "a symbol."
            )
            return False

        if symbol in self.open_positions:
            print(
                f"{symbol}: position "
                "already open."
            )
            return False

        if quantity <= 0:
            print(
                "Quantity must be "
                "greater than zero."
            )
            return False

        if entry_price <= 0:
            print(
                "Entry price must be "
                "greater than zero."
            )
            return False

        if stop_loss <= 0:
            print(
                "Stop loss must be "
                "greater than zero."
            )
            return False

        if stop_loss >= entry_price:
            print(
                "Stop loss must be below "
                "entry price for a long trade."
            )
            return False

        if target <= entry_price:
            print(
                "Target must be above "
                "entry price for a long trade."
            )
            return False

        trade_value = (
            quantity
            * entry_price
        )

        if trade_value > self.cash_balance:
            print(
                "Insufficient virtual balance. "
                f"Required: ₹{trade_value:.2f}, "
                f"Available: "
                f"₹{self.cash_balance:.2f}"
            )
            return False

        position = {
            "symbol": symbol,
            "quantity": int(
                quantity
            ),
            "initial_quantity": int(
                quantity
            ),
            "entry_price": float(
                entry_price
            ),
            "stop_loss": float(
                stop_loss
            ),
            "initial_stop_loss": float(
                stop_loss
            ),
            "target": float(
                target
            ),
            "entry_time": datetime.now(),
            "partial_realized_pnl": 0.0,
            "partial_exit_done": False,
            "partial_exits": [],
            "metadata": metadata or {},
        }

        self.open_positions[
            symbol
        ] = position

        self.cash_balance -= (
            trade_value
        )

        self._save_open_positions()

        print(
            f"Paper BUY: {symbol} | "
            f"Qty: {quantity} | "
            f"Entry: ₹{entry_price:.2f}"
        )

        return True

    def update_stop_loss(
        self,
        symbol: str,
        stop_loss: float,
    ) -> bool:
        symbol = str(
            symbol
        ).strip().upper()

        position = (
            self.open_positions.get(
                symbol
            )
        )

        if position is None:
            print(
                f"{symbol}: no open "
                "paper position."
            )
            return False

        try:
            new_stop_loss = float(
                stop_loss
            )

        except (
            TypeError,
            ValueError,
        ):
            print(
                f"{symbol}: invalid "
                "stop-loss value."
            )
            return False

        if new_stop_loss <= 0:
            print(
                f"{symbol}: stop loss "
                "must be positive."
            )
            return False

        current_stop_loss = float(
            position[
                "stop_loss"
            ]
        )

        if new_stop_loss <= (
            current_stop_loss
        ):
            return False

        target = float(
            position[
                "target"
            ]
        )

        if new_stop_loss >= target:
            print(
                f"{symbol}: stop loss "
                "must remain below target."
            )
            return False

        position[
            "stop_loss"
        ] = new_stop_loss

        self._save_open_positions()

        print(
            f"{symbol}: Paper stop "
            f"updated "
            f"₹{current_stop_loss:.2f} "
            f"→ ₹{new_stop_loss:.2f}"
        )

        return True

    def partial_close_trade(
        self,
        symbol: str,
        exit_price: float,
        quantity: int,
        exit_reason: str = (
            "PARTIAL_TARGET"
        ),
    ) -> Optional[
        Dict[str, Any]
    ]:
        symbol = str(
            symbol
        ).strip().upper()

        position = (
            self.open_positions.get(
                symbol
            )
        )

        if position is None:
            print(
                f"{symbol}: no open "
                "paper position."
            )
            return None

        if exit_price <= 0:
            print(
                "Exit price must be "
                "greater than zero."
            )
            return None

        current_quantity = int(
            position[
                "quantity"
            ]
        )

        partial_quantity = int(
            quantity
        )

        if partial_quantity <= 0:
            print(
                f"{symbol}: partial quantity "
                "must be positive."
            )
            return None

        if partial_quantity >= (
            current_quantity
        ):
            print(
                f"{symbol}: partial quantity "
                "must be smaller than the "
                "open quantity."
            )
            return None

        exit_price = float(
            exit_price
        )

        entry_price = float(
            position[
                "entry_price"
            ]
        )

        exit_value = (
            partial_quantity
            * exit_price
        )

        partial_pnl = (
            exit_price
            - entry_price
        ) * partial_quantity

        position[
            "quantity"
        ] = (
            current_quantity
            - partial_quantity
        )

        position[
            "partial_realized_pnl"
        ] = float(
            position.get(
                "partial_realized_pnl",
                0.0,
            )
            or 0.0
        ) + partial_pnl

        position[
            "partial_exit_done"
        ] = True

        partial_exit = {
            "exit_time": (
                datetime.now().isoformat()
            ),
            "quantity": (
                partial_quantity
            ),
            "exit_price": (
                exit_price
            ),
            "pnl": float(
                partial_pnl
            ),
            "exit_reason": str(
                exit_reason
            ),
        }

        position.setdefault(
            "partial_exits",
            [],
        ).append(
            partial_exit
        )

        self.cash_balance += (
            exit_value
        )

        self._save_open_positions()

        print(
            f"Paper PARTIAL SELL: "
            f"{symbol} | "
            f"Qty: {partial_quantity} | "
            f"Remaining: "
            f"{position['quantity']} | "
            f"Exit: ₹{exit_price:.2f} | "
            f"P&L: ₹{partial_pnl:.2f}"
        )

        return {
            "symbol": symbol,
            "quantity": (
                partial_quantity
            ),
            "remaining_quantity": int(
                position[
                    "quantity"
                ]
            ),
            "exit_price": (
                exit_price
            ),
            "partial_pnl": float(
                partial_pnl
            ),
            "total_partial_pnl": float(
                position[
                    "partial_realized_pnl"
                ]
            ),
            "exit_reason": str(
                exit_reason
            ),
        }

    def close_trade(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
    ) -> Optional[
        Dict[str, Any]
    ]:
        symbol = str(
            symbol
        ).strip().upper()

        position = (
            self.open_positions.get(
                symbol
            )
        )

        if position is None:
            print(
                f"{symbol}: no open "
                "paper position."
            )
            return None

        if exit_price <= 0:
            print(
                "Exit price must be "
                "greater than zero."
            )
            return None

        remaining_quantity = int(
            position[
                "quantity"
            ]
        )

        initial_quantity = int(
            position.get(
                "initial_quantity",
                remaining_quantity,
            )
        )

        entry_price = float(
            position[
                "entry_price"
            ]
        )

        exit_price = float(
            exit_price
        )

        exit_value = (
            remaining_quantity
            * exit_price
        )

        final_leg_pnl = (
            exit_price
            - entry_price
        ) * remaining_quantity

        partial_realized_pnl = float(
            position.get(
                "partial_realized_pnl",
                0.0,
            )
            or 0.0
        )

        total_pnl = (
            partial_realized_pnl
            + final_leg_pnl
        )

        self.cash_balance += (
            exit_value
        )

        trade = {
            "entry_time": position[
                "entry_time"
            ],
            "exit_time": datetime.now(),
            "symbol": symbol,
            "quantity": initial_quantity,
            "remaining_quantity": (
                remaining_quantity
            ),
            "entry_price": (
                entry_price
            ),
            "exit_price": (
                exit_price
            ),
            "stop_loss": float(
                position[
                    "stop_loss"
                ]
            ),
            "target": float(
                position[
                    "target"
                ]
            ),
            "partial_realized_pnl": (
                partial_realized_pnl
            ),
            "final_leg_pnl": float(
                final_leg_pnl
            ),
            "partial_exits": (
                position.get(
                    "partial_exits",
                    [],
                )
            ),
            "pnl": float(
                total_pnl
            ),
            "exit_reason": str(
                exit_reason
            ),
            "metadata": position.get(
                "metadata",
                {},
            ),
        }

        self.closed_trades.append(
            trade
        )

        del self.open_positions[
            symbol
        ]

        self._save_open_positions()
        self._write_trade_to_log(
            trade
        )

        metadata = trade.get(
            "metadata",
            {},
        )

        claude_review = metadata.get(
            "claude_review",
            {
                "approved": metadata.get(
                    "claude_approved",
                    False,
                ),
                "confidence": metadata.get(
                    "claude_confidence",
                    0,
                ),
                "reason": metadata.get(
                    "claude_reason",
                    "",
                ),
            },
        )

        self.trade_journal.add_entry(
            trade=trade,
            strategy=metadata.get(
                "strategy",
                "UNKNOWN",
            ),
            claude_review=(
                claude_review
            ),
            indicators=metadata.get(
                "indicators",
                {},
            ),
            market_condition=(
                metadata.get(
                    "market_condition",
                    "UNKNOWN",
                )
            ),
            market_regime=metadata.get(
                "market_regime",
                {},
            ),
            market_intelligence=(
                metadata.get(
                    "market_intelligence",
                    {},
                )
            ),
            market_brain=metadata.get(
                "market_brain",
                {},
            ),
            position_multiplier=(
                metadata.get(
                    "position_multiplier",
                    1.0,
                )
            ),
            strategy_score=metadata.get(
                "strategy_score",
                0,
            ),
        )

        print(
            f"Paper SELL: {symbol} | "
            f"Remaining Qty: "
            f"{remaining_quantity} | "
            f"Exit: ₹{exit_price:.2f} | "
            f"Total P&L: "
            f"₹{total_pnl:.2f}"
        )

        return trade

    def check_exit(
        self,
        symbol: str,
        current_price: float,
    ) -> Optional[
        Dict[str, Any]
    ]:
        symbol = str(
            symbol
        ).strip().upper()

        position = (
            self.open_positions.get(
                symbol
            )
        )

        if position is None:
            return None

        current_price = float(
            current_price
        )

        if current_price <= float(
            position[
                "stop_loss"
            ]
        ):
            return self.close_trade(
                symbol=symbol,
                exit_price=current_price,
                exit_reason=(
                    "STOP_LOSS"
                ),
            )

        if current_price >= float(
            position[
                "target"
            ]
        ):
            return self.close_trade(
                symbol=symbol,
                exit_price=current_price,
                exit_reason="TARGET",
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
            writer = csv.writer(
                file
            )

            writer.writerow(
                [
                    trade[
                        "entry_time"
                    ].isoformat(),
                    trade[
                        "exit_time"
                    ].isoformat(),
                    trade[
                        "symbol"
                    ],
                    trade[
                        "quantity"
                    ],
                    trade[
                        "entry_price"
                    ],
                    trade[
                        "exit_price"
                    ],
                    trade[
                        "stop_loss"
                    ],
                    trade[
                        "target"
                    ],
                    trade[
                        "pnl"
                    ],
                    trade[
                        "exit_reason"
                    ],
                ]
            )

    def get_open_position(
        self,
        symbol: str,
    ) -> Optional[
        Dict[str, Any]
    ]:
        symbol = str(
            symbol
        ).strip().upper()

        position = (
            self.open_positions.get(
                symbol
            )
        )

        if position is None:
            return None

        return position.copy()

    def get_open_positions(
        self,
    ) -> Dict[
        str,
        Dict[str, Any],
    ]:
        return {
            symbol: position.copy()
            for symbol, position
            in self.open_positions.items()
        }

    def total_realized_pnl(
        self,
    ) -> float:
        return sum(
            float(
                trade[
                    "pnl"
                ]
            )
            for trade in (
                self.closed_trades
            )
        )

    def account_summary(
        self,
    ) -> Dict[str, Any]:
        open_partial_pnl = sum(
            float(
                position.get(
                    "partial_realized_pnl",
                    0.0,
                )
                or 0.0
            )
            for position in (
                self.open_positions.values()
            )
        )

        return {
            "starting_balance": round(
                self.starting_balance,
                2,
            ),
            "cash_balance": round(
                self.cash_balance,
                2,
            ),
            "open_positions": len(
                self.open_positions
            ),
            "closed_trades": len(
                self.closed_trades
            ),
            "realized_pnl": round(
                self.total_realized_pnl(),
                2,
            ),
            "open_partial_pnl": round(
                open_partial_pnl,
                2,
            ),
        }


if __name__ == "__main__":
    trader = PaperTrader()

    print(
        "\nAccount summary:"
    )

    print(
        trader.account_summary()
    )

    print(
        "\nOpen positions:"
    )

    print(
        trader.get_open_positions()
    )
from typing import Any, Dict, List

from core.paper_trader import PaperTrader
from execution.sell_execution import SellExecution
from execution.live_execution_controller import (
    LiveExecutionController,
)


def monitor_positions(
    market: MarketData,
    trader: PaperTrader,
    lifecycle: TradeLifecycle,
    live_execution_controller: LiveExecutionController,
    safety_manager: SafetyManager,
) -> None:
    symbols = list(
        trader.open_positions.keys()
    )

    for symbol in symbols:
        quote = market.get_live_quote(
            symbol
        )

        if (
            not quote
            or quote.get("last_price")
            is None
        ):
            print(
                f"{symbol}: monitoring quote "
                "unavailable."
            )
            continue

        current_price = float(
            quote["last_price"]
        )

        lifecycle_update = (
            lifecycle.update_price(
                symbol=symbol,
                current_price=current_price,
            )
        )

        if not lifecycle_update.get(
            "updated",
            False,
        ):
            print(
                lifecycle_update.get(
                    "reason",
                    f"{symbol}: lifecycle "
                    "update failed.",
                )
            )
            continue

        # -------------------------
        # Synchronize stop loss
        # -------------------------

        lifecycle_stop = float(
            lifecycle_update.get(
                "stop_loss",
                0.0,
            )
            or 0.0
        )

        paper_position = (
            trader.get_open_position(
                symbol
            )
        )

        if (
            paper_position is not None
            and lifecycle_stop
            > float(
                paper_position[
                    "stop_loss"
                ]
            )
        ):
            trader.update_stop_loss(
                symbol=symbol,
                stop_loss=lifecycle_stop,
            )

        # -------------------------
        # Execute partial exit
        # -------------------------

        partial_exit = (
            lifecycle_update.get(
                "partial_exit",
                {},
            )
        )

        if (
            isinstance(
                partial_exit,
                dict,
            )
            and partial_exit.get(
                "execute",
                False,
            )
        ):
            partial_quantity = int(
                partial_exit.get(
                    "quantity",
                    0,
                )
            )

            partial_price = float(
                partial_exit.get(
                    "exit_price",
                    current_price,
                )
            )

            partial_reason = str(
                partial_exit.get(
                    "reason",
                    "PARTIAL_TARGET",
                )
            )

            sell_result = execute_paper_sell(
                controller=(
                    live_execution_controller
                ),
                symbol=symbol,
                quantity=partial_quantity,
                price=partial_price,
                reason=partial_reason,
                metadata={
                    "partial_exit": True,
                },
            )

            if not sell_result.get(
                "success",
                False,
            ):
                print(
                    f"{symbol}: partial SELL "
                    "execution registration failed."
                )
                continue

            partial_result = (
                trader.partial_close_trade(
                    symbol=symbol,
                    exit_price=partial_price,
                    quantity=partial_quantity,
                    exit_reason=partial_reason,
                )
            )

            if partial_result is None:
                print(
                    f"{symbol}: partial exit "
                    "execution failed."
                )

            else:
                print(
                    f"{symbol}: partial profit "
                    f"booked | Qty: "
                    f"{partial_result['quantity']} | "
                    f"Remaining: "
                    f"{partial_result['remaining_quantity']} | "
                    f"Partial P&L: ₹"
                    f"{partial_result['partial_pnl']:.2f}"
                )

        print(
            f"{symbol} | "
            f"Current: ₹{current_price:.2f} | "
            f"Remaining Qty: "
            f"{lifecycle_update.get('remaining_quantity', 0)} | "
            f"Unrealized P&L: ₹"
            f"{lifecycle_update.get('unrealized_pnl', 0.0):.2f} | "
            f"Partial P&L: ₹"
            f"{lifecycle_update.get('partial_realized_pnl', 0.0):.2f} | "
            f"Stop: ₹{lifecycle_stop:.2f}"
        )

        # -------------------------
        # Check complete exit
        # -------------------------

        paper_position = (
            trader.get_open_position(
                symbol
            )
        )

        if paper_position is None:
            continue

        exit_signal = str(
            lifecycle_update.get(
                "exit_signal",
                "",
            )
            or ""
        ).strip().upper()

        if not exit_signal:
            if current_price <= float(
                paper_position["stop_loss"]
            ):
                exit_signal = "STOP_LOSS"

            elif current_price >= float(
                paper_position["target"]
            ):
                exit_signal = "TARGET"

        if not exit_signal:
            continue

        remaining_quantity = int(
            paper_position.get(
                "quantity",
                0,
            )
            or 0
        )

        if remaining_quantity <= 0:
            print(
                f"{symbol}: invalid remaining "
                "quantity for full exit."
            )
            continue

        sell_result = execute_paper_sell(
            controller=(
                live_execution_controller
            ),
            symbol=symbol,
            quantity=remaining_quantity,
            price=current_price,
            reason=exit_signal,
            metadata={
                "partial_exit": False,
                "full_exit": True,
            },
        )

        if not sell_result.get(
            "success",
            False,
        ):
            print(
                f"{symbol}: full SELL execution "
                "registration failed."
            )
            continue

        closed_trade = trader.close_trade(
            symbol=symbol,
            exit_price=current_price,
            exit_reason=exit_signal,
        )

        if closed_trade is None:
            print(
                f"{symbol}: paper full exit "
                "failed after SELL registration."
            )
            continue

        safety_manager.record_trade_closed(
            pnl=float(
                closed_trade.get(
                    "pnl",
                    0.0,
                )
                or 0.0
            )
        )

        if lifecycle.has_open_trade(
            symbol
        ):
            lifecycle.close_trade(
                symbol=symbol,
                exit_price=current_price,
                exit_reason=exit_signal,
            )

        sell_order = (
            sell_result.get(
                "order",
                {},
            )
            or {}
        )

        print(
            f"{symbol}: full SELL registered | "
            f"Reason: {exit_signal} | "
            f"Qty: {remaining_quantity} | "
            f"Status: "
            f"{sell_order.get('status', 'UNKNOWN')} | "
            f"Internal Order ID: "
            f"{sell_order.get('internal_order_id')}"
        )
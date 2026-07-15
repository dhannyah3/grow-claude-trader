"""
Restart recovery followed by full SELL exit.

This verifies that:
- a position persists before restart;
- PaperTrader restores it;
- TradeLifecycle is rebuilt;
- the restored position can exit safely;
- SELL execution is registered in PAPER mode.

No real Groww order is placed.
"""

from pathlib import Path

from core.paper_trader import PaperTrader
from core.trade_lifecycle import TradeLifecycle
from execution.live_execution_controller import (
    LiveExecutionController,
)
from execution.order_executor import OrderExecutor
from execution.order_manager import OrderManager
from execution.position_sync import PositionSynchronizer
from execution.sell_execution import execute_paper_sell


TRADES_FILE = Path(
    "logs/test_restart_exit_trades.csv"
)

POSITIONS_FILE = Path(
    "logs/test_restart_exit_positions.json"
)

JOURNAL_FILE = Path(
    "logs/test_restart_exit_journal.json"
)


def remove_old_test_files() -> None:
    for path in (
        TRADES_FILE,
        POSITIONS_FILE,
        JOURNAL_FILE,
    ):
        if path.exists():
            path.unlink()


def build_trader() -> PaperTrader:
    return PaperTrader(
        starting_balance=100000.0,
        log_file=str(TRADES_FILE),
        positions_file=str(
            POSITIONS_FILE
        ),
        journal_file=str(
            JOURNAL_FILE
        ),
    )


def rebuild_lifecycle(
    trader: PaperTrader,
) -> TradeLifecycle:
    lifecycle = TradeLifecycle()

    for symbol, position in (
        trader.open_positions.items()
    ):
        metadata = position.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        opened = lifecycle.open_trade(
            symbol=symbol,
            strategy=str(
                metadata.get(
                    "strategy",
                    "UNKNOWN",
                )
            ),
            quantity=int(
                position["quantity"]
            ),
            entry_price=float(
                position["entry_price"]
            ),
            stop_loss=float(
                position["stop_loss"]
            ),
            target=float(
                position["target"]
            ),
            metadata=metadata,
        )

        assert opened is True

    return lifecycle


def main() -> None:
    print("=" * 60)
    print("RESTART EXIT RECOVERY TEST")
    print("=" * 60)

    remove_old_test_files()

    # First runtime: open and persist a position.
    first_trader = build_trader()

    opened = first_trader.open_trade(
        symbol="TCS",
        quantity=5,
        entry_price=2200.0,
        stop_loss=2180.0,
        target=2225.0,
        metadata={
            "strategy": "ORB_BREAKOUT",
            "market_condition": "TRENDING",
            "paper_trade": True,
            "internal_order_id": (
                "RECOVERY-BUY-001"
            ),
        },
    )

    assert opened is True
    assert (
        first_trader.get_open_position(
            "TCS"
        )
        is not None
    )

    print(
        "First runtime: position "
        "opened and persisted."
    )

    # Simulated restart.
    restarted_trader = build_trader()

    restored_position = (
        restarted_trader
        .get_open_position(
            "TCS"
        )
    )

    assert restored_position is not None
    assert restored_position[
        "quantity"
    ] == 5

    lifecycle = rebuild_lifecycle(
        restarted_trader
    )

    assert lifecycle.has_open_trade(
        "TCS"
    )

    print(
        "Restarted runtime: position "
        "and lifecycle restored."
    )

    # Build safe execution layer.
    executor = OrderExecutor(
        groww_client=None,
        live_trading=False,
    )

    order_manager = OrderManager()
    position_sync = PositionSynchronizer()

    controller = LiveExecutionController(
        executor=executor,
        order_manager=order_manager,
        position_sync=position_sync,
    )

    exit_price = 2225.0
    exit_reason = "TARGET_AFTER_RESTART"

    sell_result = execute_paper_sell(
        controller=controller,
        symbol="TCS",
        quantity=5,
        price=exit_price,
        reason=exit_reason,
        metadata={
            "full_exit": True,
            "restart_recovery": True,
        },
    )

    assert sell_result.get(
        "success"
    ) is True

    execution = sell_result.get(
        "execution",
        {},
    )

    order = sell_result.get(
        "order",
        {},
    )

    assert execution.get(
        "mode"
    ) == "PAPER"

    assert execution.get(
        "status"
    ) == "SIMULATED"

    assert execution.get(
        "side"
    ) == "SELL"

    assert order.get(
        "internal_order_id"
    )

    closed_trade = (
        restarted_trader.close_trade(
            symbol="TCS",
            exit_price=exit_price,
            exit_reason=exit_reason,
        )
    )

    assert closed_trade is not None
    assert closed_trade[
        "pnl"
    ] == 125.0

    if lifecycle.has_open_trade(
        "TCS"
    ):
        lifecycle.close_trade(
            symbol="TCS",
            exit_price=exit_price,
            exit_reason=exit_reason,
        )

    assert (
        restarted_trader
        .get_open_position(
            "TCS"
        )
        is None
    )

    assert not lifecycle.has_open_trade(
        "TCS"
    )

    print("\nRecovered SELL")
    print("-" * 60)
    print(
        f"Status             : "
        f"{execution['status']}"
    )
    print(
        f"Internal Order ID  : "
        f"{order['internal_order_id']}"
    )
    print(
        f"Realized P&L       : "
        f"₹{closed_trade['pnl']:.2f}"
    )

    print(
        "\nRESTART EXIT RECOVERY "
        "test passed."
    )


if __name__ == "__main__":
    main()
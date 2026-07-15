"""
Emergency shutdown integration test.

Verifies that:
- an open paper position exists;
- SafetyManager kill switch triggers shutdown;
- the position exits through simulated SELL execution;
- PaperTrader and TradeLifecycle both close cleanly.

No real Groww order is placed.
"""

from pathlib import Path

from core.paper_trader import PaperTrader
from core.safety_manager import SafetyManager
from core.trade_lifecycle import TradeLifecycle
from execution.live_execution_controller import (
    LiveExecutionController,
)
from execution.order_executor import OrderExecutor
from execution.order_manager import OrderManager
from execution.position_sync import PositionSynchronizer
from execution.sell_execution import execute_paper_sell


TRADES_FILE = Path(
    "logs/test_emergency_shutdown_trades.csv"
)

POSITIONS_FILE = Path(
    "logs/test_emergency_shutdown_positions.json"
)

JOURNAL_FILE = Path(
    "logs/test_emergency_shutdown_journal.json"
)


def remove_old_test_files() -> None:
    for path in (
        TRADES_FILE,
        POSITIONS_FILE,
        JOURNAL_FILE,
    ):
        if path.exists():
            path.unlink()


def main() -> None:
    print("=" * 60)
    print("EMERGENCY SHUTDOWN INTEGRATION TEST")
    print("=" * 60)

    remove_old_test_files()

    trader = PaperTrader(
        starting_balance=100000.0,
        log_file=str(TRADES_FILE),
        positions_file=str(
            POSITIONS_FILE
        ),
        journal_file=str(
            JOURNAL_FILE
        ),
    )

    lifecycle = TradeLifecycle()

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

    safety = SafetyManager(
        max_trades_per_day=5,
        max_daily_loss=2000.0,
        max_consecutive_losses=3,
    )

    symbol = "RELIANCE"
    quantity = 10
    entry_price = 1500.0
    exit_price = 1490.0

    opened = trader.open_trade(
        symbol=symbol,
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=1485.0,
        target=1530.0,
        metadata={
            "strategy": "ORB_BREAKOUT",
            "market_condition": "TRENDING",
            "paper_trade": True,
        },
    )

    assert opened is True

    lifecycle_opened = lifecycle.open_trade(
        symbol=symbol,
        strategy="ORB_BREAKOUT",
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=1485.0,
        target=1530.0,
        metadata={
            "paper_trade": True,
        },
    )

    assert lifecycle_opened is True

    safety.record_trade_opened()

    safety.enable_kill_switch(
        "Emergency shutdown test."
    )

    shutdown = safety.should_shutdown(
        current_daily_pnl=(
            trader.total_realized_pnl()
        )
    )

    assert shutdown["shutdown"] is True
    assert (
        shutdown["reason"]
        == "Emergency shutdown test."
    )

    position = trader.get_open_position(
        symbol
    )

    assert position is not None

    sell_result = execute_paper_sell(
        controller=controller,
        symbol=symbol,
        quantity=int(
            position["quantity"]
        ),
        price=exit_price,
        reason="SAFETY_SHUTDOWN",
        metadata={
            "full_exit": True,
            "emergency_shutdown": True,
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

    closed_trade = trader.close_trade(
        symbol=symbol,
        exit_price=exit_price,
        exit_reason="SAFETY_SHUTDOWN",
    )

    assert closed_trade is not None

    safety.record_trade_closed(
        pnl=float(
            closed_trade["pnl"]
        )
    )

    if lifecycle.has_open_trade(
        symbol
    ):
        lifecycle.close_trade(
            symbol=symbol,
            exit_price=exit_price,
            exit_reason="SAFETY_SHUTDOWN",
        )

    assert trader.get_open_position(
        symbol
    ) is None

    assert not lifecycle.has_open_trade(
        symbol
    )

    assert closed_trade["pnl"] == -100.0

    print("\nEmergency SELL")
    print("-" * 60)
    print(
        f"Shutdown Reason    : "
        f"{shutdown['reason']}"
    )
    print(
        f"Execution Status   : "
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
        "\nEMERGENCY SHUTDOWN "
        "integration test passed."
    )


if __name__ == "__main__":
    main()
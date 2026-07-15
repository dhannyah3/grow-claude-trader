"""
Controlled integration test for a complete SELL exit.

No real Groww order is placed.
Everything runs in PAPER mode.
"""

from core.paper_trader import PaperTrader
from execution.live_execution_controller import (
    LiveExecutionController,
)
from execution.order_executor import OrderExecutor
from execution.order_manager import OrderManager
from execution.position_sync import PositionSynchronizer
from execution.sell_execution import execute_paper_sell


def main() -> None:
    print("=" * 60)
    print("FULL SELL EXECUTION INTEGRATION TEST")
    print("=" * 60)

    trader = PaperTrader(
        starting_balance=100000.0,
        log_file="logs/test_full_sell_trades.csv",
        positions_file="logs/test_full_sell_positions.json",
        journal_file="logs/test_full_sell_journal.json",
    )

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

    symbol = "TCS"
    quantity = 5
    entry_price = 2200.0
    exit_price = 2225.0
    exit_reason = "TARGET_TEST"

    opened = trader.open_trade(
        symbol=symbol,
        quantity=quantity,
        entry_price=entry_price,
        stop_loss=2180.0,
        target=2225.0,
        metadata={
            "strategy": "ORB_BREAKOUT",
            "market_condition": "TRENDING",
            "paper_trade": True,
        },
    )

    assert opened is True

    sell_result = execute_paper_sell(
        controller=controller,
        symbol=symbol,
        quantity=quantity,
        price=exit_price,
        reason=exit_reason,
        metadata={
            "full_exit": True,
        },
    )

    assert sell_result.get("success") is True

    execution = sell_result.get(
        "execution",
        {},
    )

    order = sell_result.get(
        "order",
        {},
    )

    assert execution.get("mode") == "PAPER"
    assert execution.get("status") == "SIMULATED"
    assert execution.get("side") == "SELL"
    assert order.get("status") == "SIMULATED"
    assert order.get("internal_order_id")

    closed_trade = trader.close_trade(
        symbol=symbol,
        exit_price=exit_price,
        exit_reason=exit_reason,
    )

    assert closed_trade is not None
    assert trader.get_open_position(symbol) is None
    assert closed_trade["pnl"] == 125.0

    print("\nSELL Execution")
    print("-" * 60)
    print(f"Success            : {sell_result['success']}")
    print(f"Mode               : {execution['mode']}")
    print(f"Status             : {execution['status']}")
    print(f"Side               : {execution['side']}")
    print(
        f"Internal Order ID  : "
        f"{order['internal_order_id']}"
    )

    print("\nFull Close")
    print("-" * 60)
    print(f"Closed Quantity    : {quantity}")
    print(f"Exit Reason        : {exit_reason}")
    print(f"Realized P&L       : ₹{closed_trade['pnl']:.2f}")

    print("\nFULL SELL integration test passed.")


if __name__ == "__main__":
    main()
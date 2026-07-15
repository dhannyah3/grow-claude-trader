"""
Controlled integration test for partial SELL execution.

This test does not place any real Groww order.
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
    print("PARTIAL SELL EXECUTION INTEGRATION TEST")
    print("=" * 60)

    trader = PaperTrader(
        starting_balance=100000.0,
        log_file="logs/test_partial_sell_trades.csv",
        positions_file="logs/test_partial_sell_positions.json",
        journal_file="logs/test_partial_sell_journal.json",
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

    symbol = "ICICIBANK"
    entry_price = 1400.0
    partial_exit_price = 1420.0
    initial_quantity = 10
    partial_quantity = 4

    opened = trader.open_trade(
        symbol=symbol,
        quantity=initial_quantity,
        entry_price=entry_price,
        stop_loss=1390.0,
        target=1440.0,
        metadata={
            "strategy": "VWAP_PULLBACK",
            "market_condition": "RANGE_BOUND",
            "sector": "BANKING",
            "paper_trade": True,
        },
    )

    assert opened is True
    assert trader.get_open_position(symbol) is not None

    sell_result = execute_paper_sell(
        controller=controller,
        symbol=symbol,
        quantity=partial_quantity,
        price=partial_exit_price,
        reason="PARTIAL_TARGET_TEST",
        metadata={
            "partial_exit": True,
            "strategy": "VWAP_PULLBACK",
        },
    )

    assert sell_result.get("success") is True

    execution = sell_result.get("execution", {})
    order = sell_result.get("order", {})

    assert execution.get("mode") == "PAPER"
    assert execution.get("status") == "SIMULATED"
    assert execution.get("side") == "SELL"
    assert order.get("status") == "SIMULATED"
    assert order.get("internal_order_id")

    partial_result = trader.partial_close_trade(
        symbol=symbol,
        exit_price=partial_exit_price,
        quantity=partial_quantity,
        exit_reason="PARTIAL_TARGET_TEST",
    )

    assert partial_result is not None
    assert partial_result["quantity"] == partial_quantity
    assert partial_result["remaining_quantity"] == (
        initial_quantity - partial_quantity
    )

    remaining_position = trader.get_open_position(
        symbol
    )

    assert remaining_position is not None
    assert remaining_position["quantity"] == (
        initial_quantity - partial_quantity
    )

    print("\nSELL Execution")
    print("-" * 60)
    print(f"Success            : {sell_result['success']}")
    print(f"Mode               : {execution['mode']}")
    print(f"Status             : {execution['status']}")
    print(f"Side               : {execution['side']}")
    print(f"Internal Order ID  : {order['internal_order_id']}")

    print("\nPartial Close")
    print("-" * 60)
    print(f"Sold Quantity      : {partial_result['quantity']}")
    print(
        f"Remaining Quantity : "
        f"{partial_result['remaining_quantity']}"
    )
    print(
        f"Partial P&L        : "
        f"₹{partial_result['partial_pnl']:.2f}"
    )

    print("\nPARTIAL SELL integration test passed.")


if __name__ == "__main__":
    main()
    
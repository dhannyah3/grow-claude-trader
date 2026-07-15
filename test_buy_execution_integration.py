from execution.live_execution_controller import (
    LiveExecutionController,
)
from execution.order_executor import OrderExecutor
from execution.order_manager import OrderManager
from execution.position_sync import PositionSynchronizer


def main() -> None:
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

    result = controller.execute_buy(
        symbol="ICICIBANK",
        quantity=1,
        price=1425.50,
        metadata={
            "strategy": "VWAP_PULLBACK",
            "market_condition": "RANGE_BOUND",
            "sector": "BANKING",
            "paper_trade": True,
        },
    )

    print("Success:", result.get("success"))
    print("Execution:", result.get("execution"))
    print("Order:", result.get("order"))

    assert result.get("success") is True

    execution = result.get("execution", {})
    order = result.get("order", {})

    assert execution.get("mode") == "PAPER"
    assert execution.get("status") == "SIMULATED"
    assert order.get("status") == "SIMULATED"
    assert order.get("internal_order_id")

    print("\nBUY execution integration test passed.")


if __name__ == "__main__":
    main()
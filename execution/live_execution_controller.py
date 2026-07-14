"""
Live Execution Controller

Phase 9.6

Coordinates the complete execution workflow.

Scanner
    ↓
Recommendation
    ↓
Order Executor
    ↓
Order Manager
    ↓
Position Synchronizer
"""

from typing import Any, Dict, List, Optional

from execution.order_executor import OrderExecutor
from execution.order_manager import OrderManager
from execution.position_sync import PositionSynchronizer


class LiveExecutionController:

    def __init__(
        self,
        executor: OrderExecutor,
        order_manager: OrderManager,
        position_sync: PositionSynchronizer,
    ) -> None:

        self.executor = executor
        self.order_manager = order_manager
        self.position_sync = position_sync

    def execute_buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        order_result = self.executor.place_buy_order(
            symbol=symbol,
            quantity=quantity,
            reference_price=price,
        )

        if metadata:
            order_result["metadata"] = metadata

        order = self.order_manager.register_order(
            order_result
        )

        return {
            "success": order is not None,
            "execution": order_result,
            "order": order,
        }

    def execute_sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        reason: str = "EXIT",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        order_result = self.executor.place_sell_order(
            symbol=symbol,
            quantity=quantity,
            reference_price=price,
            reason=reason,
        )

        if metadata:
            order_result["metadata"] = metadata

        order = self.order_manager.register_order(
            order_result
        )

        return {
            "success": order is not None,
            "execution": order_result,
            "order": order,
        }

    def synchronize_positions(
        self,
        internal_positions: Dict[str, Any],
        broker_positions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        return self.position_sync.compare_positions(
            internal_positions=internal_positions,
            broker_positions=broker_positions,
        )


if __name__ == "__main__":

    executor = OrderExecutor(
        live_trading=False
    )

    manager = OrderManager()

    synchronizer = PositionSynchronizer()

    controller = LiveExecutionController(
        executor,
        manager,
        synchronizer,
    )

    result = controller.execute_buy(
        symbol="RELIANCE",
        quantity=10,
        price=1500.0,
        metadata={
            "strategy": "ORB_BREAKOUT",
            "confidence": 92,
        },
    )

    print("\nBUY RESULT")
    print(result)

    print("\nORDER SUMMARY")
    print(manager.summary())
"""
Order Manager

Phase 9.2

Tracks simulated and future live orders through
their full lifecycle.

Supported statuses:

- SUBMITTED
- PENDING
- PARTIALLY_FILLED
- FILLED
- REJECTED
- CANCELLED
- FAILED
- SIMULATED
"""

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


class OrderManager:
    FINAL_STATUSES = {
        "FILLED",
        "REJECTED",
        "CANCELLED",
        "FAILED",
        "SIMULATED",
    }

    VALID_STATUSES = {
        "SUBMITTED",
        "PENDING",
        "PARTIALLY_FILLED",
        "FILLED",
        "REJECTED",
        "CANCELLED",
        "FAILED",
        "SIMULATED",
    }

    def __init__(self) -> None:
        self.orders: Dict[
            str,
            Dict[str, Any],
        ] = {}

    def register_order(
        self,
        order_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(
            order_result,
            dict,
        ):
            return None

        symbol = str(
            order_result.get(
                "symbol",
                "",
            )
        ).strip().upper()

        side = str(
            order_result.get(
                "side",
                "",
            )
        ).strip().upper()

        quantity = self._to_int(
            order_result.get(
                "quantity",
                0,
            )
        )

        if (
            not symbol
            or side not in {
                "BUY",
                "SELL",
            }
            or quantity <= 0
        ):
            return None

        broker_order_id = (
            order_result.get(
                "order_id"
            )
        )

        internal_order_id = str(
            broker_order_id
            or uuid4()
        )

        status = self._normalize_status(
            order_result.get(
                "status",
                "SUBMITTED",
            )
        )

        now = datetime.now()

        order = {
            "internal_order_id": (
                internal_order_id
            ),
            "broker_order_id": (
                broker_order_id
            ),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "filled_quantity": self._to_int(
                order_result.get(
                    "filled_quantity",
                    0,
                )
            ),
            "remaining_quantity": quantity,
            "average_fill_price": (
                self._to_float(
                    order_result.get(
                        "average_fill_price",
                        0.0,
                    )
                )
            ),
            "reference_price": (
                self._to_float(
                    order_result.get(
                        "reference_price",
                        0.0,
                    )
                )
            ),
            "status": status,
            "mode": str(
                order_result.get(
                    "mode",
                    "UNKNOWN",
                )
            ).strip().upper(),
            "reason": str(
                order_result.get(
                    "reason",
                    "",
                )
            ),
            "created_at": now,
            "updated_at": now,
            "history": [
                {
                    "time": now,
                    "status": status,
                    "filled_quantity": (
                        self._to_int(
                            order_result.get(
                                "filled_quantity",
                                0,
                            )
                        )
                    ),
                    "average_fill_price": (
                        self._to_float(
                            order_result.get(
                                "average_fill_price",
                                0.0,
                            )
                        )
                    ),
                    "reason": str(
                        order_result.get(
                            "reason",
                            "",
                        )
                    ),
                }
            ],
            "metadata": deepcopy(
                order_result.get(
                    "metadata",
                    {},
                )
                if isinstance(
                    order_result.get(
                        "metadata",
                        {},
                    ),
                    dict,
                )
                else {}
            ),
        }

        if status == "SIMULATED":
            order["filled_quantity"] = quantity
            order["remaining_quantity"] = 0
            order["average_fill_price"] = (
                order["reference_price"]
            )

            order["history"][0][
                "filled_quantity"
            ] = quantity

            order["history"][0][
                "average_fill_price"
            ] = order[
                "reference_price"
            ]

        else:
            order[
                "remaining_quantity"
            ] = max(
                0,
                quantity
                - order["filled_quantity"],
            )

        self.orders[
            internal_order_id
        ] = order

        return deepcopy(order)

    def update_order(
        self,
        order_id: str,
        status: str,
        filled_quantity: Optional[
            int
        ] = None,
        average_fill_price: Optional[
            float
        ] = None,
        reason: str = "",
    ) -> Optional[Dict[str, Any]]:
        normalized_order_id = str(
            order_id
        ).strip()

        order = self.orders.get(
            normalized_order_id
        )

        if order is None:
            return None

        normalized_status = (
            self._normalize_status(
                status
            )
        )

        if (
            order["status"]
            in self.FINAL_STATUSES
            and normalized_status
            != order["status"]
        ):
            return deepcopy(order)

        if filled_quantity is not None:
            normalized_filled = max(
                0,
                min(
                    self._to_int(
                        filled_quantity
                    ),
                    int(
                        order["quantity"]
                    ),
                ),
            )

            order[
                "filled_quantity"
            ] = normalized_filled

            order[
                "remaining_quantity"
            ] = max(
                0,
                int(
                    order["quantity"]
                )
                - normalized_filled,
            )

        if average_fill_price is not None:
            normalized_price = self._to_float(
                average_fill_price
            )

            if normalized_price > 0:
                order[
                    "average_fill_price"
                ] = normalized_price

        if (
            order["filled_quantity"]
            >= order["quantity"]
        ):
            normalized_status = "FILLED"

        elif (
            order["filled_quantity"] > 0
            and normalized_status
            not in {
                "CANCELLED",
                "REJECTED",
                "FAILED",
            }
        ):
            normalized_status = (
                "PARTIALLY_FILLED"
            )

        now = datetime.now()

        order["status"] = normalized_status
        order["updated_at"] = now

        if reason:
            order["reason"] = str(
                reason
            )

        order["history"].append(
            {
                "time": now,
                "status": (
                    normalized_status
                ),
                "filled_quantity": int(
                    order[
                        "filled_quantity"
                    ]
                ),
                "average_fill_price": (
                    float(
                        order[
                            "average_fill_price"
                        ]
                    )
                ),
                "reason": str(
                    reason
                ),
            }
        )

        return deepcopy(order)

    def get_order(
        self,
        order_id: str,
    ) -> Optional[Dict[str, Any]]:
        order = self.orders.get(
            str(
                order_id
            ).strip()
        )

        return (
            deepcopy(order)
            if order is not None
            else None
        )

    def active_orders(
        self,
    ) -> List[Dict[str, Any]]:
        return [
            deepcopy(order)
            for order in self.orders.values()
            if order["status"]
            not in self.FINAL_STATUSES
        ]

    def completed_orders(
        self,
    ) -> List[Dict[str, Any]]:
        return [
            deepcopy(order)
            for order in self.orders.values()
            if order["status"]
            in self.FINAL_STATUSES
        ]

    def summary(
        self,
    ) -> Dict[str, Any]:
        status_counts: Dict[
            str,
            int,
        ] = {}

        for order in self.orders.values():
            status = str(
                order["status"]
            )

            status_counts[
                status
            ] = (
                status_counts.get(
                    status,
                    0,
                )
                + 1
            )

        return {
            "total_orders": len(
                self.orders
            ),
            "active_orders": len(
                self.active_orders()
            ),
            "completed_orders": len(
                self.completed_orders()
            ),
            "status_counts": (
                status_counts
            ),
        }

    def _normalize_status(
        self,
        status: Any,
    ) -> str:
        normalized = str(
            status
        ).strip().upper()

        if normalized not in (
            self.VALID_STATUSES
        ):
            return "FAILED"

        return normalized

    @staticmethod
    def _to_float(
        value: Any,
    ) -> float:
        try:
            return float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    @staticmethod
    def _to_int(
        value: Any,
    ) -> int:
        try:
            return int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0


if __name__ == "__main__":
    from execution.order_executor import (
        OrderExecutor,
    )

    executor = OrderExecutor(
        live_trading=False
    )

    manager = OrderManager()

    buy_result = executor.place_buy_order(
        symbol="RELIANCE",
        quantity=10,
        reference_price=1500.0,
    )

    registered = manager.register_order(
        buy_result
    )

    print(
        "\nREGISTERED ORDER:"
    )

    print(
        registered
    )

    print(
        "\nSUMMARY:"
    )

    print(
        manager.summary()
    )
    
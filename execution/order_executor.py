"""
Order Executor

Phase 9.1

Provides a safe execution interface for paper
and future live Groww orders.

Live trading is disabled by default.
"""

from typing import Any, Dict, Optional


class OrderExecutor:
    def __init__(
        self,
        groww_client: Optional[Any] = None,
        live_trading: bool = False,
    ) -> None:
        self.groww_client = groww_client
        self.live_trading = bool(
            live_trading
        )

    def place_buy_order(
        self,
        symbol: str,
        quantity: int,
        reference_price: float,
    ) -> Dict[str, Any]:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        validation_error = self._validate_order(
            symbol=normalized_symbol,
            quantity=quantity,
            reference_price=reference_price,
        )

        if validation_error:
            return self._failed_result(
                symbol=normalized_symbol,
                side="BUY",
                reason=validation_error,
            )

        if not self.live_trading:
            return {
                "success": True,
                "mode": "PAPER",
                "side": "BUY",
                "symbol": normalized_symbol,
                "quantity": int(
                    quantity
                ),
                "reference_price": float(
                    reference_price
                ),
                "order_id": None,
                "status": "SIMULATED",
                "reason": (
                    "Live trading is disabled. "
                    "Order was simulated only."
                ),
            }

        if self.groww_client is None:
            return self._failed_result(
                symbol=normalized_symbol,
                side="BUY",
                reason=(
                    "Groww client is unavailable."
                ),
            )

        return self._failed_result(
            symbol=normalized_symbol,
            side="BUY",
            reason=(
                "Live Groww order placement has "
                "not been enabled yet."
            ),
        )

    def place_sell_order(
        self,
        symbol: str,
        quantity: int,
        reference_price: float,
        reason: str = "EXIT",
    ) -> Dict[str, Any]:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        validation_error = self._validate_order(
            symbol=normalized_symbol,
            quantity=quantity,
            reference_price=reference_price,
        )

        if validation_error:
            return self._failed_result(
                symbol=normalized_symbol,
                side="SELL",
                reason=validation_error,
            )

        if not self.live_trading:
            return {
                "success": True,
                "mode": "PAPER",
                "side": "SELL",
                "symbol": normalized_symbol,
                "quantity": int(
                    quantity
                ),
                "reference_price": float(
                    reference_price
                ),
                "order_id": None,
                "status": "SIMULATED",
                "exit_reason": str(
                    reason
                ),
                "reason": (
                    "Live trading is disabled. "
                    "Order was simulated only."
                ),
            }

        if self.groww_client is None:
            return self._failed_result(
                symbol=normalized_symbol,
                side="SELL",
                reason=(
                    "Groww client is unavailable."
                ),
            )

        return self._failed_result(
            symbol=normalized_symbol,
            side="SELL",
            reason=(
                "Live Groww order placement has "
                "not been enabled yet."
            ),
        )

    def enable_live_trading(
        self,
    ) -> Dict[str, Any]:
        if self.groww_client is None:
            return {
                "enabled": False,
                "reason": (
                    "Cannot enable live trading "
                    "without a Groww client."
                ),
            }

        self.live_trading = True

        return {
            "enabled": True,
            "reason": (
                "Live trading mode enabled."
            ),
        }

    def disable_live_trading(
        self,
    ) -> Dict[str, Any]:
        self.live_trading = False

        return {
            "enabled": False,
            "reason": (
                "Live trading mode disabled."
            ),
        }

    @staticmethod
    def _validate_order(
        symbol: str,
        quantity: int,
        reference_price: float,
    ) -> Optional[str]:
        if not symbol:
            return "Order requires a symbol."

        if quantity <= 0:
            return (
                "Order quantity must be positive."
            )

        if reference_price <= 0:
            return (
                "Reference price must be positive."
            )

        return None

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        return str(
            symbol
        ).strip().upper()

    @staticmethod
    def _failed_result(
        symbol: str,
        side: str,
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "mode": "LIVE",
            "side": side,
            "symbol": symbol,
            "order_id": None,
            "status": "FAILED",
            "reason": reason,
        }


if __name__ == "__main__":
    executor = OrderExecutor(
        live_trading=False
    )

    buy_result = executor.place_buy_order(
        symbol="RELIANCE",
        quantity=10,
        reference_price=1500.0,
    )

    sell_result = executor.place_sell_order(
        symbol="RELIANCE",
        quantity=10,
        reference_price=1520.0,
        reason="TEST_EXIT",
    )

    print(
        "\nBUY RESULT:"
    )

    print(
        buy_result
    )

    print(
        "\nSELL RESULT:"
    )

    print(
        sell_result
    )
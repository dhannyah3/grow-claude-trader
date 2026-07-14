"""
Groww Order Adapter

Phase 9.4

Translates internal order requests into the
Groww Python SDK format.

Real order placement remains disabled unless
both conditions are true:

- live_trading=True
- confirmation_token="ENABLE_LIVE_ORDERS"
"""

from typing import Any, Dict, Optional
from uuid import uuid4


class GrowwOrderAdapter:
    LIVE_CONFIRMATION_TOKEN = (
        "ENABLE_LIVE_ORDERS"
    )

    def __init__(
        self,
        groww_client: Optional[Any] = None,
        live_trading: bool = False,
        confirmation_token: str = "",
    ) -> None:
        self.groww_client = groww_client

        self.live_trading = bool(
            live_trading
        )

        self.confirmation_token = str(
            confirmation_token
        ).strip()

    def submit_market_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        reference_price: float,
    ) -> Dict[str, Any]:
        normalized_symbol = (
            self._normalize_symbol(
                symbol
            )
        )

        normalized_side = str(
            side
        ).strip().upper()

        validation_error = (
            self._validate_request(
                symbol=normalized_symbol,
                side=normalized_side,
                quantity=quantity,
                reference_price=(
                    reference_price
                ),
            )
        )

        if validation_error:
            return self._failed_result(
                symbol=normalized_symbol,
                side=normalized_side,
                quantity=quantity,
                reference_price=(
                    reference_price
                ),
                reason=validation_error,
            )

        payload = self.build_market_payload(
            symbol=normalized_symbol,
            side=normalized_side,
            quantity=quantity,
        )

        if not self._live_mode_authorized():
            return {
                "success": True,
                "mode": "PAPER",
                "status": "SIMULATED",
                "symbol": normalized_symbol,
                "side": normalized_side,
                "quantity": int(
                    quantity
                ),
                "reference_price": float(
                    reference_price
                ),
                "order_id": None,
                "order_reference_id": (
                    payload[
                        "order_reference_id"
                    ]
                ),
                "broker_payload": payload,
                "broker_response": None,
                "reason": (
                    "Live Groww order placement "
                    "is disabled."
                ),
            }

        if self.groww_client is None:
            return self._failed_result(
                symbol=normalized_symbol,
                side=normalized_side,
                quantity=quantity,
                reference_price=(
                    reference_price
                ),
                reason=(
                    "Groww client is unavailable."
                ),
                payload=payload,
            )

        try:
            response = (
                self.groww_client.place_order(
                    **payload
                )
            )

        except Exception as error:
            return self._failed_result(
                symbol=normalized_symbol,
                side=normalized_side,
                quantity=quantity,
                reference_price=(
                    reference_price
                ),
                reason=(
                    "Groww place_order failed: "
                    f"{error}"
                ),
                payload=payload,
            )

        normalized_response = (
            self._normalize_response(
                response=response,
                symbol=normalized_symbol,
                side=normalized_side,
                quantity=quantity,
                reference_price=(
                    reference_price
                ),
                payload=payload,
            )
        )

        return normalized_response

    def build_market_payload(
        self,
        symbol: str,
        side: str,
        quantity: int,
    ) -> Dict[str, Any]:
        if self.groww_client is None:
            exchange = "NSE"
            segment = "CASH"
            product = "MIS"
            order_type = "MARKET"
            validity = "DAY"
            transaction_type = side

        else:
            exchange = (
                self.groww_client
                .EXCHANGE_NSE
            )

            segment = (
                self.groww_client
                .SEGMENT_CASH
            )

            product = (
                self.groww_client
                .PRODUCT_MIS
            )

            order_type = (
                self.groww_client
                .ORDER_TYPE_MARKET
            )

            validity = (
                self.groww_client
                .VALIDITY_DAY
            )

            if side == "BUY":
                transaction_type = (
                    self.groww_client
                    .TRANSACTION_TYPE_BUY
                )

            else:
                transaction_type = (
                    self.groww_client
                    .TRANSACTION_TYPE_SELL
                )

        return {
            "trading_symbol": (
                self._normalize_symbol(
                    symbol
                )
            ),
            "quantity": int(
                quantity
            ),
            "validity": validity,
            "exchange": exchange,
            "segment": segment,
            "product": product,
            "order_type": order_type,
            "transaction_type": (
                transaction_type
            ),
            "order_reference_id": (
                self._build_reference_id()
            ),
        }

    def get_order_status(
        self,
        groww_order_id: str,
    ) -> Dict[str, Any]:
        order_id = str(
            groww_order_id
        ).strip()

        if not order_id:
            return {
                "success": False,
                "status": "FAILED",
                "reason": (
                    "Groww order ID is required."
                ),
            }

        if not self._live_mode_authorized():
            return {
                "success": False,
                "status": "SIMULATED",
                "reason": (
                    "Live order-status lookup "
                    "is disabled."
                ),
            }

        if self.groww_client is None:
            return {
                "success": False,
                "status": "FAILED",
                "reason": (
                    "Groww client is unavailable."
                ),
            }

        try:
            response = (
                self.groww_client
                .get_order_status(
                    groww_order_id=order_id,
                    segment=(
                        self.groww_client
                        .SEGMENT_CASH
                    ),
                )
            )

        except Exception as error:
            return {
                "success": False,
                "status": "FAILED",
                "reason": str(
                    error
                ),
            }

        return {
            "success": True,
            "groww_order_id": (
                response.get(
                    "groww_order_id",
                    order_id,
                )
            ),
            "status": str(
                response.get(
                    "order_status",
                    "UNKNOWN",
                )
            ).strip().upper(),
            "filled_quantity": (
                self._to_int(
                    response.get(
                        "filled_quantity",
                        0,
                    )
                )
            ),
            "remark": str(
                response.get(
                    "remark",
                    "",
                )
            ),
            "broker_response": response,
        }

    def _normalize_response(
        self,
        response: Any,
        symbol: str,
        side: str,
        quantity: int,
        reference_price: float,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not isinstance(
            response,
            dict,
        ):
            return self._failed_result(
                symbol=symbol,
                side=side,
                quantity=quantity,
                reference_price=(
                    reference_price
                ),
                reason=(
                    "Groww returned an invalid "
                    "order response."
                ),
                payload=payload,
            )

        order_id = response.get(
            "groww_order_id"
        )

        order_status = str(
            response.get(
                "order_status",
                "UNKNOWN",
            )
        ).strip().upper()

        return {
            "success": bool(
                order_id
            ),
            "mode": "LIVE",
            "status": order_status,
            "symbol": symbol,
            "side": side,
            "quantity": int(
                quantity
            ),
            "reference_price": float(
                reference_price
            ),
            "order_id": order_id,
            "order_reference_id": (
                response.get(
                    "order_reference_id",
                    payload.get(
                        "order_reference_id"
                    ),
                )
            ),
            "broker_payload": payload,
            "broker_response": response,
            "reason": str(
                response.get(
                    "remark",
                    "",
                )
            ),
        }

    def _live_mode_authorized(
        self,
    ) -> bool:
        return (
            self.live_trading
            and self.confirmation_token
            == self.LIVE_CONFIRMATION_TOKEN
        )

    @staticmethod
    def _validate_request(
        symbol: str,
        side: str,
        quantity: int,
        reference_price: float,
    ) -> Optional[str]:
        if not symbol:
            return "Symbol is required."

        if side not in {
            "BUY",
            "SELL",
        }:
            return (
                "Side must be BUY or SELL."
            )

        if quantity <= 0:
            return (
                "Quantity must be positive."
            )

        if reference_price <= 0:
            return (
                "Reference price must be "
                "positive."
            )

        return None

    @staticmethod
    def _normalize_symbol(
        symbol: Any,
    ) -> str:
        normalized = str(
            symbol
        ).strip().upper()

        if normalized.startswith(
            "NSE-"
        ):
            normalized = (
                normalized[4:]
            )

        return normalized

    @staticmethod
    def _build_reference_id(
    ) -> str:
        return (
            "AI-"
            + uuid4().hex[:12].upper()
        )

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

    @staticmethod
    def _failed_result(
        symbol: str,
        side: str,
        quantity: int,
        reference_price: float,
        reason: str,
        payload: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:
        return {
            "success": False,
            "mode": "LIVE",
            "status": "FAILED",
            "symbol": symbol,
            "side": side,
            "quantity": int(
                quantity
            ),
            "reference_price": float(
                reference_price
            ),
            "order_id": None,
            "broker_payload": payload,
            "broker_response": None,
            "reason": reason,
        }


if __name__ == "__main__":
    adapter = GrowwOrderAdapter(
        groww_client=None,
        live_trading=False,
    )

    result = adapter.submit_market_order(
        symbol="NSE-RELIANCE",
        side="BUY",
        quantity=10,
        reference_price=1500.0,
    )

    print(
        "\nADAPTER RESULT:"
    )

    print(
        result
    )

    print(
        "\nBROKER PAYLOAD:"
    )

    print(
        result.get(
            "broker_payload"
        )
    )
    
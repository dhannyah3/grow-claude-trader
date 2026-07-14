"""
Position Synchronizer

Phase 9.3

Compares internal trading positions with
broker positions and reports mismatches.
"""

from typing import Any, Dict, List


class PositionSynchronizer:
    def compare_positions(
        self,
        internal_positions: Dict[
            str,
            Dict[str, Any],
        ],
        broker_positions: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:
        internal = self._normalize_internal(
            internal_positions
        )

        broker = self._normalize_broker(
            broker_positions
        )

        symbols = sorted(
            set(
                internal.keys()
            )
            | set(
                broker.keys()
            )
        )

        comparisons: List[
            Dict[str, Any]
        ] = []

        for symbol in symbols:
            internal_position = (
                internal.get(
                    symbol
                )
            )

            broker_position = (
                broker.get(
                    symbol
                )
            )

            if (
                internal_position is not None
                and broker_position is None
            ):
                comparisons.append(
                    {
                        "symbol": symbol,
                        "status": (
                            "MISSING_AT_BROKER"
                        ),
                        "internal_position": (
                            internal_position
                        ),
                        "broker_position": None,
                    }
                )

                continue

            if (
                internal_position is None
                and broker_position is not None
            ):
                comparisons.append(
                    {
                        "symbol": symbol,
                        "status": (
                            "MISSING_IN_SYSTEM"
                        ),
                        "internal_position": None,
                        "broker_position": (
                            broker_position
                        ),
                    }
                )

                continue

            if (
                internal_position is None
                or broker_position is None
            ):
                continue

            internal_quantity = int(
                internal_position[
                    "quantity"
                ]
            )

            broker_quantity = int(
                broker_position[
                    "quantity"
                ]
            )

            internal_price = float(
                internal_position[
                    "average_price"
                ]
            )

            broker_price = float(
                broker_position[
                    "average_price"
                ]
            )

            quantity_matches = (
                internal_quantity
                == broker_quantity
            )

            price_difference = abs(
                internal_price
                - broker_price
            )

            price_matches = (
                price_difference
                <= 0.05
            )

            if not quantity_matches:
                status = (
                    "QUANTITY_MISMATCH"
                )

            elif not price_matches:
                status = (
                    "PRICE_MISMATCH"
                )

            else:
                status = "MATCHED"

            comparisons.append(
                {
                    "symbol": symbol,
                    "status": status,
                    "internal_quantity": (
                        internal_quantity
                    ),
                    "broker_quantity": (
                        broker_quantity
                    ),
                    "quantity_difference": (
                        broker_quantity
                        - internal_quantity
                    ),
                    "internal_average_price": (
                        internal_price
                    ),
                    "broker_average_price": (
                        broker_price
                    ),
                    "price_difference": round(
                        price_difference,
                        4,
                    ),
                    "internal_position": (
                        internal_position
                    ),
                    "broker_position": (
                        broker_position
                    ),
                }
            )

        mismatch_count = sum(
            1
            for item in comparisons
            if item["status"]
            != "MATCHED"
        )

        return {
            "synchronized": (
                mismatch_count == 0
            ),
            "total_symbols": len(
                comparisons
            ),
            "matched": sum(
                1
                for item in comparisons
                if item["status"]
                == "MATCHED"
            ),
            "mismatches": mismatch_count,
            "comparisons": comparisons,
        }

    def _normalize_internal(
        self,
        positions: Dict[
            str,
            Dict[str, Any],
        ],
    ) -> Dict[
        str,
        Dict[str, Any],
    ]:
        normalized: Dict[
            str,
            Dict[str, Any],
        ] = {}

        if not isinstance(
            positions,
            dict,
        ):
            return normalized

        for symbol, position in (
            positions.items()
        ):
            if not isinstance(
                position,
                dict,
            ):
                continue

            normalized_symbol = (
                self._normalize_symbol(
                    symbol
                )
            )

            if not normalized_symbol:
                continue

            quantity = self._to_int(
                position.get(
                    "quantity",
                    position.get(
                        "remaining_quantity",
                        0,
                    ),
                )
            )

            average_price = (
                self._to_float(
                    position.get(
                        "entry_price",
                        position.get(
                            "average_price",
                            0.0,
                        ),
                    )
                )
            )

            if quantity <= 0:
                continue

            normalized[
                normalized_symbol
            ] = {
                "symbol": (
                    normalized_symbol
                ),
                "quantity": quantity,
                "average_price": (
                    average_price
                ),
                "raw": position,
            }

        return normalized

    def _normalize_broker(
        self,
        positions: List[
            Dict[str, Any]
        ],
    ) -> Dict[
        str,
        Dict[str, Any],
    ]:
        normalized: Dict[
            str,
            Dict[str, Any],
        ] = {}

        if not isinstance(
            positions,
            list,
        ):
            return normalized

        for position in positions:
            if not isinstance(
                position,
                dict,
            ):
                continue

            symbol = (
                position.get(
                    "symbol"
                )
                or position.get(
                    "trading_symbol"
                )
                or position.get(
                    "groww_symbol"
                )
                or ""
            )

            normalized_symbol = (
                self._normalize_symbol(
                    symbol
                )
            )

            if not normalized_symbol:
                continue

            quantity = self._to_int(
                position.get(
                    "quantity",
                    position.get(
                        "net_quantity",
                        0,
                    ),
                )
            )

            average_price = (
                self._to_float(
                    position.get(
                        "average_price",
                        position.get(
                            "buy_average_price",
                            0.0,
                        ),
                    )
                )
            )

            if quantity <= 0:
                continue

            normalized[
                normalized_symbol
            ] = {
                "symbol": (
                    normalized_symbol
                ),
                "quantity": quantity,
                "average_price": (
                    average_price
                ),
                "raw": position,
            }

        return normalized

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
    synchronizer = (
        PositionSynchronizer()
    )

    internal_positions = {
        "RELIANCE": {
            "quantity": 10,
            "entry_price": 1500.0,
        },
        "TCS": {
            "quantity": 5,
            "entry_price": 3800.0,
        },
    }

    broker_positions = [
        {
            "symbol": "NSE-RELIANCE",
            "quantity": 10,
            "average_price": 1500.0,
        },
        {
            "symbol": "NSE-TCS",
            "quantity": 4,
            "average_price": 3800.0,
        },
        {
            "symbol": "NSE-INFY",
            "quantity": 3,
            "average_price": 1600.0,
        },
    ]

    result = (
        synchronizer.compare_positions(
            internal_positions=(
                internal_positions
            ),
            broker_positions=(
                broker_positions
            ),
        )
    )

    print(
        "\nPOSITION SYNC RESULT:"
    )

    print(
        result
    )

    print(
        "\nCOMPARISONS:"
    )

    for comparison in result[
        "comparisons"
    ]:
        print(
            comparison
        )
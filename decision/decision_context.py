"""
Decision Context.

Builds the runtime context required by the DecisionPipeline.
"""

from typing import Any, Dict, List


class DecisionContext:

    @staticmethod
    def build(
        scan_results: List[Dict[str, Any]],
        trader: Any,
    ) -> Dict[str, Any]:

        sector_map: Dict[str, str] = {}
        prices: Dict[str, float] = {}

        for result in scan_results:

            symbol = str(
                result.get("symbol", "")
            ).strip().upper()

            if not symbol:
                continue

            sector_map[symbol] = result.get(
                "sector",
                "UNKNOWN",
            )

            prices[symbol] = float(
                result.get(
                    "suggested_entry",
                    result.get(
                        "entry_price",
                        0.0,
                    ),
                )
                or 0.0
            )

        return {
            "sector_map": sector_map,
            "prices": prices,
            "total_capital": float(
                trader.cash_balance
            ),
        }
    
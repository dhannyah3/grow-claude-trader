"""
Snapshot Adapter.

Converts scanner output into the snapshot format expected by
FinalDecisionEngine and merges approved execution decisions back
into the original scanner results.
"""

from typing import Any, Dict, List, Mapping


class SnapshotAdapter:
    """
    Translate data between the market scanner and decision engine.
    """

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        """
        Return a normalized uppercase trading symbol.
        """

        if value is None:
            return ""

        return str(value).strip().upper()

    @classmethod
    def from_scan_results(
        cls,
        scan_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Convert scan_market() output into a decision snapshot.

        The complete scanner result is preserved for each symbol so
        downstream decision modules can access strategy, intelligence,
        regime, price, and confidence information.
        """

        stocks: Dict[str, Dict[str, Any]] = {}

        for result in scan_results:
            if not isinstance(result, Mapping):
                continue

            symbol = cls._normalize_symbol(
                result.get("symbol")
            )

            if not symbol:
                continue

            stock_data = dict(result)
            stock_data["symbol"] = symbol

            stocks[symbol] = stock_data

        return {
            "stocks": stocks,
        }

    @classmethod
    def merge_execution_queue(
        cls,
        scan_results: List[Dict[str, Any]],
        execution_queue: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge approved FinalDecisionEngine results into scanner output.

        Only symbols approved in the execution queue are returned.

        Original scanner metadata remains intact. Decision-engine fields
        are stored with a ``decision_`` prefix to prevent accidental
        overwriting of scanner or strategy values.
        """

        approved_lookup: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for queue_item in execution_queue:
            if not isinstance(queue_item, Mapping):
                continue

            symbol = cls._normalize_symbol(
                queue_item.get("symbol")
            )

            if not symbol:
                continue

            if not bool(
                queue_item.get("approved", False)
            ):
                continue

            approved_lookup[symbol] = dict(
                queue_item
            )

        approved_results: List[
            Dict[str, Any]
        ] = []

        for result in scan_results:
            if not isinstance(result, Mapping):
                continue

            symbol = cls._normalize_symbol(
                result.get("symbol")
            )

            decision = approved_lookup.get(
                symbol
            )

            if decision is None:
                continue

            merged = dict(result)
            merged["symbol"] = symbol

            merged.update(
                {
                    "decision_approved": True,
                    "decision_quantity": (
                        decision.get(
                            "quantity",
                            0,
                        )
                    ),
                    "decision_entry_price": (
                        decision.get(
                            "entry_price",
                            0.0,
                        )
                    ),
                    "decision_stop_loss": (
                        decision.get(
                            "stop_loss",
                            0.0,
                        )
                    ),
                    "decision_target_price": (
                        decision.get(
                            "target_price",
                            0.0,
                        )
                    ),
                    "decision_position_value": (
                        decision.get(
                            "position_value",
                            0.0,
                        )
                    ),
                    "decision_risk_amount": (
                        decision.get(
                            "risk_amount",
                            0.0,
                        )
                    ),
                    "decision_priority_rank": (
                        decision.get(
                            "priority_rank",
                            0,
                        )
                    ),
                    "decision_priority_score": (
                        decision.get(
                            "priority_score",
                            0.0,
                        )
                    ),
                    "decision_confidence": (
                        decision.get(
                            "confidence",
                            0.0,
                        )
                    ),
                    "decision_sector": (
                        decision.get(
                            "sector",
                            "",
                        )
                    ),
                    "decision_scaled_by_risk_budget": (
                        decision.get(
                            "scaled_by_risk_budget",
                            False,
                        )
                    ),
                    "decision_reasons": list(
                        decision.get(
                            "reasons",
                            [],
                        )
                    ),
                }
            )

            approved_results.append(merged)

        approved_results.sort(
            key=lambda item: (
                item.get(
                    "decision_priority_rank",
                    999999,
                ),
                -float(
                    item.get(
                        "decision_priority_score",
                        0.0,
                    )
                    or 0.0
                ),
            )
        )

        return approved_results
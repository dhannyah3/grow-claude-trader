"""
Dynamic Position Sizer

Version 7.1

Converts a recommendation-engine result into
a safe position-size multiplier.
"""

from typing import Any, Dict


class DynamicPositionSizer:
    def size_position(
        self,
        recommendation: Dict[str, Any],
        base_quantity: int,
    ) -> Dict[str, Any]:
        if not isinstance(
            recommendation,
            dict,
        ):
            return self._blocked_result(
                "Invalid recommendation object."
            )

        if base_quantity <= 0:
            return self._blocked_result(
                "Base quantity must be positive."
            )

        decision = str(
            recommendation.get(
                "decision",
                "INSUFFICIENT_DATA",
            )
        ).strip().upper()

        risk_level = str(
            recommendation.get(
                "risk_level",
                "VERY_HIGH",
            )
        ).strip().upper()

        decision_confidence = self._to_float(
            recommendation.get(
                "decision_confidence",
                0.0,
            )
        )

        multiplier = self._select_multiplier(
            decision=decision,
            risk_level=risk_level,
            decision_confidence=(
                decision_confidence
            ),
        )

        adjusted_quantity = int(
            base_quantity
            * multiplier
        )

        allowed = (
            multiplier > 0
            and adjusted_quantity > 0
        )

        return {
            "allowed": allowed,
            "decision": decision,
            "risk_level": risk_level,
            "decision_confidence": round(
                decision_confidence,
                2,
            ),
            "base_quantity": int(
                base_quantity
            ),
            "position_multiplier": round(
                multiplier,
                2,
            ),
            "adjusted_quantity": (
                adjusted_quantity
            ),
            "reason": self._build_reason(
                decision=decision,
                risk_level=risk_level,
                decision_confidence=(
                    decision_confidence
                ),
                multiplier=multiplier,
            ),
        }

    def _select_multiplier(
        self,
        decision: str,
        risk_level: str,
        decision_confidence: float,
    ) -> float:
        if decision in {
            "SKIP",
            "INSUFFICIENT_DATA",
        }:
            return 0.0

        if decision == "WATCH":
            return 0.5

        if decision != "TAKE_TRADE":
            return 0.0

        if (
            risk_level == "LOW"
            and decision_confidence >= 90.0
        ):
            return 1.25

        if (
            risk_level == "MEDIUM"
            and decision_confidence >= 75.0
        ):
            return 1.0

        if (
            risk_level == "HIGH"
            and decision_confidence >= 60.0
        ):
            return 0.75

        return 0.5

    def _build_reason(
        self,
        decision: str,
        risk_level: str,
        decision_confidence: float,
        multiplier: float,
    ) -> str:
        if multiplier <= 0:
            return (
                f"{decision} recommendations are "
                "not allowed to open a position."
            )

        return (
            f"{decision} recommendation with "
            f"{risk_level} risk and "
            f"{decision_confidence:.2f}% confidence "
            f"uses a {multiplier:.2f}x multiplier."
        )

    @staticmethod
    def _blocked_result(
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "allowed": False,
            "position_multiplier": 0.0,
            "adjusted_quantity": 0,
            "reason": reason,
        }

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


if __name__ == "__main__":
    sizer = DynamicPositionSizer()

    recommendation = {
        "decision": "TAKE_TRADE",
        "decision_confidence": 84.65,
        "risk_level": "MEDIUM",
    }

    print(
        sizer.size_position(
            recommendation=(
                recommendation
            ),
            base_quantity=100,
        )
    )
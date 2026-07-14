"""
Portfolio Heat Manager

Version 8.1

Controls total portfolio risk before a new
trade is allowed.
"""

from typing import Any, Dict, List


class PortfolioHeatManager:
    def __init__(
        self,
        max_total_risk_percent: float = 3.0,
        max_open_positions: int = 3,
        max_sector_positions: int = 1,
    ) -> None:
        self.max_total_risk_percent = float(
            max_total_risk_percent
        )
        self.max_open_positions = int(
            max_open_positions
        )
        self.max_sector_positions = int(
            max_sector_positions
        )

    def evaluate(
        self,
        account_balance: float,
        proposed_risk_amount: float,
        open_positions: List[Dict[str, Any]],
        proposed_sector: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        if account_balance <= 0:
            return self._blocked(
                "Account balance must be positive."
            )

        if proposed_risk_amount <= 0:
            return self._blocked(
                "Proposed risk must be positive."
            )

        open_positions = (
            open_positions
            if isinstance(
                open_positions,
                list,
            )
            else []
        )

        current_open_count = len(
            open_positions
        )

        if (
            current_open_count
            >= self.max_open_positions
        ):
            return self._blocked(
                "Maximum open positions reached."
            )

        current_risk = sum(
            self._to_float(
                position.get(
                    "risk_amount",
                    0.0,
                )
            )
            for position in open_positions
            if isinstance(
                position,
                dict,
            )
        )

        total_risk = (
            current_risk
            + proposed_risk_amount
        )

        total_risk_percent = (
            total_risk
            / account_balance
            * 100
        )

        if (
            total_risk_percent
            > self.max_total_risk_percent
        ):
            return self._blocked(
                "Portfolio risk limit exceeded."
            )

        normalized_sector = str(
            proposed_sector
        ).strip().upper()

        sector_positions = sum(
            1
            for position in open_positions
            if str(
                position.get(
                    "sector",
                    "UNKNOWN",
                )
            ).strip().upper()
            == normalized_sector
        )

        if (
            normalized_sector != "UNKNOWN"
            and sector_positions
            >= self.max_sector_positions
        ):
            return self._blocked(
                "Sector exposure limit reached."
            )

        return {
            "allowed": True,
            "current_risk_amount": round(
                current_risk,
                2,
            ),
            "proposed_risk_amount": round(
                proposed_risk_amount,
                2,
            ),
            "total_risk_amount": round(
                total_risk,
                2,
            ),
            "total_risk_percent": round(
                total_risk_percent,
                2,
            ),
            "open_positions": (
                current_open_count
            ),
            "sector_positions": (
                sector_positions
            ),
            "reason": (
                "Portfolio heat is within limits."
            ),
        }

    @staticmethod
    def _blocked(
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "allowed": False,
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
    manager = PortfolioHeatManager(
        max_total_risk_percent=3.0,
        max_open_positions=3,
        max_sector_positions=1,
    )

    result = manager.evaluate(
        account_balance=100000.0,
        proposed_risk_amount=500.0,
        open_positions=[
            {
                "symbol": "RELIANCE",
                "risk_amount": 600.0,
                "sector": "ENERGY",
            },
        ],
        proposed_sector="BANKING",
    )

    print(
        result
    )
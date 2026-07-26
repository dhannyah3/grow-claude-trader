"""
Risk-aware position sizing for the decision layer.

The position sizer combines:

1. Capital assigned by PortfolioAllocator.
2. Risk limits calculated by RiskManager.
3. Entry, stop-loss, and target prices.

The final quantity is the smallest quantity allowed by both the
portfolio allocation and the account risk rules.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from core.risk_manager import RiskManager


@dataclass(frozen=True)
class PositionSizeResult:
    symbol: str
    entry_price: float
    stop_loss: float
    target_price: float

    allocation_cash: float
    allocation_quantity: int
    risk_quantity: int
    final_quantity: int

    position_value: float
    risk_per_share: float
    risk_amount: float
    reward_per_share: float
    risk_reward_ratio: float

    approved: bool
    limiting_factor: str
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PositionSizingSummary:
    requested_positions: int
    approved_positions: int
    rejected_positions: int
    total_allocated_cash: float
    total_position_value: float
    total_risk_amount: float
    unused_allocated_cash: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PositionSizer:
    """
    Convert portfolio allocations into risk-controlled order quantities.
    """

    def __init__(
        self,
        risk_manager: Optional[RiskManager] = None,
        minimum_risk_reward_ratio: float = 1.5,
        minimum_quantity: int = 1,
        round_values: int = 2,
    ) -> None:
        self.risk_manager = risk_manager or RiskManager()

        self.minimum_risk_reward_ratio = self._positive_float(
            minimum_risk_reward_ratio,
            "minimum_risk_reward_ratio",
        )

        if not isinstance(minimum_quantity, int) or minimum_quantity <= 0:
            raise ValueError(
                "minimum_quantity must be a positive integer."
            )

        if not isinstance(round_values, int) or round_values < 0:
            raise ValueError(
                "round_values must be a non-negative integer."
            )

        self.minimum_quantity = minimum_quantity
        self.round_values = round_values

    @staticmethod
    def _positive_float(
        value: Any,
        field_name: str,
    ) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be numeric."
            ) from exc

        if numeric_value <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return numeric_value

    @staticmethod
    def _non_negative_float(
        value: Any,
        field_name: str,
    ) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be numeric."
            ) from exc

        if numeric_value < 0:
            raise ValueError(
                f"{field_name} cannot be negative."
            )

        return numeric_value

    @staticmethod
    def _value(
        source: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(source, Mapping):
            return source.get(field_name, default)

        return getattr(source, field_name, default)

    def size_position(
        self,
        symbol: str,
        allocation_cash: float,
        entry_price: float,
        stop_loss: float,
        target_price: float,
        allocation_selected: bool = True,
    ) -> PositionSizeResult:
        symbol = str(symbol).strip().upper()

        if not symbol:
            raise ValueError("symbol cannot be empty.")

        allocation_cash = self._non_negative_float(
            allocation_cash,
            "allocation_cash",
        )

        entry_price = self._positive_float(
            entry_price,
            "entry_price",
        )

        stop_loss = self._positive_float(
            stop_loss,
            "stop_loss",
        )

        target_price = self._positive_float(
            target_price,
            "target_price",
        )

        reasons: List[str] = []

        risk_per_share = abs(entry_price - stop_loss)
        reward_per_share = abs(target_price - entry_price)

        risk_reward_ratio = (
            reward_per_share / risk_per_share
            if risk_per_share > 0
            else 0.0
        )

        allocation_quantity = int(
            allocation_cash / entry_price
        )

        risk_plan = self.risk_manager.trade_plan(
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
        )

        risk_quantity = int(
            risk_plan.get("quantity", 0)
        )

        final_quantity = min(
            allocation_quantity,
            risk_quantity,
        )

        approved = True
        limiting_factor = "none"

        if not allocation_selected:
            approved = False
            final_quantity = 0
            limiting_factor = "allocation_rejected"
            reasons.append(
                "Portfolio allocator rejected this candidate."
            )

        if allocation_cash <= 0:
            approved = False
            final_quantity = 0
            limiting_factor = "no_allocated_capital"
            reasons.append(
                "No portfolio capital was allocated."
            )

        if not (
            0 < stop_loss < entry_price < target_price
        ):
            approved = False
            final_quantity = 0
            limiting_factor = "invalid_trade_prices"
            reasons.append(
                "A long trade requires stop-loss below entry "
                "and target above entry."
            )

        if risk_reward_ratio < self.minimum_risk_reward_ratio:
            approved = False
            final_quantity = 0
            limiting_factor = "risk_reward"
            reasons.append(
                "Risk-reward ratio is below the configured minimum."
            )

        if allocation_quantity < self.minimum_quantity:
            approved = False
            final_quantity = 0
            limiting_factor = "allocated_capital"
            reasons.append(
                "Allocated capital cannot purchase the minimum quantity."
            )

        if risk_quantity < self.minimum_quantity:
            approved = False
            final_quantity = 0
            limiting_factor = "risk_limit"
            reasons.append(
                "Risk limits do not allow the minimum quantity."
            )

        if approved:
            if allocation_quantity < risk_quantity:
                limiting_factor = "allocated_capital"
                reasons.append(
                    "Final quantity was limited by allocated capital."
                )
            elif risk_quantity < allocation_quantity:
                limiting_factor = "risk_limit"
                reasons.append(
                    "Final quantity was limited by account risk rules."
                )
            else:
                limiting_factor = "allocation_and_risk"
                reasons.append(
                    "Allocated-capital and risk quantities were equal."
                )

            reasons.append(
                "Position satisfies the minimum risk-reward requirement."
            )
            reasons.append(
                "Final quantity respects both capital and risk limits."
            )

        position_value = final_quantity * entry_price
        risk_amount = final_quantity * risk_per_share

        return PositionSizeResult(
            symbol=symbol,
            entry_price=round(entry_price, self.round_values),
            stop_loss=round(stop_loss, self.round_values),
            target_price=round(target_price, self.round_values),
            allocation_cash=round(
                allocation_cash,
                self.round_values,
            ),
            allocation_quantity=allocation_quantity,
            risk_quantity=risk_quantity,
            final_quantity=final_quantity,
            position_value=round(
                position_value,
                self.round_values,
            ),
            risk_per_share=round(
                risk_per_share,
                self.round_values,
            ),
            risk_amount=round(
                risk_amount,
                self.round_values,
            ),
            reward_per_share=round(
                reward_per_share,
                self.round_values,
            ),
            risk_reward_ratio=round(
                risk_reward_ratio,
                self.round_values,
            ),
            approved=approved,
            limiting_factor=limiting_factor,
            reasons=reasons,
        )

    def size_allocation(
        self,
        allocation: Any,
        stop_loss: float,
        target_price: float,
    ) -> PositionSizeResult:
        """
        Size one PortfolioAllocationResult or allocation dictionary.
        """

        return self.size_position(
            symbol=self._value(
                allocation,
                "symbol",
                "",
            ),
            allocation_cash=self._value(
                allocation,
                "cash_used",
                0.0,
            ),
            entry_price=self._value(
                allocation,
                "last_price",
                0.0,
            ),
            stop_loss=stop_loss,
            target_price=target_price,
            allocation_selected=bool(
                self._value(
                    allocation,
                    "selected",
                    False,
                )
            ),
        )

    def size_positions(
        self,
        requests: Iterable[Mapping[str, Any]],
    ) -> List[PositionSizeResult]:
        results: List[PositionSizeResult] = []

        for request in requests:
            results.append(
                self.size_position(
                    symbol=request.get("symbol", ""),
                    allocation_cash=request.get(
                        "allocation_cash",
                        request.get("cash_used", 0.0),
                    ),
                    entry_price=request.get(
                        "entry_price",
                        request.get("last_price", 0.0),
                    ),
                    stop_loss=request.get("stop_loss", 0.0),
                    target_price=request.get(
                        "target_price",
                        request.get("target", 0.0),
                    ),
                    allocation_selected=bool(
                        request.get("selected", True)
                    ),
                )
            )

        return results

    def summarize(
        self,
        results: Iterable[PositionSizeResult],
    ) -> PositionSizingSummary:
        result_list = list(results)

        total_allocated_cash = sum(
            result.allocation_cash
            for result in result_list
        )

        total_position_value = sum(
            result.position_value
            for result in result_list
        )

        return PositionSizingSummary(
            requested_positions=len(result_list),
            approved_positions=sum(
                1 for result in result_list
                if result.approved
            ),
            rejected_positions=sum(
                1 for result in result_list
                if not result.approved
            ),
            total_allocated_cash=round(
                total_allocated_cash,
                self.round_values,
            ),
            total_position_value=round(
                total_position_value,
                self.round_values,
            ),
            total_risk_amount=round(
                sum(
                    result.risk_amount
                    for result in result_list
                ),
                self.round_values,
            ),
            unused_allocated_cash=round(
                max(
                    0.0,
                    total_allocated_cash
                    - total_position_value,
                ),
                self.round_values,
            ),
        )

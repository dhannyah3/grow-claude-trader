"""
Portfolio-level risk budget allocator.

This module receives ranked trade candidates from the TradePriorityEngine and
determines whether each trade can be executed within:

- Daily risk limits
- Portfolio exposure limits
- Available capital
- Sector concentration limits
- Minimum executable quantity requirements

When possible, the allocator reduces position size instead of rejecting a
trade completely.

The module is broker-independent and accepts dictionaries, dataclasses, or
plain Python objects.
"""

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class RiskBudgetResult:
    """Risk-budget decision for one trade candidate."""

    symbol: str
    priority_rank: int
    priority_score: float
    sector: str

    requested_execute: bool
    approved: bool
    scaled: bool
    rejection_reason: str

    original_quantity: int
    adjusted_quantity: int

    entry_price: float
    stop_loss: float
    risk_per_share: float

    original_position_value: float
    adjusted_position_value: float

    original_risk_amount: float
    allocated_risk_amount: float

    daily_risk_remaining: float
    exposure_remaining: float
    capital_remaining: float

    reasons: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a plain dictionary."""

        data = asdict(self)
        data["reasons"] = list(self.reasons)
        return data


@dataclass(frozen=True)
class RiskBudgetSummary:
    """Portfolio-level summary for one allocation run."""

    total_candidates: int
    requested_candidates: int
    approved_trades: int
    scaled_trades: int
    rejected_trades: int

    starting_capital: float
    available_capital: float

    maximum_daily_risk: float
    existing_daily_risk: float
    allocated_new_risk: float
    remaining_daily_risk: float

    maximum_portfolio_exposure: float
    existing_portfolio_exposure: float
    allocated_new_exposure: float
    final_portfolio_exposure: float
    remaining_exposure: float

    total_original_quantity: int
    total_adjusted_quantity: int

    sector_allocations: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the summary to a plain dictionary."""

        return asdict(self)


class RiskBudgetAllocator:
    """
    Allocate portfolio risk across ranked trade candidates.

    Parameters
    ----------
    maximum_daily_risk_percent:
        Maximum percentage of starting capital that may be at risk during the
        trading day.

        Example:
            starting_capital = 100000
            maximum_daily_risk_percent = 1.0

            maximum_daily_risk = 1000

    maximum_portfolio_exposure_percent:
        Maximum percentage of starting capital that may be deployed across all
        open and newly approved positions.

    maximum_sector_exposure_percent:
        Maximum percentage of total portfolio exposure that may be assigned to
        one sector.

    minimum_position_value:
        Minimum adjusted position value required for approval.

    minimum_quantity:
        Minimum executable quantity required for approval.

    allow_position_scaling:
        When True, quantities may be reduced to fit remaining risk, exposure,
        and capital limits.

    round_values:
        Number of decimal places used in output values.
    """

    def __init__(
        self,
        maximum_daily_risk_percent: float = 1.0,
        maximum_portfolio_exposure_percent: float = 60.0,
        maximum_sector_exposure_percent: float = 35.0,
        minimum_position_value: float = 0.0,
        minimum_quantity: int = 1,
        allow_position_scaling: bool = True,
        round_values: int = 2,
    ) -> None:
        self.maximum_daily_risk_percent = self._positive_percentage(
            maximum_daily_risk_percent,
            "maximum_daily_risk_percent",
        )

        self.maximum_portfolio_exposure_percent = self._positive_percentage(
            maximum_portfolio_exposure_percent,
            "maximum_portfolio_exposure_percent",
        )

        self.maximum_sector_exposure_percent = self._positive_percentage(
            maximum_sector_exposure_percent,
            "maximum_sector_exposure_percent",
        )

        self.minimum_position_value = self._non_negative_float(
            minimum_position_value,
            "minimum_position_value",
        )

        if not isinstance(minimum_quantity, int):
            raise ValueError("minimum_quantity must be an integer.")

        if minimum_quantity <= 0:
            raise ValueError("minimum_quantity must be greater than zero.")

        if not isinstance(allow_position_scaling, bool):
            raise ValueError("allow_position_scaling must be a boolean.")

        if not isinstance(round_values, int) or round_values < 0:
            raise ValueError(
                "round_values must be a non-negative integer."
            )

        self.minimum_quantity = minimum_quantity
        self.allow_position_scaling = allow_position_scaling
        self.round_values = round_values

    @staticmethod
    def _non_negative_float(
        value: Any,
        field_name: str,
    ) -> float:
        """Convert a value to a non-negative float."""

        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must be a valid number."
            )

        if number < 0:
            raise ValueError(
                f"{field_name} cannot be negative."
            )

        return number

    @classmethod
    def _positive_float(
        cls,
        value: Any,
        field_name: str,
    ) -> float:
        """Convert a value to a strictly positive float."""

        number = cls._non_negative_float(
            value,
            field_name,
        )

        if number <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return number

    @classmethod
    def _positive_percentage(
        cls,
        value: Any,
        field_name: str,
    ) -> float:
        """Validate a percentage between 0 and 100."""

        number = cls._positive_float(
            value,
            field_name,
        )

        if number > 100:
            raise ValueError(
                f"{field_name} cannot exceed 100."
            )

        return number

    @staticmethod
    def _candidate_mapping(
        candidate: Any,
    ) -> Mapping[str, Any]:
        """Convert supported candidate types into a mapping."""

        if isinstance(candidate, Mapping):
            return candidate

        if is_dataclass(candidate):
            return asdict(candidate)

        if hasattr(candidate, "to_dict"):
            value = candidate.to_dict()

            if isinstance(value, Mapping):
                return value

        if hasattr(candidate, "__dict__"):
            return vars(candidate)

        raise ValueError(
            "Trade candidates must be mappings, dataclasses, "
            "or objects with attributes."
        )

    @classmethod
    def _value(
        cls,
        candidate: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        """Read one field from a candidate."""

        mapping = cls._candidate_mapping(candidate)
        return mapping.get(field_name, default)

    @classmethod
    def _first_value(
        cls,
        candidate: Any,
        field_names: Sequence[str],
        default: Any = None,
    ) -> Any:
        """Return the first available non-None candidate value."""

        mapping = cls._candidate_mapping(candidate)

        for field_name in field_names:
            if field_name in mapping:
                value = mapping[field_name]

                if value is not None:
                    return value

        return default

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        """Clamp a number to a range."""

        return max(
            minimum,
            min(value, maximum),
        )

    def configuration(self) -> Dict[str, Any]:
        """Return allocator configuration."""

        return {
            "maximum_daily_risk_percent":
                self.maximum_daily_risk_percent,
            "maximum_portfolio_exposure_percent":
                self.maximum_portfolio_exposure_percent,
            "maximum_sector_exposure_percent":
                self.maximum_sector_exposure_percent,
            "minimum_position_value":
                self.minimum_position_value,
            "minimum_quantity":
                self.minimum_quantity,
            "allow_position_scaling":
                self.allow_position_scaling,
            "round_values":
                self.round_values,
        }

    def _normalize_candidate(
        self,
        candidate: Any,
        original_rank: int,
    ) -> Dict[str, Any]:
        """Normalize one priority-engine candidate."""

        symbol = str(
            self._first_value(
                candidate,
                ("symbol", "trading_symbol"),
                "",
            )
        ).strip().upper()

        if not symbol:
            raise ValueError(
                "Every risk-budget candidate requires a symbol."
            )

        requested_execute = bool(
            self._first_value(
                candidate,
                (
                    "execute",
                    "approved",
                    "approved_by_priority",
                    "selected",
                ),
                False,
            )
        )

        priority_rank = int(
            self._first_value(
                candidate,
                ("priority_rank", "rank"),
                original_rank,
            )
        )

        priority_score = self._non_negative_float(
            self._first_value(
                candidate,
                ("priority_score", "strategy_score", "score"),
                0.0,
            ),
            "priority_score",
        )

        sector = str(
            self._first_value(
                candidate,
                ("sector", "sector_name"),
                "UNKNOWN",
            )
        ).strip().upper()

        if not sector:
            sector = "UNKNOWN"

        original_quantity = int(
            self._first_value(
                candidate,
                (
                    "final_quantity",
                    "adjusted_quantity",
                    "quantity",
                ),
                0,
            )
            or 0
        )

        if original_quantity < 0:
            raise ValueError(
                "Trade quantity cannot be negative."
            )

        entry_price = self._non_negative_float(
            self._first_value(
                candidate,
                (
                    "entry_price",
                    "last_price",
                    "price",
                ),
                0.0,
            ),
            "entry_price",
        )

        stop_loss = self._non_negative_float(
            self._first_value(
                candidate,
                (
                    "stop_loss",
                    "stop_price",
                ),
                0.0,
            ),
            "stop_loss",
        )

        supplied_position_value = self._non_negative_float(
            self._first_value(
                candidate,
                (
                    "position_value",
                    "adjusted_position_value",
                    "cash_used",
                ),
                0.0,
            ),
            "position_value",
        )

        if entry_price <= 0 and original_quantity > 0:
            if supplied_position_value > 0:
                entry_price = (
                    supplied_position_value /
                    original_quantity
                )

        original_position_value = supplied_position_value

        if (
            original_position_value <= 0
            and entry_price > 0
            and original_quantity > 0
        ):
            original_position_value = (
                entry_price *
                original_quantity
            )

        supplied_risk_amount = self._non_negative_float(
            self._first_value(
                candidate,
                (
                    "risk_amount",
                    "allocated_risk_amount",
                    "original_risk_amount",
                ),
                0.0,
            ),
            "risk_amount",
        )

        risk_per_share = self._non_negative_float(
            self._first_value(
                candidate,
                (
                    "risk_per_share",
                    "per_share_risk",
                ),
                0.0,
            ),
            "risk_per_share",
        )

        if (
            risk_per_share <= 0
            and entry_price > 0
            and stop_loss > 0
        ):
            risk_per_share = abs(
                entry_price - stop_loss
            )

        if (
            risk_per_share <= 0
            and supplied_risk_amount > 0
            and original_quantity > 0
        ):
            risk_per_share = (
                supplied_risk_amount /
                original_quantity
            )

        original_risk_amount = supplied_risk_amount

        if (
            original_risk_amount <= 0
            and risk_per_share > 0
            and original_quantity > 0
        ):
            original_risk_amount = (
                risk_per_share *
                original_quantity
            )

        return {
            "symbol": symbol,
            "original_rank": original_rank,
            "priority_rank": priority_rank,
            "priority_score": priority_score,
            "sector": sector,
            "requested_execute": requested_execute,
            "original_quantity": original_quantity,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "risk_per_share": risk_per_share,
            "original_position_value": original_position_value,
            "original_risk_amount": original_risk_amount,
        }

    def _quantity_allowed_by_risk(
        self,
        remaining_risk: float,
        risk_per_share: float,
        original_quantity: int,
    ) -> int:
        """Calculate maximum quantity allowed by remaining risk."""

        if original_quantity <= 0:
            return 0

        if risk_per_share <= 0:
            return original_quantity

        return min(
            original_quantity,
            int(remaining_risk // risk_per_share),
        )

    def _quantity_allowed_by_exposure(
        self,
        remaining_exposure: float,
        entry_price: float,
        original_quantity: int,
    ) -> int:
        """Calculate maximum quantity allowed by exposure."""

        if original_quantity <= 0:
            return 0

        if entry_price <= 0:
            return original_quantity

        return min(
            original_quantity,
            int(remaining_exposure // entry_price),
        )

    def _quantity_allowed_by_capital(
        self,
        remaining_capital: float,
        entry_price: float,
        original_quantity: int,
    ) -> int:
        """Calculate maximum quantity allowed by available capital."""

        if original_quantity <= 0:
            return 0

        if entry_price <= 0:
            return original_quantity

        return min(
            original_quantity,
            int(remaining_capital // entry_price),
        )

    def _quantity_allowed_by_sector(
        self,
        remaining_sector_exposure: float,
        entry_price: float,
        original_quantity: int,
    ) -> int:
        """Calculate maximum quantity allowed by sector exposure."""

        if original_quantity <= 0:
            return 0

        if entry_price <= 0:
            return original_quantity

        return min(
            original_quantity,
            int(remaining_sector_exposure // entry_price),
        )

    def _build_reasons(
        self,
        normalized: Mapping[str, Any],
        approved: bool,
        scaled: bool,
        rejection_reason: str,
        adjusted_quantity: int,
    ) -> Tuple[str, ...]:
        """Build human-readable allocation reasons."""

        reasons: List[str] = []

        if not bool(normalized["requested_execute"]):
            reasons.append(
                "Trade was not selected by the priority engine."
            )

        if approved and not scaled:
            reasons.append(
                "Full requested quantity fits all portfolio risk limits."
            )

        if approved and scaled:
            reasons.append(
                "Quantity was reduced to fit remaining portfolio limits."
            )

        if adjusted_quantity > 0:
            reasons.append(
                f"Final approved quantity is {adjusted_quantity}."
            )

        if rejection_reason:
            reasons.append(rejection_reason)

        return tuple(reasons)

    def allocate(
        self,
        candidates: Iterable[Any],
        starting_capital: float,
        available_capital: Optional[float] = None,
        existing_daily_risk: float = 0.0,
        existing_portfolio_exposure: float = 0.0,
        existing_sector_exposure: Optional[
            Mapping[str, float]
        ] = None,
    ) -> List[RiskBudgetResult]:
        """
        Allocate risk budget across ranked candidates.

        Candidates are processed by priority rank and priority score.

        Parameters
        ----------
        candidates:
            TradePriorityResult objects or equivalent dictionaries.

        starting_capital:
            Portfolio capital used to calculate percentage limits.

        available_capital:
            Cash available for new positions. Defaults to starting capital
            minus existing portfolio exposure.

        existing_daily_risk:
            Risk already consumed by existing or completed trades today.

        existing_portfolio_exposure:
            Current value of all open positions.

        existing_sector_exposure:
            Optional mapping of sector names to current exposure values.
        """

        starting_capital = self._positive_float(
            starting_capital,
            "starting_capital",
        )

        existing_daily_risk = self._non_negative_float(
            existing_daily_risk,
            "existing_daily_risk",
        )

        existing_portfolio_exposure = self._non_negative_float(
            existing_portfolio_exposure,
            "existing_portfolio_exposure",
        )

        if available_capital is None:
            available_capital = max(
                0.0,
                starting_capital -
                existing_portfolio_exposure,
            )
        else:
            available_capital = self._non_negative_float(
                available_capital,
                "available_capital",
            )

        maximum_daily_risk = (
            starting_capital *
            self.maximum_daily_risk_percent /
            100.0
        )

        maximum_portfolio_exposure = (
            starting_capital *
            self.maximum_portfolio_exposure_percent /
            100.0
        )

        maximum_sector_exposure = (
            maximum_portfolio_exposure *
            self.maximum_sector_exposure_percent /
            100.0
        )

        normalized_sector_exposure: Dict[str, float] = {}

        if existing_sector_exposure:
            for sector_name, exposure in (
                existing_sector_exposure.items()
            ):
                sector = str(
                    sector_name
                ).strip().upper() or "UNKNOWN"

                normalized_sector_exposure[sector] = (
                    self._non_negative_float(
                        exposure,
                        f"sector exposure for {sector}",
                    )
                )

        normalized_candidates = [
            self._normalize_candidate(candidate, index)
            for index, candidate in enumerate(
                candidates,
                start=1,
            )
        ]

        normalized_candidates.sort(
            key=lambda item: (
                not bool(item["requested_execute"]),
                int(item["priority_rank"]),
                -float(item["priority_score"]),
                int(item["original_rank"]),
                str(item["symbol"]),
            )
        )

        allocated_new_risk = 0.0
        allocated_new_exposure = 0.0
        allocated_new_capital = 0.0

        sector_allocations = dict(
            normalized_sector_exposure
        )

        results: List[RiskBudgetResult] = []

        for item in normalized_candidates:
            symbol = str(item["symbol"])
            sector = str(item["sector"])
            requested_execute = bool(
                item["requested_execute"]
            )

            original_quantity = int(
                item["original_quantity"]
            )

            entry_price = float(
                item["entry_price"]
            )

            stop_loss = float(
                item["stop_loss"]
            )

            risk_per_share = float(
                item["risk_per_share"]
            )

            original_position_value = float(
                item["original_position_value"]
            )

            original_risk_amount = float(
                item["original_risk_amount"]
            )

            remaining_daily_risk = max(
                0.0,
                maximum_daily_risk -
                existing_daily_risk -
                allocated_new_risk,
            )

            remaining_exposure = max(
                0.0,
                maximum_portfolio_exposure -
                existing_portfolio_exposure -
                allocated_new_exposure,
            )

            remaining_capital = max(
                0.0,
                available_capital -
                allocated_new_capital,
            )

            current_sector_exposure = (
                sector_allocations.get(
                    sector,
                    0.0,
                )
            )

            remaining_sector_exposure = max(
                0.0,
                maximum_sector_exposure -
                current_sector_exposure,
            )

            approved = False
            scaled = False
            rejection_reason = ""
            adjusted_quantity = 0

            if not requested_execute:
                rejection_reason = (
                    "Trade was not approved for execution by "
                    "the priority stage."
                )

            elif original_quantity < self.minimum_quantity:
                rejection_reason = (
                    "Requested quantity is below the minimum "
                    "executable quantity."
                )

            elif entry_price <= 0:
                rejection_reason = (
                    "A valid entry price is required for "
                    "risk-budget allocation."
                )

            elif risk_per_share <= 0:
                rejection_reason = (
                    "A valid per-share risk is required for "
                    "risk-budget allocation."
                )

            elif remaining_daily_risk <= 0:
                rejection_reason = (
                    "No daily risk budget remains."
                )

            elif remaining_exposure <= 0:
                rejection_reason = (
                    "No portfolio exposure capacity remains."
                )

            elif remaining_capital <= 0:
                rejection_reason = (
                    "No available capital remains."
                )

            elif remaining_sector_exposure <= 0:
                rejection_reason = (
                    "Sector exposure limit has been reached."
                )

            else:
                risk_quantity = (
                    self._quantity_allowed_by_risk(
                        remaining_risk=
                            remaining_daily_risk,
                        risk_per_share=risk_per_share,
                        original_quantity=
                            original_quantity,
                    )
                )

                exposure_quantity = (
                    self._quantity_allowed_by_exposure(
                        remaining_exposure=
                            remaining_exposure,
                        entry_price=entry_price,
                        original_quantity=
                            original_quantity,
                    )
                )

                capital_quantity = (
                    self._quantity_allowed_by_capital(
                        remaining_capital=
                            remaining_capital,
                        entry_price=entry_price,
                        original_quantity=
                            original_quantity,
                    )
                )

                sector_quantity = (
                    self._quantity_allowed_by_sector(
                        remaining_sector_exposure=
                            remaining_sector_exposure,
                        entry_price=entry_price,
                        original_quantity=
                            original_quantity,
                    )
                )

                allowed_quantity = min(
                    original_quantity,
                    risk_quantity,
                    exposure_quantity,
                    capital_quantity,
                    sector_quantity,
                )

                if not self.allow_position_scaling:
                    if allowed_quantity < original_quantity:
                        allowed_quantity = 0

                if allowed_quantity < self.minimum_quantity:
                    rejection_reason = (
                        "Trade cannot fit within the remaining "
                        "risk, exposure, capital, or sector limits."
                    )
                else:
                    adjusted_quantity = allowed_quantity
                    approved = True
                    scaled = (
                        adjusted_quantity <
                        original_quantity
                    )

            adjusted_position_value = (
                entry_price *
                adjusted_quantity
            )

            allocated_risk_amount = (
                risk_per_share *
                adjusted_quantity
            )

            if approved:
                allocated_new_risk += (
                    allocated_risk_amount
                )

                allocated_new_exposure += (
                    adjusted_position_value
                )

                allocated_new_capital += (
                    adjusted_position_value
                )

                sector_allocations[sector] = (
                    sector_allocations.get(
                        sector,
                        0.0,
                    )
                    + adjusted_position_value
                )

            remaining_daily_risk_after = max(
                0.0,
                maximum_daily_risk -
                existing_daily_risk -
                allocated_new_risk,
            )

            remaining_exposure_after = max(
                0.0,
                maximum_portfolio_exposure -
                existing_portfolio_exposure -
                allocated_new_exposure,
            )

            remaining_capital_after = max(
                0.0,
                available_capital -
                allocated_new_capital,
            )

            reasons = self._build_reasons(
                normalized=item,
                approved=approved,
                scaled=scaled,
                rejection_reason=rejection_reason,
                adjusted_quantity=adjusted_quantity,
            )

            results.append(
                RiskBudgetResult(
                    symbol=symbol,
                    priority_rank=int(
                        item["priority_rank"]
                    ),
                    priority_score=round(
                        float(item["priority_score"]),
                        self.round_values,
                    ),
                    sector=sector,
                    requested_execute=requested_execute,
                    approved=approved,
                    scaled=scaled,
                    rejection_reason=rejection_reason,
                    original_quantity=original_quantity,
                    adjusted_quantity=adjusted_quantity,
                    entry_price=round(
                        entry_price,
                        self.round_values,
                    ),
                    stop_loss=round(
                        stop_loss,
                        self.round_values,
                    ),
                    risk_per_share=round(
                        risk_per_share,
                        self.round_values,
                    ),
                    original_position_value=round(
                        original_position_value,
                        self.round_values,
                    ),
                    adjusted_position_value=round(
                        adjusted_position_value,
                        self.round_values,
                    ),
                    original_risk_amount=round(
                        original_risk_amount,
                        self.round_values,
                    ),
                    allocated_risk_amount=round(
                        allocated_risk_amount,
                        self.round_values,
                    ),
                    daily_risk_remaining=round(
                        remaining_daily_risk_after,
                        self.round_values,
                    ),
                    exposure_remaining=round(
                        remaining_exposure_after,
                        self.round_values,
                    ),
                    capital_remaining=round(
                        remaining_capital_after,
                        self.round_values,
                    ),
                    reasons=reasons,
                )
            )

        return results

    @staticmethod
    def approved_trades(
        results: Iterable[RiskBudgetResult],
    ) -> List[RiskBudgetResult]:
        """Return approved risk-budget results."""

        return [
            result
            for result in results
            if result.approved
        ]

    @staticmethod
    def rejected_trades(
        results: Iterable[RiskBudgetResult],
    ) -> List[RiskBudgetResult]:
        """Return rejected risk-budget results."""

        return [
            result
            for result in results
            if not result.approved
        ]

    @staticmethod
    def execution_queue(
        results: Iterable[RiskBudgetResult],
    ) -> List[RiskBudgetResult]:
        """Return approved trades ordered for execution."""

        return sorted(
            (
                result
                for result in results
                if result.approved
            ),
            key=lambda result: (
                result.priority_rank,
                -result.priority_score,
                result.symbol,
            ),
        )

    @staticmethod
    def results_as_dicts(
        results: Iterable[RiskBudgetResult],
    ) -> List[Dict[str, Any]]:
        """Convert results into plain dictionaries."""

        return [
            result.to_dict()
            for result in results
        ]

    def summarize(
        self,
        results: Iterable[RiskBudgetResult],
        starting_capital: float,
        available_capital: Optional[float] = None,
        existing_daily_risk: float = 0.0,
        existing_portfolio_exposure: float = 0.0,
        existing_sector_exposure: Optional[
            Mapping[str, float]
        ] = None,
    ) -> RiskBudgetSummary:
        """Create a portfolio-level risk allocation summary."""

        results_list = list(results)

        starting_capital = self._positive_float(
            starting_capital,
            "starting_capital",
        )

        existing_daily_risk = self._non_negative_float(
            existing_daily_risk,
            "existing_daily_risk",
        )

        existing_portfolio_exposure = self._non_negative_float(
            existing_portfolio_exposure,
            "existing_portfolio_exposure",
        )

        if available_capital is None:
            available_capital = max(
                0.0,
                starting_capital -
                existing_portfolio_exposure,
            )
        else:
            available_capital = self._non_negative_float(
                available_capital,
                "available_capital",
            )

        maximum_daily_risk = (
            starting_capital *
            self.maximum_daily_risk_percent /
            100.0
        )

        maximum_portfolio_exposure = (
            starting_capital *
            self.maximum_portfolio_exposure_percent /
            100.0
        )

        allocated_new_risk = sum(
            result.allocated_risk_amount
            for result in results_list
            if result.approved
        )

        allocated_new_exposure = sum(
            result.adjusted_position_value
            for result in results_list
            if result.approved
        )

        final_portfolio_exposure = (
            existing_portfolio_exposure +
            allocated_new_exposure
        )

        sector_allocations: Dict[str, int] = {}

        if existing_sector_exposure:
            for sector, exposure in (
                existing_sector_exposure.items()
            ):
                normalized_sector = (
                    str(sector).strip().upper()
                    or "UNKNOWN"
                )

                sector_allocations[normalized_sector] = int(
                    round(float(exposure))
                )

        for result in results_list:
            if not result.approved:
                continue

            sector_allocations[result.sector] = (
                sector_allocations.get(
                    result.sector,
                    0,
                )
                + int(
                    round(
                        result.adjusted_position_value
                    )
                )
            )

        total_original_quantity = sum(
            result.original_quantity
            for result in results_list
        )

        total_adjusted_quantity = sum(
            result.adjusted_quantity
            for result in results_list
            if result.approved
        )

        requested_candidates = sum(
            1
            for result in results_list
            if result.requested_execute
        )

        approved_trades = sum(
            1
            for result in results_list
            if result.approved
        )

        scaled_trades = sum(
            1
            for result in results_list
            if result.approved and result.scaled
        )

        rejected_trades = (
            len(results_list) -
            approved_trades
        )

        remaining_daily_risk = max(
            0.0,
            maximum_daily_risk -
            existing_daily_risk -
            allocated_new_risk,
        )

        remaining_exposure = max(
            0.0,
            maximum_portfolio_exposure -
            final_portfolio_exposure,
        )

        return RiskBudgetSummary(
            total_candidates=len(results_list),
            requested_candidates=requested_candidates,
            approved_trades=approved_trades,
            scaled_trades=scaled_trades,
            rejected_trades=rejected_trades,
            starting_capital=round(
                starting_capital,
                self.round_values,
            ),
            available_capital=round(
                available_capital,
                self.round_values,
            ),
            maximum_daily_risk=round(
                maximum_daily_risk,
                self.round_values,
            ),
            existing_daily_risk=round(
                existing_daily_risk,
                self.round_values,
            ),
            allocated_new_risk=round(
                allocated_new_risk,
                self.round_values,
            ),
            remaining_daily_risk=round(
                remaining_daily_risk,
                self.round_values,
            ),
            maximum_portfolio_exposure=round(
                maximum_portfolio_exposure,
                self.round_values,
            ),
            existing_portfolio_exposure=round(
                existing_portfolio_exposure,
                self.round_values,
            ),
            allocated_new_exposure=round(
                allocated_new_exposure,
                self.round_values,
            ),
            final_portfolio_exposure=round(
                final_portfolio_exposure,
                self.round_values,
            ),
            remaining_exposure=round(
                remaining_exposure,
                self.round_values,
            ),
            total_original_quantity=
                total_original_quantity,
            total_adjusted_quantity=
                total_adjusted_quantity,
            sector_allocations=sector_allocations,
        )


if __name__ == "__main__":
    allocator = RiskBudgetAllocator(
        maximum_daily_risk_percent=1.0,
        maximum_portfolio_exposure_percent=60.0,
        maximum_sector_exposure_percent=40.0,
    )

    sample_candidates = [
        {
            "symbol": "ICICIBANK",
            "sector": "BANKING",
            "priority_rank": 1,
            "priority_score": 85.75,
            "execute": True,
            "final_quantity": 14,
            "entry_price": 1425.5,
            "stop_loss": 1415.5,
            "position_value": 19957.0,
            "risk_amount": 140.0,
        },
        {
            "symbol": "SBIN",
            "sector": "BANKING",
            "priority_rank": 2,
            "priority_score": 81.5,
            "execute": True,
            "final_quantity": 12,
            "entry_price": 1500.0,
            "stop_loss": 1487.5,
            "position_value": 18000.0,
            "risk_amount": 150.0,
        },
        {
            "symbol": "TCS",
            "sector": "IT",
            "priority_rank": 3,
            "priority_score": 74.35,
            "execute": False,
            "final_quantity": 0,
            "entry_price": 3200.0,
            "stop_loss": 3170.0,
            "position_value": 0.0,
            "risk_amount": 0.0,
        },
    ]

    allocation_results = allocator.allocate(
        candidates=sample_candidates,
        starting_capital=100000.0,
        available_capital=50000.0,
        existing_daily_risk=100.0,
        existing_portfolio_exposure=10000.0,
        existing_sector_exposure={
            "BANKING": 5000.0,
        },
    )

    print("\n===== RISK BUDGET RESULTS =====\n")

    for allocation_result in allocation_results:
        print(allocation_result.to_dict())

    allocation_summary = allocator.summarize(
        results=allocation_results,
        starting_capital=100000.0,
        available_capital=50000.0,
        existing_daily_risk=100.0,
        existing_portfolio_exposure=10000.0,
        existing_sector_exposure={
            "BANKING": 5000.0,
        },
    )

    print("\n===== RISK BUDGET SUMMARY =====\n")
    print(allocation_summary.to_dict())
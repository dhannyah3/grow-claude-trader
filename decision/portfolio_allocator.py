"""
Portfolio capital-allocation engine.

This module converts ranked stock-selection candidates into a practical
capital-allocation plan.

The allocator:

- reserves part of the account as cash,
- limits the number of positions,
- allocates more capital to stronger candidates,
- enforces per-position concentration limits,
- rejects positions that are too small,
- calculates whole-share quantities using the latest market price,
- prevents total cash usage from exceeding the deployable capital.

The module is intentionally independent from broker execution. It produces
allocation instructions that can later be passed to the position-sizing,
risk-budget, and execution layers.
"""

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


@dataclass(frozen=True)
class PortfolioAllocationResult:
    """
    Final allocation produced for one stock candidate.
    """

    symbol: str
    rank: int
    score: float
    confidence: float
    last_price: float

    requested_allocation: float
    capped_allocation: float
    cash_used: float
    allocation_percent: float
    quantity: int

    selected: bool
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the allocation result into a plain dictionary.
        """

        return asdict(self)


@dataclass(frozen=True)
class PortfolioAllocationSummary:
    """
    Portfolio-level summary for an allocation run.
    """

    total_capital: float
    reserve_percent: float
    reserve_amount: float
    deployable_capital: float
    total_cash_used: float
    remaining_deployable_cash: float
    total_remaining_cash: float
    selected_positions: int
    rejected_positions: int

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the summary into a plain dictionary.
        """

        return asdict(self)


class PortfolioAllocator:
    """
    Allocate available capital across ranked stock candidates.

    Parameters
    ----------
    cash_reserve_percent:
        Percentage of total capital that must remain unallocated.

    maximum_positions:
        Maximum number of positions that may receive capital.

    maximum_position_percent:
        Maximum percentage of deployable capital that one stock may receive.

    minimum_position_amount:
        Minimum intended allocation for a stock.

    minimum_confidence:
        Minimum candidate confidence required for allocation.

    minimum_score:
        Minimum candidate score required for allocation.

    score_weight:
        Contribution of the candidate score to its allocation weight.

    confidence_weight:
        Contribution of confidence to its allocation weight.

    round_cash_values:
        Number of decimal places used for monetary outputs.
    """

    def __init__(
        self,
        cash_reserve_percent: float = 10.0,
        maximum_positions: int = 3,
        maximum_position_percent: float = 45.0,
        minimum_position_amount: float = 5000.0,
        minimum_confidence: float = 55.0,
        minimum_score: float = 55.0,
        score_weight: float = 0.60,
        confidence_weight: float = 0.40,
        round_cash_values: int = 2,
    ) -> None:
        self.cash_reserve_percent = self._validate_percentage(
            cash_reserve_percent,
            field_name="cash_reserve_percent",
            allow_zero=True,
            maximum=95.0,
        )

        if not isinstance(maximum_positions, int) or maximum_positions <= 0:
            raise ValueError(
                "maximum_positions must be a positive integer."
            )

        self.maximum_positions = maximum_positions

        self.maximum_position_percent = self._validate_percentage(
            maximum_position_percent,
            field_name="maximum_position_percent",
            allow_zero=False,
            maximum=100.0,
        )

        self.minimum_position_amount = self._validate_non_negative_number(
            minimum_position_amount,
            field_name="minimum_position_amount",
        )

        self.minimum_confidence = self._validate_percentage(
            minimum_confidence,
            field_name="minimum_confidence",
            allow_zero=True,
            maximum=100.0,
        )

        self.minimum_score = self._validate_percentage(
            minimum_score,
            field_name="minimum_score",
            allow_zero=True,
            maximum=100.0,
        )

        self.score_weight = self._validate_non_negative_number(
            score_weight,
            field_name="score_weight",
        )

        self.confidence_weight = self._validate_non_negative_number(
            confidence_weight,
            field_name="confidence_weight",
        )

        if self.score_weight + self.confidence_weight <= 0:
            raise ValueError(
                "score_weight and confidence_weight cannot both be zero."
            )

        if not isinstance(round_cash_values, int) or round_cash_values < 0:
            raise ValueError(
                "round_cash_values must be a non-negative integer."
            )

        self.round_cash_values = round_cash_values

    @staticmethod
    def _validate_non_negative_number(
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

    @classmethod
    def _validate_percentage(
        cls,
        value: Any,
        field_name: str,
        allow_zero: bool,
        maximum: float,
    ) -> float:
        numeric_value = cls._validate_non_negative_number(
            value=value,
            field_name=field_name,
        )

        if not allow_zero and numeric_value == 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        if numeric_value > maximum:
            raise ValueError(
                f"{field_name} cannot exceed {maximum}."
            )

        return numeric_value

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            if value is None:
                return default

            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _candidate_to_mapping(
        candidate: Any,
    ) -> Mapping[str, Any]:
        if isinstance(candidate, Mapping):
            return candidate

        if is_dataclass(candidate):
            return asdict(candidate)

        attributes: Dict[str, Any] = {}

        for field_name in (
            "symbol",
            "rank",
            "score",
            "confidence",
            "selected",
            "last_price",
            "entry_price",
            "price",
        ):
            if hasattr(candidate, field_name):
                attributes[field_name] = getattr(
                    candidate,
                    field_name,
                )

        return attributes

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip().upper()

    @staticmethod
    def _lookup_price(
        symbol: str,
        candidate: Mapping[str, Any],
        prices: Optional[Mapping[str, Any]],
    ) -> float:
        """
        Resolve the latest tradable price.

        Price resolution order:

        1. Explicit prices mapping
        2. candidate["last_price"]
        3. candidate["entry_price"]
        4. candidate["price"]
        """

        if prices:
            direct_value = prices.get(symbol)

            if direct_value is None:
                direct_value = prices.get(symbol.upper())

            if direct_value is None:
                direct_value = prices.get(symbol.lower())

            try:
                direct_price = float(direct_value)
            except (TypeError, ValueError):
                direct_price = 0.0

            if direct_price > 0:
                return direct_price

        for field_name in (
            "last_price",
            "entry_price",
            "price",
        ):
            try:
                candidate_price = float(
                    candidate.get(field_name)
                )
            except (TypeError, ValueError):
                candidate_price = 0.0

            if candidate_price > 0:
                return candidate_price

        return 0.0

    def configuration(self) -> Dict[str, Any]:
        """
        Return the active allocator configuration.
        """

        return {
            "cash_reserve_percent": self.cash_reserve_percent,
            "maximum_positions": self.maximum_positions,
            "maximum_position_percent": (
                self.maximum_position_percent
            ),
            "minimum_position_amount": (
                self.minimum_position_amount
            ),
            "minimum_confidence": self.minimum_confidence,
            "minimum_score": self.minimum_score,
            "score_weight": self.score_weight,
            "confidence_weight": self.confidence_weight,
            "round_cash_values": self.round_cash_values,
        }

    def _candidate_weight(
        self,
        score: float,
        confidence: float,
    ) -> float:
        total_weight = (
            self.score_weight
            + self.confidence_weight
        )

        weighted_value = (
            (score * self.score_weight)
            + (confidence * self.confidence_weight)
        )

        return max(
            0.0,
            weighted_value / total_weight,
        )

    def _prepare_candidates(
        self,
        candidates: Iterable[Any],
        prices: Optional[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        prepared: List[Dict[str, Any]] = []
        seen_symbols = set()

        for original_position, raw_candidate in enumerate(
            candidates,
            start=1,
        ):
            candidate = self._candidate_to_mapping(
                raw_candidate
            )

            symbol = self._normalize_symbol(
                candidate.get("symbol")
            )

            if not symbol or symbol in seen_symbols:
                continue

            seen_symbols.add(symbol)

            score = max(
                0.0,
                min(
                    100.0,
                    self._safe_float(
                        candidate.get("score")
                    ),
                ),
            )

            confidence = max(
                0.0,
                min(
                    100.0,
                    self._safe_float(
                        candidate.get(
                            "confidence",
                            score,
                        )
                    ),
                ),
            )

            selected_value = candidate.get(
                "selected",
                True,
            )

            selected = bool(selected_value)

            rank_value = candidate.get(
                "rank",
                original_position,
            )

            try:
                rank = int(rank_value)
            except (TypeError, ValueError):
                rank = original_position

            last_price = self._lookup_price(
                symbol=symbol,
                candidate=candidate,
                prices=prices,
            )

            prepared.append(
                {
                    "symbol": symbol,
                    "rank": max(1, rank),
                    "score": score,
                    "confidence": confidence,
                    "last_price": last_price,
                    "eligible": (
                        selected
                        and score >= self.minimum_score
                        and confidence
                        >= self.minimum_confidence
                        and last_price > 0
                    ),
                    "weight": self._candidate_weight(
                        score=score,
                        confidence=confidence,
                    ),
                }
            )

        prepared.sort(
            key=lambda item: (
                not item["eligible"],
                -item["weight"],
                item["rank"],
                item["symbol"],
            )
        )

        return prepared

    def _build_rejected_result(
        self,
        candidate: Mapping[str, Any],
        reasons: Sequence[str],
    ) -> PortfolioAllocationResult:
        return PortfolioAllocationResult(
            symbol=str(candidate["symbol"]),
            rank=int(candidate["rank"]),
            score=round(float(candidate["score"]), 2),
            confidence=round(
                float(candidate["confidence"]),
                2,
            ),
            last_price=round(
                float(candidate["last_price"]),
                2,
            ),
            requested_allocation=0.0,
            capped_allocation=0.0,
            cash_used=0.0,
            allocation_percent=0.0,
            quantity=0,
            selected=False,
            reasons=list(reasons),
        )

    def allocate(
        self,
        candidates: Iterable[Any],
        total_capital: float,
        prices: Optional[Mapping[str, Any]] = None,
    ) -> List[PortfolioAllocationResult]:
        """
        Allocate capital across eligible candidates.

        Parameters
        ----------
        candidates:
            Ranked stock candidates. Each item may be a dictionary,
            dataclass, or object with compatible attributes.

        total_capital:
            Total account capital available before the reserve is applied.

        prices:
            Optional symbol-to-last-price mapping. This is the recommended
            input when candidates come directly from StockSelector because
            StockSelectionResult does not own market-price data.

        Returns
        -------
        list[PortfolioAllocationResult]
            Allocation results for all supplied unique symbols.
        """

        capital = self._validate_non_negative_number(
            total_capital,
            field_name="total_capital",
        )

        prepared = self._prepare_candidates(
            candidates=candidates,
            prices=prices,
        )

        if not prepared:
            return []

        reserve_amount = (
            capital
            * self.cash_reserve_percent
            / 100.0
        )

        deployable_capital = max(
            0.0,
            capital - reserve_amount,
        )

        eligible_candidates = [
            item
            for item in prepared
            if item["eligible"]
        ][: self.maximum_positions]

        eligible_symbols = {
            item["symbol"]
            for item in eligible_candidates
        }

        total_candidate_weight = sum(
            float(item["weight"])
            for item in eligible_candidates
        )

        maximum_position_amount = (
            deployable_capital
            * self.maximum_position_percent
            / 100.0
        )

        remaining_cash = deployable_capital
        selected_results: Dict[
            str,
            PortfolioAllocationResult
        ] = {}

        for candidate in eligible_candidates:
            reasons: List[str] = []

            if total_candidate_weight <= 0:
                requested_allocation = 0.0
            else:
                requested_allocation = (
                    deployable_capital
                    * float(candidate["weight"])
                    / total_candidate_weight
                )

            capped_allocation = min(
                requested_allocation,
                maximum_position_amount,
                remaining_cash,
            )

            last_price = float(
                candidate["last_price"]
            )

            quantity = int(
                capped_allocation // last_price
            )

            cash_used = quantity * last_price

            if requested_allocation > maximum_position_amount:
                reasons.append(
                    "Allocation was limited by the maximum "
                    "position-size rule."
                )

            if capped_allocation < requested_allocation:
                reasons.append(
                    "Allocation was reduced to remain within "
                    "available deployable capital."
                )

            if capped_allocation < self.minimum_position_amount:
                reasons.append(
                    "Proposed allocation was below the minimum "
                    "position amount."
                )

            if quantity <= 0:
                reasons.append(
                    "Available allocation could not purchase "
                    "one whole share."
                )

            if (
                cash_used > 0
                and cash_used
                < self.minimum_position_amount
            ):
                reasons.append(
                    "Whole-share cash usage was below the minimum "
                    "position amount."
                )

            selected = (
                quantity > 0
                and cash_used
                >= self.minimum_position_amount
                and cash_used <= remaining_cash
            )

            if selected:
                remaining_cash -= cash_used

                reasons.append(
                    "Candidate received a confidence-weighted "
                    "portfolio allocation."
                )

                reasons.append(
                    "Allocation respects the configured cash "
                    "reserve and position concentration limit."
                )
            else:
                quantity = 0
                cash_used = 0.0
                capped_allocation = 0.0

                reasons.append(
                    "Candidate was not included in the final "
                    "portfolio allocation."
                )

            allocation_percent = (
                cash_used / capital * 100.0
                if capital > 0
                else 0.0
            )

            selected_results[
                str(candidate["symbol"])
            ] = PortfolioAllocationResult(
                symbol=str(candidate["symbol"]),
                rank=int(candidate["rank"]),
                score=round(
                    float(candidate["score"]),
                    2,
                ),
                confidence=round(
                    float(candidate["confidence"]),
                    2,
                ),
                last_price=round(
                    last_price,
                    2,
                ),
                requested_allocation=round(
                    requested_allocation,
                    self.round_cash_values,
                ),
                capped_allocation=round(
                    capped_allocation,
                    self.round_cash_values,
                ),
                cash_used=round(
                    cash_used,
                    self.round_cash_values,
                ),
                allocation_percent=round(
                    allocation_percent,
                    2,
                ),
                quantity=quantity,
                selected=selected,
                reasons=reasons,
            )

        final_results: List[
            PortfolioAllocationResult
        ] = []

        for candidate in prepared:
            symbol = str(candidate["symbol"])

            existing_result = selected_results.get(
                symbol
            )

            if existing_result is not None:
                final_results.append(
                    existing_result
                )
                continue

            rejection_reasons: List[str] = []

            if symbol not in eligible_symbols:
                if not bool(candidate["eligible"]):
                    if (
                        float(candidate["score"])
                        < self.minimum_score
                    ):
                        rejection_reasons.append(
                            "Candidate score is below the minimum "
                            "allocation threshold."
                        )

                    if (
                        float(candidate["confidence"])
                        < self.minimum_confidence
                    ):
                        rejection_reasons.append(
                            "Candidate confidence is below the "
                            "minimum allocation threshold."
                        )

                    if (
                        float(candidate["last_price"])
                        <= 0
                    ):
                        rejection_reasons.append(
                            "No valid latest market price was "
                            "available."
                        )

                    if not rejection_reasons:
                        rejection_reasons.append(
                            "Candidate was not marked as selected "
                            "by the stock-selection layer."
                        )
                else:
                    rejection_reasons.append(
                        "Candidate exceeded the configured maximum "
                        "number of portfolio positions."
                    )

            rejection_reasons.append(
                "Candidate received no portfolio capital."
            )

            final_results.append(
                self._build_rejected_result(
                    candidate=candidate,
                    reasons=rejection_reasons,
                )
            )

        final_results.sort(
            key=lambda result: (
                not result.selected,
                result.rank,
                -result.score,
                result.symbol,
            )
        )

        return final_results

    def selected_allocations(
        self,
        candidates: Iterable[Any],
        total_capital: float,
        prices: Optional[Mapping[str, Any]] = None,
    ) -> List[PortfolioAllocationResult]:
        """
        Return only allocations selected for execution.
        """

        return [
            result
            for result in self.allocate(
                candidates=candidates,
                total_capital=total_capital,
                prices=prices,
            )
            if result.selected
        ]

    def allocate_as_dicts(
        self,
        candidates: Iterable[Any],
        total_capital: float,
        prices: Optional[Mapping[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return allocation results as plain dictionaries.
        """

        return [
            result.to_dict()
            for result in self.allocate(
                candidates=candidates,
                total_capital=total_capital,
                prices=prices,
            )
        ]

    def summarize(
        self,
        allocations: Sequence[PortfolioAllocationResult],
        total_capital: float,
    ) -> PortfolioAllocationSummary:
        """
        Build a portfolio-level allocation summary.
        """

        capital = self._validate_non_negative_number(
            total_capital,
            field_name="total_capital",
        )

        reserve_amount = (
            capital
            * self.cash_reserve_percent
            / 100.0
        )

        deployable_capital = max(
            0.0,
            capital - reserve_amount,
        )

        total_cash_used = sum(
            result.cash_used
            for result in allocations
            if result.selected
        )

        remaining_deployable_cash = max(
            0.0,
            deployable_capital - total_cash_used,
        )

        selected_positions = sum(
            1
            for result in allocations
            if result.selected
        )

        rejected_positions = (
            len(allocations)
            - selected_positions
        )

        return PortfolioAllocationSummary(
            total_capital=round(
                capital,
                self.round_cash_values,
            ),
            reserve_percent=round(
                self.cash_reserve_percent,
                2,
            ),
            reserve_amount=round(
                reserve_amount,
                self.round_cash_values,
            ),
            deployable_capital=round(
                deployable_capital,
                self.round_cash_values,
            ),
            total_cash_used=round(
                total_cash_used,
                self.round_cash_values,
            ),
            remaining_deployable_cash=round(
                remaining_deployable_cash,
                self.round_cash_values,
            ),
            total_remaining_cash=round(
                capital - total_cash_used,
                self.round_cash_values,
            ),
            selected_positions=selected_positions,
            rejected_positions=rejected_positions,
        )

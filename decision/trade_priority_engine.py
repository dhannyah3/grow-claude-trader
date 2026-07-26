"""
Trade priority engine for the decision layer.

This module ranks risk-approved trading opportunities and determines which
trades may enter the execution queue when the number of candidates exceeds the
available position slots.

The engine is broker-independent. It accepts dictionaries, dataclasses, or
plain objects and returns immutable result objects that can be passed to a
final-decision or execution layer.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class TradePriorityResult:
    """Priority result for one trade candidate."""

    symbol: str
    original_rank: int
    priority_rank: int
    priority_score: float

    approved_by_sizer: bool
    execute: bool
    rejection_reason: str

    strategy_score: float
    confidence: float
    risk_reward_ratio: float
    market_strength: float
    sector_strength: float
    relative_strength: float

    final_quantity: int
    position_value: float
    risk_amount: float

    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a plain dictionary."""

        return asdict(self)


@dataclass(frozen=True)
class TradePrioritySummary:
    """Portfolio-level summary for one ranking run."""

    total_candidates: int
    approved_candidates: int
    executable_trades: int
    queued_but_not_executed: int
    rejected_candidates: int

    available_position_slots: int
    maximum_new_positions: int

    highest_priority_score: float
    average_priority_score: float

    total_execution_value: float
    total_execution_risk: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert the summary to a plain dictionary."""

        return asdict(self)


class TradePriorityEngine:
    """
    Rank approved trade candidates and create an execution queue.

    Parameters
    ----------
    maximum_new_positions:
        Maximum number of new trades the engine may mark for execution.

    minimum_priority_score:
        Minimum final priority score required for execution eligibility.

    strategy_weight, confidence_weight, risk_reward_weight,
    market_weight, sector_weight, relative_strength_weight:
        Weights used to calculate the final priority score. Weights are
        normalized internally and therefore do not need to total exactly 1.0.

    maximum_risk_reward_score:
        Risk/reward ratios are converted to a 0-100 score. This value defines
        the ratio that receives the maximum 100-point contribution.

    round_values:
        Number of decimal places used for numeric output fields.
    """

    def __init__(
        self,
        maximum_new_positions: int = 2,
        minimum_priority_score: float = 55.0,
        strategy_weight: float = 0.30,
        confidence_weight: float = 0.25,
        risk_reward_weight: float = 0.15,
        market_weight: float = 0.10,
        sector_weight: float = 0.10,
        relative_strength_weight: float = 0.10,
        maximum_risk_reward_score: float = 4.0,
        round_values: int = 2,
    ) -> None:
        if not isinstance(maximum_new_positions, int):
            raise ValueError("maximum_new_positions must be an integer.")

        if maximum_new_positions <= 0:
            raise ValueError(
                "maximum_new_positions must be greater than zero."
            )

        if not isinstance(round_values, int) or round_values < 0:
            raise ValueError(
                "round_values must be a non-negative integer."
            )

        self.maximum_new_positions = maximum_new_positions
        self.minimum_priority_score = self._percentage(
            minimum_priority_score,
            "minimum_priority_score",
        )
        self.maximum_risk_reward_score = self._positive_float(
            maximum_risk_reward_score,
            "maximum_risk_reward_score",
        )
        self.round_values = round_values

        raw_weights = {
            "strategy": self._non_negative_float(
                strategy_weight,
                "strategy_weight",
            ),
            "confidence": self._non_negative_float(
                confidence_weight,
                "confidence_weight",
            ),
            "risk_reward": self._non_negative_float(
                risk_reward_weight,
                "risk_reward_weight",
            ),
            "market": self._non_negative_float(
                market_weight,
                "market_weight",
            ),
            "sector": self._non_negative_float(
                sector_weight,
                "sector_weight",
            ),
            "relative_strength": self._non_negative_float(
                relative_strength_weight,
                "relative_strength_weight",
            ),
        }

        total_weight = sum(raw_weights.values())

        if total_weight <= 0:
            raise ValueError("At least one priority weight must be positive.")

        self.weights = {
            name: value / total_weight
            for name, value in raw_weights.items()
        }

    @staticmethod
    def _non_negative_float(value: Any, field_name: str) -> float:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} must be numeric.") from exc

        if numeric_value < 0:
            raise ValueError(f"{field_name} cannot be negative.")

        return numeric_value

    @classmethod
    def _positive_float(cls, value: Any, field_name: str) -> float:
        numeric_value = cls._non_negative_float(value, field_name)

        if numeric_value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")

        return numeric_value

    @classmethod
    def _percentage(cls, value: Any, field_name: str) -> float:
        numeric_value = cls._non_negative_float(value, field_name)

        if numeric_value > 100:
            raise ValueError(f"{field_name} cannot exceed 100.")

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

    @classmethod
    def _first_value(
        cls,
        source: Any,
        field_names: Sequence[str],
        default: Any = None,
    ) -> Any:
        for field_name in field_names:
            value = cls._value(source, field_name, None)

            if value is not None:
                return value

        return default

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))

    def configuration(self) -> Dict[str, Any]:
        """Return the active engine configuration."""

        return {
            "maximum_new_positions": self.maximum_new_positions,
            "minimum_priority_score": self.minimum_priority_score,
            "maximum_risk_reward_score": (
                self.maximum_risk_reward_score
            ),
            "weights": dict(self.weights),
            "round_values": self.round_values,
        }

    def _risk_reward_score(self, risk_reward_ratio: float) -> float:
        normalized = (
            risk_reward_ratio
            / self.maximum_risk_reward_score
            * 100.0
        )
        return self._clamp(normalized, 0.0, 100.0)

    def calculate_priority_score(
        self,
        strategy_score: float,
        confidence: float,
        risk_reward_ratio: float,
        market_strength: float,
        sector_strength: float,
        relative_strength: float,
    ) -> float:
        """Calculate one weighted priority score on a 0-100 scale."""

        strategy_score = self._percentage(
            strategy_score,
            "strategy_score",
        )
        confidence = self._percentage(
            confidence,
            "confidence",
        )
        market_strength = self._percentage(
            market_strength,
            "market_strength",
        )
        sector_strength = self._percentage(
            sector_strength,
            "sector_strength",
        )
        relative_strength = self._percentage(
            relative_strength,
            "relative_strength",
        )
        risk_reward_ratio = self._non_negative_float(
            risk_reward_ratio,
            "risk_reward_ratio",
        )

        risk_reward_score = self._risk_reward_score(
            risk_reward_ratio
        )

        score = (
            strategy_score * self.weights["strategy"]
            + confidence * self.weights["confidence"]
            + risk_reward_score * self.weights["risk_reward"]
            + market_strength * self.weights["market"]
            + sector_strength * self.weights["sector"]
            + relative_strength * self.weights["relative_strength"]
        )

        return round(score, self.round_values)

    def _normalize_candidate(
        self,
        candidate: Any,
        original_rank: int,
    ) -> Dict[str, Any]:
        symbol = str(
            self._first_value(
                candidate,
                ("symbol", "trading_symbol"),
                "",
            )
        ).strip().upper()

        if not symbol:
            raise ValueError("Every trade candidate requires a symbol.")

        approved_by_sizer = bool(
         self._first_value(
           candidate,
          (
            "approved_by_sizer",
            "approved",
            "selected",
            "execute",
        ),
           False,
    )
)

        strategy_score = self._percentage(
            self._first_value(
                candidate,
                ("strategy_score", "score"),
                0.0,
            ),
            "strategy_score",
        )

        confidence = self._percentage(
            self._first_value(
                candidate,
                ("confidence", "claude_confidence", "ai_confidence"),
                0.0,
            ),
            "confidence",
        )

        risk_reward_ratio = self._non_negative_float(
            self._first_value(
                candidate,
                ("risk_reward_ratio", "risk_reward", "rr_ratio"),
                0.0,
            ),
            "risk_reward_ratio",
        )

        market_strength = self._percentage(
            self._first_value(
                candidate,
                ("market_strength", "market_quality"),
                50.0,
            ),
            "market_strength",
        )

        sector_strength = self._percentage(
            self._first_value(
                candidate,
                ("sector_strength", "sector_score"),
                50.0,
            ),
            "sector_strength",
        )

        relative_strength = self._percentage(
            self._first_value(
                candidate,
                ("relative_strength", "relative_strength_score"),
                50.0,
            ),
            "relative_strength",
        )

        final_quantity = int(
            self._first_value(
                candidate,
                ("final_quantity", "quantity"),
                0,
            )
            or 0
        )

        position_value = self._non_negative_float(
            self._first_value(
                candidate,
                ("position_value", "cash_used"),
                0.0,
            ),
            "position_value",
        )

        risk_amount = self._non_negative_float(
            self._first_value(
                candidate,
                ("risk_amount",),
                0.0,
            ),
            "risk_amount",
        )

        priority_score = self.calculate_priority_score(
            strategy_score=strategy_score,
            confidence=confidence,
            risk_reward_ratio=risk_reward_ratio,
            market_strength=market_strength,
            sector_strength=sector_strength,
            relative_strength=relative_strength,
        )

        return {
            "symbol": symbol,
            "original_rank": original_rank,
            "approved_by_sizer": approved_by_sizer,
            "strategy_score": strategy_score,
            "confidence": confidence,
            "risk_reward_ratio": risk_reward_ratio,
            "market_strength": market_strength,
            "sector_strength": sector_strength,
            "relative_strength": relative_strength,
            "final_quantity": final_quantity,
            "position_value": position_value,
            "risk_amount": risk_amount,
            "priority_score": priority_score,
        }

    def _build_reasons(
        self,
        normalized: Mapping[str, Any],
        execute: bool,
        rejection_reason: str,
    ) -> List[str]:
        reasons: List[str] = []

        score = float(normalized["priority_score"])
        strategy_score = float(normalized["strategy_score"])
        confidence = float(normalized["confidence"])
        risk_reward_ratio = float(normalized["risk_reward_ratio"])
        market_strength = float(normalized["market_strength"])
        sector_strength = float(normalized["sector_strength"])
        relative_strength = float(normalized["relative_strength"])

        if strategy_score >= 80:
            reasons.append("Strategy score strongly supports the trade.")
        elif strategy_score >= 65:
            reasons.append("Strategy score provides moderate support.")
        else:
            reasons.append("Strategy score is comparatively weak.")

        if confidence >= 80:
            reasons.append("AI confidence is high.")
        elif confidence >= 65:
            reasons.append("AI confidence is moderate.")
        else:
            reasons.append("AI confidence is below preferred levels.")

        if risk_reward_ratio >= 2.0:
            reasons.append("Risk-reward ratio is favorable.")
        elif risk_reward_ratio > 0:
            reasons.append("Risk-reward ratio is positive but limited.")
        else:
            reasons.append("Risk-reward information is unavailable.")

        positive_context = sum(
            value >= 65
            for value in (
                market_strength,
                sector_strength,
                relative_strength,
            )
        )

        if positive_context >= 2:
            reasons.append(
                "Market, sector, or relative-strength context supports priority."
            )
        elif positive_context == 1:
            reasons.append(
                "One market-context factor supports the opportunity."
            )
        else:
            reasons.append(
                "Market-context confirmation is limited."
            )

        if execute:
            reasons.append(
                "Trade is inside the available execution-slot limit."
            )
        elif rejection_reason:
            reasons.append(rejection_reason)

        reasons.append(
            f"Final weighted priority score is {score:.2f}."
        )

        return reasons

    def rank_trades(
        self,
        candidates: Iterable[Any],
        current_open_positions: int = 0,
        maximum_open_positions: Optional[int] = None,
    ) -> List[TradePriorityResult]:
        """
        Rank candidates and mark the highest-priority trades for execution.

        When maximum_open_positions is supplied, the engine subtracts the
        current open-position count before deciding how many new positions may
        execute.
        """

        if not isinstance(current_open_positions, int):
            raise ValueError("current_open_positions must be an integer.")

        if current_open_positions < 0:
            raise ValueError(
                "current_open_positions cannot be negative."
            )

        if maximum_open_positions is None:
            available_slots = self.maximum_new_positions
        else:
            if not isinstance(maximum_open_positions, int):
                raise ValueError(
                    "maximum_open_positions must be an integer."
                )

            if maximum_open_positions < 0:
                raise ValueError(
                    "maximum_open_positions cannot be negative."
                )

            available_slots = max(
                0,
                maximum_open_positions - current_open_positions,
            )
            available_slots = min(
                available_slots,
                self.maximum_new_positions,
            )

        normalized_candidates = [
            self._normalize_candidate(candidate, index)
            for index, candidate in enumerate(candidates, start=1)
        ]

        normalized_candidates.sort(
            key=lambda item: (
                not bool(item["approved_by_sizer"]),
                -float(item["priority_score"]),
                -float(item["strategy_score"]),
                -float(item["confidence"]),
                int(item["original_rank"]),
                str(item["symbol"]),
            )
        )

        results: List[TradePriorityResult] = []
        execution_count = 0

        for priority_rank, item in enumerate(
            normalized_candidates,
            start=1,
        ):
            approved_by_sizer = bool(item["approved_by_sizer"])
            priority_score = float(item["priority_score"])
            final_quantity = int(item["final_quantity"])

            execute = False
            rejection_reason = ""

            if not approved_by_sizer:
                rejection_reason = (
                    "Trade was rejected by the position-sizing stage."
                )
            elif final_quantity <= 0:
                rejection_reason = (
                    "Trade has no executable quantity."
                )
            elif priority_score < self.minimum_priority_score:
                rejection_reason = (
                    "Priority score is below the configured minimum."
                )
            elif execution_count >= available_slots:
                rejection_reason = (
                    "Trade remains queued because no execution slot is available."
                )
            else:
                execute = True
                execution_count += 1

            reasons = self._build_reasons(
                normalized=item,
                execute=execute,
                rejection_reason=rejection_reason,
            )

            results.append(
                TradePriorityResult(
                    symbol=str(item["symbol"]),
                    original_rank=int(item["original_rank"]),
                    priority_rank=priority_rank,
                    priority_score=round(
                        priority_score,
                        self.round_values,
                    ),
                    approved_by_sizer=approved_by_sizer,
                    execute=execute,
                    rejection_reason=rejection_reason,
                    strategy_score=round(
                        float(item["strategy_score"]),
                        self.round_values,
                    ),
                    confidence=round(
                        float(item["confidence"]),
                        self.round_values,
                    ),
                    risk_reward_ratio=round(
                        float(item["risk_reward_ratio"]),
                        self.round_values,
                    ),
                    market_strength=round(
                        float(item["market_strength"]),
                        self.round_values,
                    ),
                    sector_strength=round(
                        float(item["sector_strength"]),
                        self.round_values,
                    ),
                    relative_strength=round(
                        float(item["relative_strength"]),
                        self.round_values,
                    ),
                    final_quantity=final_quantity,
                    position_value=round(
                        float(item["position_value"]),
                        self.round_values,
                    ),
                    risk_amount=round(
                        float(item["risk_amount"]),
                        self.round_values,
                    ),
                    reasons=reasons,
                )
            )

        return results

    def execution_queue(
        self,
        results: Iterable[TradePriorityResult],
    ) -> List[TradePriorityResult]:
        """Return only trades marked for execution, in priority order."""

        return sorted(
            (
                result
                for result in results
                if result.execute
            ),
            key=lambda result: (
                result.priority_rank,
                result.symbol,
            ),
        )

    def rejected_trades(
        self,
        results: Iterable[TradePriorityResult],
    ) -> List[TradePriorityResult]:
        """Return trades not marked for immediate execution."""

        return sorted(
            (
                result
                for result in results
                if not result.execute
            ),
            key=lambda result: (
                result.priority_rank,
                result.symbol,
            ),
        )

    def rank_as_dicts(
        self,
        candidates: Iterable[Any],
        current_open_positions: int = 0,
        maximum_open_positions: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Rank candidates and return plain dictionaries."""

        return [
            result.to_dict()
            for result in self.rank_trades(
                candidates=candidates,
                current_open_positions=current_open_positions,
                maximum_open_positions=maximum_open_positions,
            )
        ]

    def summarize(
        self,
        results: Iterable[TradePriorityResult],
        current_open_positions: int = 0,
        maximum_open_positions: Optional[int] = None,
    ) -> TradePrioritySummary:
        """Create a portfolio-level summary for ranked results."""

        result_list = list(results)

        if maximum_open_positions is None:
            available_slots = self.maximum_new_positions
        else:
            available_slots = max(
                0,
                maximum_open_positions - current_open_positions,
            )
            available_slots = min(
                available_slots,
                self.maximum_new_positions,
            )

        approved_results = [
            result
            for result in result_list
            if result.approved_by_sizer
            and result.final_quantity > 0
            and result.priority_score >= self.minimum_priority_score
        ]

        executable_results = [
            result
            for result in result_list
            if result.execute
        ]

        priority_scores = [
            result.priority_score
            for result in approved_results
        ]

        highest_priority_score = (
            max(priority_scores)
            if priority_scores
            else 0.0
        )

        average_priority_score = (
            sum(priority_scores) / len(priority_scores)
            if priority_scores
            else 0.0
        )

        return TradePrioritySummary(
            total_candidates=len(result_list),
            approved_candidates=len(approved_results),
            executable_trades=len(executable_results),
            queued_but_not_executed=max(
                0,
                len(approved_results) - len(executable_results),
            ),
            rejected_candidates=(
                len(result_list) - len(approved_results)
            ),
            available_position_slots=available_slots,
            maximum_new_positions=self.maximum_new_positions,
            highest_priority_score=round(
                highest_priority_score,
                self.round_values,
            ),
            average_priority_score=round(
                average_priority_score,
                self.round_values,
            ),
            total_execution_value=round(
                sum(
                    result.position_value
                    for result in executable_results
                ),
                self.round_values,
            ),
            total_execution_risk=round(
                sum(
                    result.risk_amount
                    for result in executable_results
                ),
                self.round_values,
            ),
        )


if __name__ == "__main__":
    engine = TradePriorityEngine(
        maximum_new_positions=2,
        minimum_priority_score=55.0,
    )

    sample_candidates = [
        {
            "symbol": "ICICIBANK",
            "approved": True,
            "strategy_score": 92.0,
            "confidence": 88.0,
            "risk_reward_ratio": 2.2,
            "market_strength": 82.0,
            "sector_strength": 85.0,
            "relative_strength": 90.0,
            "final_quantity": 14,
            "position_value": 19957.0,
            "risk_amount": 140.0,
        },
        {
            "symbol": "SBIN",
            "approved": True,
            "strategy_score": 86.0,
            "confidence": 80.0,
            "risk_reward_ratio": 2.0,
            "market_strength": 78.0,
            "sector_strength": 82.0,
            "relative_strength": 84.0,
            "final_quantity": 25,
            "position_value": 18375.0,
            "risk_amount": 175.0,
        },
        {
            "symbol": "INFY",
            "approved": True,
            "strategy_score": 72.0,
            "confidence": 70.0,
            "risk_reward_ratio": 1.8,
            "market_strength": 68.0,
            "sector_strength": 65.0,
            "relative_strength": 70.0,
            "final_quantity": 10,
            "position_value": 15200.0,
            "risk_amount": 120.0,
        },
    ]

    ranked_results = engine.rank_trades(sample_candidates)

    print("\n===== TRADE PRIORITY RESULTS =====\n")

    for ranked_result in ranked_results:
        print(ranked_result.to_dict())

    print("\n===== EXECUTION QUEUE =====\n")

    for queued_trade in engine.execution_queue(ranked_results):
        print(
            queued_trade.priority_rank,
            queued_trade.symbol,
            queued_trade.priority_score,
        )

    print("\n===== SUMMARY =====\n")
    print(engine.summarize(ranked_results).to_dict())
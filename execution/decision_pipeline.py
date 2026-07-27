"""
Decision Pipeline.

Bridges Market Intelligence and the Final Decision Engine.
"""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from decision.final_decision_engine import (
    FinalDecisionEngine,
    FinalDecisionResult,
)


@dataclass
class DecisionPipelineResult:
    """
    Result returned by the execution pipeline.
    """

    decision_result: FinalDecisionResult
    execution_queue: list
    summary: Dict[str, Any]


class DecisionPipeline:

    def __init__(
        self,
        decision_engine: Optional[
            FinalDecisionEngine
        ] = None,
    ) -> None:

        self.decision_engine = (
            decision_engine
            or FinalDecisionEngine()
        )

    def run(
        self,
        snapshot: Any,
        sector_map: Mapping[str, str],
        total_capital: float,
        prices: Dict[str, Any],
        **kwargs: Any,
    ) -> DecisionPipelineResult:

        result = self.decision_engine.run(
            snapshot=snapshot,
            sector_map=sector_map,
            total_capital=total_capital,
            prices=prices,
            **kwargs,
        )

        return DecisionPipelineResult(
            decision_result=result,
            execution_queue=result.execution_queue,
            summary=result.summary.to_dict(),
        )
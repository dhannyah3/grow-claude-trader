"""
Integration test for the FinalDecisionEngine orchestration pipeline.

This test uses small deterministic test doubles for each decision module.
It verifies that the FinalDecisionEngine:

1. Runs every stage in the correct order.
2. Translates data correctly between stages.
3. Builds a final execution queue.
4. Produces an accurate summary.

Run with:

    python3 -m tests.test_final_decision_engine
"""

from typing import Any, Dict, Iterable, List, Mapping, Optional

from decision.final_decision_engine import FinalDecisionEngine


class TestResult:
    """
    Lightweight result object with the same to_dict interface used by
    the production decision-layer result dataclasses.
    """

    def __init__(self, **values: Any) -> None:
        self.values = values

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.values)


class FakeStockSelector:
    def __init__(self) -> None:
        self.was_called = False

    def select(
        self,
        snapshot: Any,
        sector_map: Mapping[str, str],
    ) -> List[TestResult]:
        self.was_called = True

        assert snapshot is not None
        assert sector_map["ICICIBANK"] == "BANKING"

        return [
            TestResult(
                symbol="ICICIBANK",
                sector="BANKING",
                score=82.0,
                confidence=78.0,
                relative_strength_rank=1,
                relative_strength_percentile=91.0,
                relative_strength_score=88.0,
                relative_return=4.5,
                sector_rank=1,
                sector_percentile=87.0,
                sector_strength_score=84.0,
                sector_relative_return=3.2,
                sector_classification="LEADING",
                market_regime="TRENDING",
                selected=True,
                reasons=[
                    "Strong relative strength.",
                    "Leading sector.",
                ],
            ),
            TestResult(
                symbol="SBIN",
                sector="BANKING",
                score=48.0,
                confidence=51.0,
                relative_strength_rank=8,
                relative_strength_percentile=42.0,
                relative_strength_score=40.0,
                relative_return=-0.5,
                sector_rank=1,
                sector_percentile=87.0,
                sector_strength_score=84.0,
                sector_relative_return=3.2,
                sector_classification="LEADING",
                market_regime="TRENDING",
                selected=False,
                reasons=["Selection score below minimum."],
            ),
        ]


class FakePortfolioAllocator:
    def __init__(self) -> None:
        self.was_called = False
        self.received_candidates: List[Dict[str, Any]] = []

    def allocate(
        self,
        candidates: Iterable[Any],
        total_capital: float,
        prices: Optional[Mapping[str, Any]] = None,
    ) -> List[TestResult]:
        self.was_called = True
        self.received_candidates = list(candidates)

        assert total_capital == 100000.0
        assert prices is not None
        assert prices["ICICIBANK"] == 1400.0

        selected_candidate = next(
            candidate
            for candidate in self.received_candidates
            if candidate["symbol"] == "ICICIBANK"
        )

        assert selected_candidate["selected"] is True
        assert selected_candidate["score"] == 82.0

        return [
            TestResult(
                symbol="ICICIBANK",
                rank=1,
                score=82.0,
                confidence=78.0,
                last_price=1400.0,
                requested_allocation=30000.0,
                capped_allocation=30000.0,
                cash_used=29400.0,
                allocation_percent=29.4,
                quantity=21,
                selected=True,
                reasons=["Capital allocated successfully."],
            ),
            TestResult(
                symbol="SBIN",
                rank=2,
                score=48.0,
                confidence=51.0,
                last_price=800.0,
                requested_allocation=0.0,
                capped_allocation=0.0,
                cash_used=0.0,
                allocation_percent=0.0,
                quantity=0,
                selected=False,
                reasons=["Candidate was not selected."],
            ),
        ]


class FakePositionSizer:
    def __init__(self) -> None:
        self.was_called = False
        self.received_requests: List[Dict[str, Any]] = []

    def size_positions(
        self,
        requests: Iterable[Mapping[str, Any]],
    ) -> List[TestResult]:
        self.was_called = True
        self.received_requests = [
            dict(request)
            for request in requests
        ]

        assert len(self.received_requests) == 1

        request = self.received_requests[0]

        assert request["symbol"] == "ICICIBANK"
        assert request["entry_price"] == 1400.0
        assert request["allocation_cash"] == 29400.0
        assert request["allocation_quantity"] == 21
        assert request["sector"] == "BANKING"

        # With the engine's default 1% stop-loss:
        assert request["stop_loss"] == 1386.0

        # With the engine's default 2:1 reward-to-risk ratio:
        assert request["target_price"] == 1428.0

        return [
            TestResult(
                symbol="ICICIBANK",
                entry_price=1400.0,
                stop_loss=1386.0,
                target_price=1428.0,
                allocation_cash=29400.0,
                allocation_quantity=21,
                risk_quantity=14,
                final_quantity=14,
                position_value=19600.0,
                risk_per_share=14.0,
                risk_amount=196.0,
                reward_per_share=28.0,
                risk_reward_ratio=2.0,
                approved=True,
                limiting_factor="RISK",
                reasons=["Position approved by risk sizing."],
            )
        ]


class FakeTradePriorityEngine:
    def __init__(self) -> None:
        self.was_called = False
        self.received_candidates: List[Dict[str, Any]] = []

    def rank_trades(
        self,
        candidates: Iterable[Any],
        current_open_positions: int = 0,
        maximum_open_positions: Optional[int] = None,
    ) -> List[TestResult]:
        self.was_called = True
        self.received_candidates = list(candidates)

        assert current_open_positions == 0
        assert maximum_open_positions == 3
        assert len(self.received_candidates) == 1

        candidate = self.received_candidates[0]

        assert candidate["symbol"] == "ICICIBANK"
        assert candidate["approved_by_sizer"] is True
        assert candidate["final_quantity"] == 14
        assert candidate["strategy_score"] == 82.0
        assert candidate["confidence"] == 78.0
        assert candidate["relative_strength"] == 88.0
        assert candidate["sector_strength"] == 84.0

        return [
            TestResult(
                symbol="ICICIBANK",
                original_rank=1,
                priority_rank=1,
                priority_score=81.5,
                approved_by_sizer=True,
                execute=True,
                rejection_reason="",
                strategy_score=82.0,
                confidence=78.0,
                risk_reward_ratio=2.0,
                market_strength=82.0,
                sector_strength=84.0,
                relative_strength=88.0,
                final_quantity=14,
                position_value=19600.0,
                risk_amount=196.0,
                reasons=["Highest-priority executable trade."],
            )
        ]


class FakeRiskBudgetAllocator:
    def __init__(self) -> None:
        self.was_called = False
        self.received_candidates: List[Dict[str, Any]] = []

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
    ) -> List[TestResult]:
        self.was_called = True
        self.received_candidates = list(candidates)

        assert starting_capital == 100000.0
        assert available_capital == 90000.0
        assert existing_daily_risk == 100.0
        assert existing_portfolio_exposure == 5000.0
        assert existing_sector_exposure == {
            "BANKING": 5000.0
        }

        assert len(self.received_candidates) == 1

        candidate = self.received_candidates[0]

        assert candidate["symbol"] == "ICICIBANK"
        assert candidate["sector"] == "BANKING"
        assert candidate["requested_execute"] is True
        assert candidate["entry_price"] == 1400.0
        assert candidate["stop_loss"] == 1386.0
        assert candidate["risk_per_share"] == 14.0
        assert candidate["final_quantity"] == 14
        assert candidate["position_value"] == 19600.0
        assert candidate["risk_amount"] == 196.0

        return [
            TestResult(
                symbol="ICICIBANK",
                priority_rank=1,
                priority_score=81.5,
                sector="BANKING",
                requested_execute=True,
                approved=True,
                scaled=True,
                rejection_reason="",
                original_quantity=14,
                adjusted_quantity=13,
                entry_price=1400.0,
                stop_loss=1386.0,
                risk_per_share=14.0,
                original_position_value=19600.0,
                adjusted_position_value=18200.0,
                original_risk_amount=196.0,
                allocated_risk_amount=182.0,
                daily_risk_remaining=718.0,
                exposure_remaining=36800.0,
                capital_remaining=71800.0,
                reasons=[
                    "Approved after risk-budget scaling."
                ],
            )
        ]


def test_complete_pipeline() -> None:
    stock_selector = FakeStockSelector()
    portfolio_allocator = FakePortfolioAllocator()
    position_sizer = FakePositionSizer()
    trade_priority_engine = FakeTradePriorityEngine()
    risk_budget_allocator = FakeRiskBudgetAllocator()

    engine = FinalDecisionEngine(
        stock_selector=stock_selector,
        portfolio_allocator=portfolio_allocator,
        position_sizer=position_sizer,
        trade_priority_engine=trade_priority_engine,
        risk_budget_allocator=risk_budget_allocator,
    )

    snapshot = {
        "stocks": {
            "ICICIBANK": {
                "symbol": "ICICIBANK",
                "last_price": 1400.0,
                "close": 1400.0,
                "sector": "BANKING",
            },
            "SBIN": {
                "symbol": "SBIN",
                "last_price": 800.0,
                "close": 800.0,
                "sector": "BANKING",
            },
        }
    }

    result = engine.run(
        snapshot=snapshot,
        sector_map={
            "ICICIBANK": "BANKING",
            "SBIN": "BANKING",
        },
        total_capital=100000.0,
        prices={
            "ICICIBANK": 1400.0,
            "SBIN": 800.0,
        },
        current_open_positions=0,
        maximum_open_positions=3,
        existing_daily_risk=100.0,
        existing_portfolio_exposure=5000.0,
        existing_sector_exposure={
            "BANKING": 5000.0,
        },
        available_capital=90000.0,
    )

    # Confirm every stage was executed.
    assert stock_selector.was_called is True
    assert portfolio_allocator.was_called is True
    assert position_sizer.was_called is True
    assert trade_priority_engine.was_called is True
    assert risk_budget_allocator.was_called is True

    # Confirm stage result counts.
    assert len(result.stock_selection) == 2
    assert len(result.portfolio_allocation) == 2
    assert len(result.position_sizing) == 1
    assert len(result.trade_priority) == 1
    assert len(result.risk_budget) == 1
    assert len(result.execution_queue) == 1

    # Confirm final execution order.
    trade = result.execution_queue[0]

    assert trade["symbol"] == "ICICIBANK"
    assert trade["side"] == "BUY"
    assert trade["quantity"] == 13
    assert trade["entry_price"] == 1400.0
    assert trade["stop_loss"] == 1386.0
    assert trade["target_price"] == 1428.0
    assert trade["position_value"] == 18200.0
    assert trade["risk_amount"] == 182.0
    assert trade["priority_rank"] == 1
    assert trade["priority_score"] == 81.5
    assert trade["confidence"] == 78.0
    assert trade["sector"] == "BANKING"
    assert trade["market_regime"] == "TRENDING"
    assert trade["scaled_by_risk_budget"] is True
    assert trade["approved"] is True

    # Confirm summary values.
    summary = result.summary

    assert summary.selected_candidates == 1
    assert summary.allocated_positions == 1
    assert summary.approved_position_sizes == 1
    assert summary.executable_priority_trades == 1
    assert summary.risk_approved_trades == 1
    assert summary.risk_rejected_trades == 0
    assert summary.total_execution_value == 18200.0
    assert summary.total_execution_risk == 182.0

    # Confirm full result serialization.
    serialized = result.to_dict()

    assert serialized["summary"]["selected_candidates"] == 1
    assert serialized["execution_queue"][0]["symbol"] == (
        "ICICIBANK"
    )
    assert serialized["execution_queue"][0]["quantity"] == 13

    print("\n===== FINAL DECISION ENGINE TEST =====\n")
    print("Stock selection stage: PASSED")
    print("Portfolio allocation stage: PASSED")
    print("Position sizing stage: PASSED")
    print("Trade priority stage: PASSED")
    print("Risk budget stage: PASSED")
    print("Execution queue stage: PASSED")
    print("Summary generation: PASSED")

    print("\n===== FINAL EXECUTION QUEUE =====\n")
    print(result.execution_queue)

    print("\n===== FINAL SUMMARY =====\n")
    print(result.summary.to_dict())

    print("\nFinalDecisionEngine integration test passed.")


if __name__ == "__main__":
    test_complete_pipeline()
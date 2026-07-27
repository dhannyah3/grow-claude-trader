"""
Integration test for the complete decision pipeline.

Validates:

scan results
    -> LiveSnapshotBuilder
    -> MarketIntelligenceSnapshot
    -> DecisionContext
    -> DecisionPipeline
    -> FinalDecisionEngine
    -> execution queue
    -> merged approved scanner results
"""

from typing import Any, Dict, List

from decision.decision_context import DecisionContext
from decision.snapshot_adapter import SnapshotAdapter
from execution.decision_pipeline import DecisionPipeline
from market_intelligence.live_snapshot_builder import (
    LiveSnapshotBuilder,
)


class MockTrader:
    """
    Minimal trader object required by DecisionContext.
    """

    def __init__(
        self,
        cash_balance: float = 100000.0,
    ) -> None:
        self.cash_balance = float(
            cash_balance
        )


def build_scan_results() -> List[
    Dict[str, Any]
]:
    """
    Create realistic scanner-style test data.
    """

    return [
        {
            "symbol": "INFY",
            "action": "BUY",
            "strategy": "ORB_BREAKOUT",
            "suggested_entry": 1540.50,
            "suggested_stop_loss": 1525.00,
            "suggested_target": 1571.50,
            "strategy_score": 88.0,
            "confidence": 85.0,
            "sector": "IT",
            "market_regime": {
                "regime": "BULLISH",
                "trend": "UPTREND",
                "volatility": "NORMAL",
            },
            "relative_strength": 82.0,
            "sector_strength": 78.0,
            "market_brain": {
                "should_trade": True,
                "confidence": 85.0,
            },
            "market_intelligence": {
                "market_quality": 80.0,
            },
        },
        {
            "symbol": "TCS",
            "action": "BUY",
            "strategy": "VWAP_PULLBACK",
            "suggested_entry": 3625.75,
            "suggested_stop_loss": 3595.00,
            "suggested_target": 3687.25,
            "strategy_score": 76.0,
            "confidence": 74.0,
            "sector": "IT",
            "market_regime": {
                "regime": "BULLISH",
                "trend": "UPTREND",
                "volatility": "NORMAL",
            },
            "relative_strength": 70.0,
            "sector_strength": 78.0,
            "market_brain": {
                "should_trade": True,
                "confidence": 74.0,
            },
            "market_intelligence": {
                "market_quality": 72.0,
            },
        },
        {
            "symbol": "SBIN",
            "action": "BUY",
            "strategy": "ORB_BREAKOUT",
            "suggested_entry": 845.20,
            "suggested_stop_loss": 836.00,
            "suggested_target": 863.60,
            "strategy_score": 81.0,
            "confidence": 79.0,
            "sector": "BANKING",
            "market_regime": {
                "regime": "BULLISH",
                "trend": "UPTREND",
                "volatility": "NORMAL",
            },
            "relative_strength": 77.0,
            "sector_strength": 74.0,
            "market_brain": {
                "should_trade": True,
                "confidence": 79.0,
            },
            "market_intelligence": {
                "market_quality": 76.0,
            },
        },
    ]


def print_snapshot(
    snapshot: Dict[str, Any],
) -> None:
    """
    Print the generated intelligence snapshot.
    """

    print(
        "\n===== LIVE INTELLIGENCE SNAPSHOT ====="
    )

    print(
        "Symbols analyzed:",
        snapshot.get(
            "symbols_analyzed",
            0,
        ),
    )

    print(
        "Sectors analyzed:",
        snapshot.get(
            "sectors_analyzed",
            0,
        ),
    )

    print(
        "\nRelative strength:"
    )

    for item in snapshot.get(
        "relative_strength",
        [],
    ):
        print(item)

    print(
        "\nSector strength:"
    )

    for item in snapshot.get(
        "sector_strength",
        [],
    ):
        print(item)

    print(
        "\nMarket regime:"
    )

    print(
        snapshot.get(
            "market_regime",
            {},
        )
    )


def run_test() -> None:
    """
    Run the complete decision-pipeline integration test.
    """

    scan_results = (
        build_scan_results()
    )

    trader = MockTrader(
        cash_balance=100000.0
    )

    # Build the official intelligence snapshot dataclass.
    snapshot_object = (
        LiveSnapshotBuilder.build(
            scan_results
        )
    )

    # FinalDecisionEngine and StockSelector consume mappings,
    # so convert the dataclass into its dictionary form.
    snapshot = (
        snapshot_object.to_dict()
    )

    context = DecisionContext.build(
        scan_results=scan_results,
        trader=trader,
    )

    print_snapshot(
        snapshot
    )

    print(
        "\n===== DECISION CONTEXT ====="
    )

    print(
        "Total capital:",
        context["total_capital"],
    )

    print(
        "Sector map:",
        context["sector_map"],
    )

    print(
        "Prices:",
        context["prices"],
    )

    pipeline = DecisionPipeline()

    pipeline_result = pipeline.run(
        snapshot=snapshot,
        sector_map=context[
            "sector_map"
        ],
        total_capital=context[
            "total_capital"
        ],
        prices=context[
            "prices"
        ],
        available_capital=context[
            "total_capital"
        ],
        current_open_positions=0,
        maximum_open_positions=3,
        existing_daily_risk=0.0,
        existing_portfolio_exposure=0.0,
        existing_sector_exposure={},
    )

    execution_queue = (
        pipeline_result.execution_queue
    )

    approved_results = (
        SnapshotAdapter.merge_execution_queue(
            scan_results=scan_results,
            execution_queue=(
                execution_queue
            ),
        )
    )

    print(
        "\n===== DECISION PIPELINE SUMMARY ====="
    )

    print(
        pipeline_result.summary
    )

    print(
        "\n===== EXECUTION QUEUE ====="
    )

    if execution_queue:
        for item in execution_queue:
            print(item)
    else:
        print(
            "No trades entered the execution queue."
        )

    print(
        "\n===== MERGED APPROVED RESULTS ====="
    )

    if approved_results:
        for item in approved_results:
            print(item)
    else:
        print(
            "No approved scanner results were merged."
        )

    # ---------------------------------
    # Base result validations
    # ---------------------------------

    assert isinstance(
        execution_queue,
        list,
    ), (
        "Execution queue must be a list."
    )

    assert isinstance(
        pipeline_result.summary,
        dict,
    ), (
        "Pipeline summary must be a dictionary."
    )

    assert (
        snapshot[
            "symbols_analyzed"
        ]
        == len(scan_results)
    ), (
        "Snapshot did not analyze every "
        "scanner result."
    )

    assert snapshot[
        "relative_strength"
    ], (
        "Relative-strength results are empty."
    )

    assert snapshot[
        "sector_strength"
    ], (
        "Sector-strength results are empty."
    )

    # Confirm ranking fields required by StockSelector.
    for item in snapshot[
        "relative_strength"
    ]:
        assert (
            "symbol" in item
        )

        assert (
            "rank" in item
        )

        assert (
            "percentile_rank" in item
        )

        assert (
            "relative_return" in item
        )

    for item in snapshot[
        "sector_strength"
    ]:
        assert (
            "sector" in item
        )

        assert (
            "rank" in item
        )

        assert (
            "percentile_rank" in item
        )

        assert (
            "classification" in item
        )

        assert (
            "strongest_stock" in item
        )

        assert (
            "weakest_stock" in item
        )

    snapshot_symbols = {
        str(
            item["symbol"]
        ).strip().upper()
        for item in snapshot[
            "relative_strength"
        ]
    }

    # ---------------------------------
    # Execution queue validations
    # ---------------------------------

    for item in execution_queue:
        assert isinstance(
            item,
            dict,
        ), (
            "Each execution queue item "
            "must be a dictionary."
        )

        assert (
            item.get(
                "approved"
            )
            is True
        ), (
            "Execution queue contains "
            "an unapproved trade."
        )

        assert (
            int(
                item.get(
                    "quantity",
                    0,
                )
            )
            > 0
        ), (
            "Approved trade quantity "
            "must be greater than zero."
        )

        symbol = str(
            item.get(
                "symbol",
                "",
            )
        ).strip().upper()

        assert (
            symbol
            in snapshot_symbols
        ), (
            f"{symbol} was not found in "
            "the intelligence snapshot."
        )

    # ---------------------------------
    # Merged result validations
    # ---------------------------------

    for item in approved_results:
        assert (
            item.get(
                "decision_approved"
            )
            is True
        ), (
            "Merged result was not "
            "decision-approved."
        )

        assert (
            int(
                item.get(
                    "decision_quantity",
                    0,
                )
            )
            > 0
        ), (
            "Merged decision quantity "
            "must be greater than zero."
        )

        assert (
            "strategy" in item
        )

        assert (
            "market_brain" in item
        )

        assert (
            "market_intelligence"
            in item
        )

    print(
        "\nDecision pipeline integration "
        "test passed."
    )


if __name__ == "__main__":
    run_test()
from decision.portfolio_allocator import PortfolioAllocator


def main():
    candidates = [
        {
            "symbol": "ICICIBANK",
            "rank": 1,
            "score": 96.0,
            "confidence": 96.0,
            "selected": True,
        },
        {
            "symbol": "SBIN",
            "rank": 2,
            "score": 88.3,
            "confidence": 88.0,
            "selected": True,
        },
        {
            "symbol": "INFY",
            "rank": 3,
            "score": 43.75,
            "confidence": 44.0,
            "selected": False,
        },
    ]

    prices = {
        "ICICIBANK": 1425.50,
        "SBIN": 735.20,
        "INFY": 1632.80,
    }

    allocator = PortfolioAllocator(
        cash_reserve_percent=10.0,
        maximum_positions=2,
        maximum_position_percent=45.0,
        minimum_position_amount=5000.0,
    )

    allocations = allocator.allocate(
        candidates=candidates,
        total_capital=100000.0,
        prices=prices,
    )

    summary = allocator.summarize(
        allocations,
        total_capital=100000.0,
    )

    print("\n===== PORTFOLIO ALLOCATION =====\n")

    for allocation in allocations:
        print(
            {
                "symbol": allocation.symbol,
                "selected": allocation.selected,
                "cash_used": allocation.cash_used,
                "quantity": allocation.quantity,
                "allocation_percent": allocation.allocation_percent,
            }
        )

        for reason in allocation.reasons:
            print(f"  - {reason}")

        print()

    print("===== SUMMARY =====\n")
    print(summary.to_dict())

    selected = [a for a in allocations if a.selected]

    assert len(selected) == 2
    assert selected[0].symbol == "ICICIBANK"
    assert selected[1].symbol == "SBIN"

    assert summary.selected_positions == 2
    assert summary.rejected_positions == 1

    assert (
        summary.total_cash_used
        <= summary.deployable_capital
    )

    assert summary.total_remaining_cash >= 0

    print("\n✅ Portfolio allocator test passed.")


if __name__ == "__main__":
    main()

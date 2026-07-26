from decision.risk_budget_allocator import RiskBudgetAllocator


def main():
    allocator = RiskBudgetAllocator(
        maximum_daily_risk_percent=1.0,
        maximum_portfolio_exposure_percent=60.0,
        maximum_sector_exposure_percent=40.0,
    )

    candidates = [
        {
            "symbol": "ICICIBANK",
            "sector": "BANKING",
            "priority_rank": 1,
            "priority_score": 85.75,
            "execute": True,
            "final_quantity": 14,
            "entry_price": 1425.5,
            "stop_loss": 1415.5,
            "position_value": 19957,
            "risk_amount": 140,
        },
        {
            "symbol": "SBIN",
            "sector": "BANKING",
            "priority_rank": 2,
            "priority_score": 81.50,
            "execute": True,
            "final_quantity": 12,
            "entry_price": 1500,
            "stop_loss": 1487.5,
            "position_value": 18000,
            "risk_amount": 150,
        },
        {
            "symbol": "TCS",
            "sector": "IT",
            "priority_rank": 3,
            "priority_score": 74.35,
            "execute": False,
            "final_quantity": 0,
            "entry_price": 3200,
            "stop_loss": 3170,
            "position_value": 0,
            "risk_amount": 0,
        },
    ]

    results = allocator.allocate(
        candidates=candidates,
        starting_capital=100000,
        available_capital=50000,
        existing_daily_risk=100,
        existing_portfolio_exposure=10000,
        existing_sector_exposure={
            "BANKING": 5000
        },
    )

    print("\n===== RISK BUDGET RESULTS =====\n")

    for result in results:
        print(result.to_dict())

    summary = allocator.summarize(
        results,
        starting_capital=100000,
        available_capital=50000,
        existing_daily_risk=100,
        existing_portfolio_exposure=10000,
        existing_sector_exposure={
            "BANKING": 5000
        },
    )

    print("\n===== SUMMARY =====\n")

    print(summary.to_dict())

    print("\n✅ Risk Budget Allocator test passed.")


if __name__ == "__main__":
    main()
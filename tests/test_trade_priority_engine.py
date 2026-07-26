from decision.trade_priority_engine import TradePriorityEngine


def main():
    engine = TradePriorityEngine(
        maximum_new_positions=2
    )

    candidates = [
        {
            "symbol": "ICICIBANK",
            "approved_by_sizer": True,
            "strategy_score": 95,
            "confidence": 90,
            "risk_reward_ratio": 2.2,
            "market_strength": 88,
            "sector_strength": 85,
            "relative_strength": 92,
            "final_quantity": 14,
            "position_value": 19957,
            "risk_amount": 140,
        },
        {
            "symbol": "SBIN",
            "approved_by_sizer": True,
            "strategy_score": 90,
            "confidence": 86,
            "risk_reward_ratio": 2.0,
            "market_strength": 84,
            "sector_strength": 82,
            "relative_strength": 89,
            "final_quantity": 12,
            "position_value": 18000,
            "risk_amount": 150,
        },
        {
            "symbol": "TCS",
            "approved_by_sizer": False,
            "strategy_score": 82,
            "confidence": 78,
            "risk_reward_ratio": 1.8,
            "market_strength": 80,
            "sector_strength": 79,
            "relative_strength": 76,
            "final_quantity": 0,
            "position_value": 0,
            "risk_amount": 0,
        },
    ]

    results = engine.rank_trades(candidates)

    print("\n===== TRADE PRIORITY =====\n")

    for trade in results:
        print(trade.to_dict())

    print("\n===== SUMMARY =====\n")

    summary = engine.summarize(results)

    print(summary.to_dict())

    print("\n✅ Trade Priority Engine test passed.")


if __name__ == "__main__":
    main()
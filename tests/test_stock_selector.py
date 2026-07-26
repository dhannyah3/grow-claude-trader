from decision.stock_selector import StockSelector


def build_sample_snapshot():
    return {
        "timestamp": "2026-07-26T09:30:00",
        "benchmark_returns": {
            20: 2.4,
        },
        "market_regime": {
            "regime": "TRENDING",
            "trend": "TRENDING",
            "volatility": "MEDIUM",
        },
        "relative_strength": [
            {
                "symbol": "ICICIBANK",
                "weighted_stock_return": 8.2,
                "weighted_benchmark_return": 2.4,
                "relative_return": 5.8,
                "relative_strength_score": 88.0,
                "percentile_rank": 95.0,
                "rank": 1,
                "observations": 100,
            },
            {
                "symbol": "SBIN",
                "weighted_stock_return": 6.7,
                "weighted_benchmark_return": 2.4,
                "relative_return": 4.3,
                "relative_strength_score": 80.0,
                "percentile_rank": 82.0,
                "rank": 2,
                "observations": 100,
            },
            {
                "symbol": "INFY",
                "weighted_stock_return": 1.2,
                "weighted_benchmark_return": 2.4,
                "relative_return": -1.2,
                "relative_strength_score": 38.0,
                "percentile_rank": 25.0,
                "rank": 3,
                "observations": 100,
            },
        ],
        "sector_strength": [
            {
                "sector": "BANKING",
                "rank": 1,
                "percentile_rank": 92.0,
                "sector_score": 85.0,
                "classification": "LEADING",
                "average_return": 7.0,
                "median_return": 6.5,
                "benchmark_return": 2.4,
                "relative_return": 4.6,
                "positive_stock_ratio": 0.90,
                "stock_count": 5,
                "strongest_stock": "ICICIBANK",
                "weakest_stock": "HDFCBANK",
                "lookback": 20,
            },
            {
                "sector": "IT",
                "rank": 2,
                "percentile_rank": 35.0,
                "sector_score": 42.0,
                "classification": "NEUTRAL",
                "average_return": 1.5,
                "median_return": 1.2,
                "benchmark_return": 2.4,
                "relative_return": -0.9,
                "positive_stock_ratio": 0.40,
                "stock_count": 4,
                "strongest_stock": "TCS",
                "weakest_stock": "INFY",
                "lookback": 20,
            },
        ],
        "symbols_analyzed": 3,
        "sectors_analyzed": 2,
        "metadata": {
            "benchmark_lookback": 20,
            "primary_benchmark_return": 2.4,
        },
    }


def main():
    snapshot = build_sample_snapshot()

    sector_map = {
        "ICICIBANK": "BANKING",
        "SBIN": "BANKING",
        "INFY": "IT",
    }

    selector = StockSelector(
        minimum_score=55.0,
        maximum_candidates=2,
    )

    results = selector.select(
        snapshot=snapshot,
        sector_map=sector_map,
    )

    assert len(results) == 3
    assert results[0].symbol == "ICICIBANK"
    assert results[0].score >= results[1].score
    assert results[1].score >= results[2].score

    selected = [
        result
        for result in results
        if result.selected
    ]

    assert len(selected) == 2
    assert selected[0].symbol == "ICICIBANK"
    assert selected[1].symbol == "SBIN"

    best = selector.best_candidate(
        snapshot=snapshot,
        sector_map=sector_map,
    )

    assert best is not None
    assert best.symbol == "ICICIBANK"

    print("\n===== STOCK SELECTOR RESULTS =====\n")

    for result in results:
        print(
            {
                "symbol": result.symbol,
                "sector": result.sector,
                "score": result.score,
                "confidence": result.confidence,
                "selected": result.selected,
                "relative_rank": (
                    result.relative_strength_rank
                ),
                "sector_rank": result.sector_rank,
                "classification": (
                    result.sector_classification
                ),
            }
        )

        for reason in result.reasons:
            print(f"  - {reason}")

        print()

    print(
        "BEST CANDIDATE:",
        best.symbol,
        best.score,
    )

    print(
        "\n✅ Stock selector test passed."
    )


if __name__ == "__main__":
    main()

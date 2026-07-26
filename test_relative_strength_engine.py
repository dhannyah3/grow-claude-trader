"""
Validation test for the Relative Strength Engine.
"""

from pathlib import Path

import pandas as pd

from market_intelligence.relative_strength_engine import (
    RelativeStrengthEngine,
)


def build_price_data(
    start_price: float,
    daily_change: float,
    periods: int = 80,
) -> pd.DataFrame:
    timestamps = pd.date_range(
        start="2026-01-01",
        periods=periods,
        freq="D",
    )

    closes = [
        start_price + (index * daily_change)
        for index in range(periods)
    ]

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": closes,
        }
    )


def main() -> None:
    engine = RelativeStrengthEngine()

    benchmark_data = build_price_data(
        start_price=20000.0,
        daily_change=10.0,
    )

    stock_data_by_symbol = {
        "STRONG": build_price_data(
            start_price=1000.0,
            daily_change=5.0,
        ),
        "MEDIUM": build_price_data(
            start_price=1000.0,
            daily_change=2.0,
        ),
        "WEAK": build_price_data(
            start_price=1000.0,
            daily_change=0.5,
        ),
    }

    rankings = engine.rank_universe(
        stock_data_by_symbol=stock_data_by_symbol,
        benchmark_data=benchmark_data,
    )

    print(
        "===== RELATIVE STRENGTH TEST ====="
    )

    print(
        rankings[
            [
                "symbol",
                "rank",
                "relative_strength_score",
                "relative_return",
            ]
        ].to_string(
            index=False
        )
    )

    assert len(rankings) == 3

    assert rankings.iloc[0][
        "symbol"
    ] == "STRONG"

    assert rankings.iloc[1][
        "symbol"
    ] == "MEDIUM"

    assert rankings.iloc[2][
        "symbol"
    ] == "WEAK"

    assert rankings.iloc[0][
        "rank"
    ] == 1

    assert rankings.iloc[0][
        "relative_strength_score"
    ] == 100.0

    assert rankings.iloc[-1][
        "relative_strength_score"
    ] == 0.0

    top_result = engine.get_top(
        rankings=rankings,
        count=1,
    )

    bottom_result = engine.get_bottom(
        rankings=rankings,
        count=1,
    )

    assert top_result.iloc[0][
        "symbol"
    ] == "STRONG"

    assert bottom_result.iloc[0][
        "symbol"
    ] == "WEAK"

    output_path = (
        "market_intelligence/results/"
        "test_relative_strength_rankings.csv"
    )

    exported_path = engine.export_rankings(
        rankings=rankings,
        output_path=output_path,
    )

    assert exported_path.exists()

    print(
        f"Exported rankings: {exported_path}"
    )

    print(
        "Relative Strength Engine test passed."
    )

    exported_path.unlink()

    results_directory = Path(
        "market_intelligence/results"
    )

    if (
        results_directory.exists()
        and not any(
            results_directory.iterdir()
        )
    ):
        results_directory.rmdir()


if __name__ == "__main__":
    main()

"""
Basic validation for the Benchmark Engine.
"""

import pandas as pd

from market_intelligence.benchmark import BenchmarkEngine


def build_test_data() -> pd.DataFrame:
    timestamps = pd.date_range(
        start="2026-01-01",
        periods=70,
        freq="D",
    )

    closes = [
        20000 + (index * 10)
        for index in range(70)
    ]

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "close": closes,
        }
    )


def main() -> None:
    engine = BenchmarkEngine()
    dataframe = build_test_data()

    prepared = engine.prepare(
        dataframe
    )

    returns = engine.calculate_returns(
        dataframe=prepared,
        lookbacks=(
            5,
            10,
            20,
            50,
        ),
    )

    print(
        "===== BENCHMARK ENGINE TEST ====="
    )
    print(
        f"Prepared rows: {len(prepared)}"
    )

    for lookback, result in returns.items():
        print(
            f"{lookback}-day return: "
            f"{result.return_percent:.4f}%"
        )

    assert len(prepared) == 70
    assert set(returns.keys()) == {
        5,
        10,
        20,
        50,
    }

    for result in returns.values():
        assert result.return_percent > 0

    print(
        "Benchmark Engine test passed."
    )


if __name__ == "__main__":
    main()

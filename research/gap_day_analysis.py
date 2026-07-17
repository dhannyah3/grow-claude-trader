from research.dataset_builder import DatasetBuilder

import pandas as pd


builder = DatasetBuilder()

symbols = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "LT",
    "AXISBANK",
    "ITC",
    "BHARTIARTL",
]

thresholds = [
    0.2,
    0.3,
    0.5,
    1.0,
]

results = []

print()
print("=" * 90)
print("GAP DAY ANALYSIS")
print("=" * 90)

for symbol in symbols:
    print(f"Loading {symbol}...")

    df = builder.build_dataset(
        symbol=symbol,
        interval_name="5m",
        year=2025,
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    df["trade_date"] = (
        df["timestamp"]
        .dt.date
    )

    df = (
        df.sort_values("timestamp")
        .reset_index(drop=True)
    )

    total_days = 0

    gap_counts = {
        threshold: 0
        for threshold in thresholds
    }

    daily_groups = list(
        df.groupby(
            "trade_date",
            sort=True,
        )
    )

    for day_index in range(
        1,
        len(daily_groups),
    ):
        _, day = daily_groups[day_index]

        _, previous_day = daily_groups[
            day_index - 1
        ]

        day = (
            day.sort_values("timestamp")
            .reset_index(drop=True)
        )

        previous_day = (
            previous_day
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        if day.empty or previous_day.empty:
            continue

        previous_close = float(
            previous_day.iloc[-1]["close"]
        )

        day_open = float(
            day.iloc[0]["open"]
        )

        if previous_close <= 0:
            continue

        total_days += 1

        gap_percent = (
            (day_open - previous_close)
            / previous_close
            * 100.0
        )

        for threshold in thresholds:
            if gap_percent >= threshold:
                gap_counts[threshold] += 1

    row = {
        "symbol": symbol,
        "trading_days": total_days,
    }

    for threshold in thresholds:
        row[f"gap>={threshold}%"] = (
            gap_counts[threshold]
        )

    results.append(row)

results_df = pd.DataFrame(results)

print()
print(
    results_df.to_string(
        index=False,
    )
)

print()
print("=" * 90)
print("TOTALS")
print("=" * 90)

print(
    results_df.sum(
        numeric_only=True,
    )
)
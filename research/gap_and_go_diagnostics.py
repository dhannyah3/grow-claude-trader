from research.dataset_builder import DatasetBuilder
from research.gap_and_go_strategy import GapAndGoStrategy

import pandas as pd

def diagnose_symbol(
    symbol: str,
    strategy: GapAndGoStrategy,
    builder: DatasetBuilder,
) -> dict:
    """
    Count how many candles survive each Gap and Go filter.
    """

    data = builder.build_dataset(
        symbol=symbol,
        interval_name="5m",
        year=2025,
    )

    data = strategy.prepare_dataframe(data)

    counts = {
        "symbol": symbol,
        "trading_days": 0,
        "candles_checked": 0,
        "gap_condition": 0,
        "opening_range_complete": 0,
        "opening_range_breakout": 0,
        "ema_filter": 0,
        "vwap_filter": 0,
        "rsi_filter": 0,
        "volume_filter": 0,
        "atr_filter": 0,
        "final_entries": 0,
    }

    for trade_date, day_data in data.groupby(
        "trade_date",
        sort=True,
    ):
        day_data = (
            day_data.sort_values("timestamp")
            .reset_index(drop=True)
        )

        if day_data.empty:
            continue

        counts["trading_days"] += 1

        previous_close = day_data.iloc[0].get(
            "previous_close"
        )

        if (
            pd.isna(previous_close)
            or float(previous_close) <= 0
        ):
            continue

        day_open = float(day_data.iloc[0]["open"])

        gap_percent = (
            (day_open - float(previous_close))
            / float(previous_close)
            * 100.0
        )

        market_open = day_data.iloc[0]["timestamp"]

        opening_range_end = (
            market_open
            + pd.Timedelta(
                minutes=strategy.opening_range_minutes
            )
        )

        opening_data = day_data[
            day_data["timestamp"]
            < opening_range_end
        ]

        if opening_data.empty:
            continue

        opening_high = float(
            opening_data["high"].max()
        )

        for _, row in day_data.iterrows():
            current_time = row["timestamp"].time()

            if not (
                strategy.entry_start_time
                <= current_time
                <= strategy.entry_cutoff_time
            ):
                continue

            counts["candles_checked"] += 1

            if (
                gap_percent
                < strategy.minimum_gap_percent
            ):
                continue

            counts["gap_condition"] += 1

            if row["timestamp"] < opening_range_end:
                continue

            counts["opening_range_complete"] += 1

            close = float(row["close"])

            if close <= opening_high:
                continue

            counts["opening_range_breakout"] += 1

            if (
                float(row["ema_20"])
                <= float(row["ema_50"])
            ):
                continue

            counts["ema_filter"] += 1

            if close <= float(row["vwap"]):
                continue

            counts["vwap_filter"] += 1

            rsi = float(row["rsi"])

            if not (
                strategy.minimum_rsi
                <= rsi
                <= strategy.maximum_rsi
            ):
                continue

            counts["rsi_filter"] += 1

            if (
                float(row["volume_ratio"])
                < strategy.minimum_volume_ratio
            ):
                continue

            counts["volume_filter"] += 1

            if float(row["atr"]) <= 0:
                continue

            counts["atr_filter"] += 1
            counts["final_entries"] += 1

    return counts
def main() -> None:
    builder = DatasetBuilder()

    strategy = GapAndGoStrategy(
        minimum_gap_percent=0.5,
        opening_range_minutes=15,
        minimum_rsi=50.0,
        maximum_rsi=80.0,
        minimum_volume_ratio=1.2,
        stop_atr_multiplier=1.0,
        target_atr_multiplier=2.5,
        entry_start_time="09:30",
        entry_cutoff_time="11:30",
        force_exit_time="15:20",
    )

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

    results = []

    print()
    print("=" * 120)
    print("GAP AND GO DIAGNOSTICS")
    print("=" * 120)

    for symbol in symbols:
        print(f"Analyzing {symbol}...")
        results.append(
            diagnose_symbol(
                symbol=symbol,
                strategy=strategy,
                builder=builder,
            )
        )

    results_df = pd.DataFrame(results)

    print()
    print(results_df.to_string(index=False))

    print()
    print("=" * 120)
    print("TOTALS")
    print("=" * 120)

    numeric_columns = [
        c
        for c in results_df.columns
        if c != "symbol"
    ]

    totals = results_df[numeric_columns].sum()

    print(totals)


if __name__ == "__main__":
    main()

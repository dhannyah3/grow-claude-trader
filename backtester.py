from typing import Any, Dict, Optional

import pandas as pd

from indicators import calculate_indicators
from market_data import MarketData


def backtest_orb(
    candles_response: Dict[str, Any],
    risk_reward_ratio: float = 2.0,
) -> Optional[Dict[str, Any]]:
    dataframe = calculate_indicators(candles_response)

    if dataframe.empty:
        print("No candle data available.")
        return None

    dataframe = dataframe.sort_values("timestamp").reset_index(drop=True)

    opening_range = dataframe[
        (dataframe["timestamp"].dt.time >= pd.Timestamp("09:15").time())
        & (dataframe["timestamp"].dt.time < pd.Timestamp("09:30").time())
    ]

    trading_period = dataframe[
        dataframe["timestamp"].dt.time >= pd.Timestamp("09:30").time()
    ]

    if opening_range.empty or trading_period.empty:
        print("Not enough data for ORB backtest.")
        return None

    opening_high = float(opening_range["high"].max())
    opening_low = float(opening_range["low"].min())

    entry_price = None
    entry_time = None
    stop_loss = None
    target = None
    exit_price = None
    exit_time = None
    result = "NO_TRADE"

    for _, candle in trading_period.iterrows():
        required_values = [
            candle.get("ema_20"),
            candle.get("ema_50"),
            candle.get("vwap"),
            candle.get("rsi"),
        ]

        if any(pd.isna(value) for value in required_values):
            continue

        long_breakout = (
            candle["close"] > opening_high
            and candle["ema_20"] > candle["ema_50"]
            and candle["close"] > candle["vwap"]
            and 50 <= candle["rsi"] <= 70
        )

        if long_breakout:
            entry_price = float(candle["close"])
            entry_time = candle["timestamp"]

            stop_loss = opening_low
            risk_per_share = entry_price - stop_loss

            if risk_per_share <= 0:
                continue

            target = entry_price + (
                risk_per_share * risk_reward_ratio
            )

            result = "OPEN"
            break

    if entry_price is None:
        return {
            "result": "NO_TRADE",
            "opening_high": opening_high,
            "opening_low": opening_low,
        }

    candles_after_entry = trading_period[
        trading_period["timestamp"] > entry_time
    ]

    for _, candle in candles_after_entry.iterrows():
        if candle["low"] <= stop_loss:
            exit_price = stop_loss
            exit_time = candle["timestamp"]
            result = "STOP_LOSS"
            break

        if candle["high"] >= target:
            exit_price = target
            exit_time = candle["timestamp"]
            result = "TARGET"
            break

    if exit_price is None:
        final_candle = candles_after_entry.iloc[-1]

        exit_price = float(final_candle["close"])
        exit_time = final_candle["timestamp"]
        result = "DAY_END_EXIT"

    pnl_per_share = exit_price - entry_price

    return {
        "result": result,
        "opening_high": round(opening_high, 2),
        "opening_low": round(opening_low, 2),
        "entry_time": str(entry_time),
        "entry_price": round(entry_price, 2),
        "stop_loss": round(stop_loss, 2),
        "target": round(target, 2),
        "exit_time": str(exit_time),
        "exit_price": round(exit_price, 2),
        "pnl_per_share": round(pnl_per_share, 2),
    }


if __name__ == "__main__":
    market = MarketData()

    candles = market.get_historical_data(
        groww_symbol="NSE-RELIANCE",
        start_time="2026-07-10 09:15:00",
        end_time="2026-07-10 15:30:00",
        interval=market.groww.CANDLE_INTERVAL_MIN_5,
    )

    if not candles:
        print("Could not fetch candle data.")
    else:
        result = backtest_orb(candles)

        print("\n===== ORB BACKTEST RESULT =====\n")

        if result:
            for key, value in result.items():
                print(f"{key}: {value}")
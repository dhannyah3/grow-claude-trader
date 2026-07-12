from typing import Any, Dict, Optional

import pandas as pd

from data.market_data import MarketData
from strategies.indicators import calculate_indicators
from core.trading_costs import calculate_intraday_costs


def backtest_orb(
    candles_response: Dict[str, Any],
    risk_reward_ratio: float = 2.0,
    starting_capital: float = 100000.0,
    risk_per_trade_percent: float = 0.5,
    slippage_bps: float = 5.0,
    transaction_cost_rate: float = 0.001,
) -> Optional[Dict[str, Any]]:
    """
    Backtest one ORB trade for one trading day.

    Notes:
    - slippage_bps applies adverse slippage to entry and exit.
    - transaction_cost_rate is a configurable estimate applied
      to total turnover. It is not a broker-exact charges model.
    """

    dataframe = calculate_indicators(
        candles_response
    )

    if dataframe.empty:
        print("No candle data available.")
        return None

    dataframe = (
        dataframe
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    opening_range = dataframe[
        (
            dataframe["timestamp"].dt.time
            >= pd.Timestamp("09:15").time()
        )
        & (
            dataframe["timestamp"].dt.time
            < pd.Timestamp("09:30").time()
        )
    ]

    trading_period = dataframe[
        dataframe["timestamp"].dt.time
        >= pd.Timestamp("09:30").time()
    ]

    if opening_range.empty or trading_period.empty:
        print("Not enough data for ORB backtest.")
        return None

    opening_high = float(
        opening_range["high"].max()
    )

    opening_low = float(
        opening_range["low"].min()
    )

    entry_price = None
    entry_time = None
    stop_loss = None
    target = None
    exit_price = None
    exit_time = None
    quantity = 0
    result = "NO_TRADE"

    slippage_rate = slippage_bps / 10000

    for _, candle in trading_period.iterrows():
        required_values = [
            candle.get("ema_20"),
            candle.get("ema_50"),
            candle.get("vwap"),
            candle.get("rsi"),
        ]

        if any(
            pd.isna(value)
            for value in required_values
        ):
            continue

        long_breakout = (
            candle["close"] > opening_high
            and candle["ema_20"]
            > candle["ema_50"]
            and candle["close"]
            > candle["vwap"]
            and 50
            <= candle["rsi"]
            <= 70
        )

        if not long_breakout:
            continue

        raw_entry_price = float(
            candle["close"]
        )

        entry_price = raw_entry_price * (
            1 + slippage_rate
        )

        entry_time = candle["timestamp"]
        stop_loss = opening_low

        risk_per_share = (
            entry_price - stop_loss
        )

        if risk_per_share <= 0:
            entry_price = None
            continue

        risk_amount = starting_capital * (
            risk_per_trade_percent / 100
        )

        risk_based_quantity = int(
            risk_amount / risk_per_share
        )

        capital_based_quantity = int(
            starting_capital / entry_price
        )

        quantity = min(
            risk_based_quantity,
            capital_based_quantity,
        )

        if quantity <= 0:
            return {
                "result": "INSUFFICIENT_CAPITAL",
                "opening_high": round(
                    opening_high,
                    2,
                ),
                "opening_low": round(
                    opening_low,
                    2,
                ),
                "starting_capital": round(
                    starting_capital,
                    2,
                ),
                "quantity": 0,
                "gross_pnl": 0.0,
                "transaction_costs": 0.0,
                "net_pnl": 0.0,
                "pnl_per_share": 0.0,
            }

        target = entry_price + (
            risk_per_share
            * risk_reward_ratio
        )

        result = "OPEN"
        break

    if entry_price is None:
        return {
            "result": "NO_TRADE",
            "opening_high": round(
                opening_high,
                2,
            ),
            "opening_low": round(
                opening_low,
                2,
            ),
            "starting_capital": round(
                starting_capital,
                2,
            ),
            "quantity": 0,
            "gross_pnl": 0.0,
            "transaction_costs": 0.0,
            "net_pnl": 0.0,
            "pnl_per_share": 0.0,
        }

    candles_after_entry = trading_period[
        trading_period["timestamp"]
        > entry_time
    ]

    raw_exit_price = None

    for _, candle in (
        candles_after_entry.iterrows()
    ):
        if candle["low"] <= stop_loss:
            raw_exit_price = stop_loss
            exit_time = candle["timestamp"]
            result = "STOP_LOSS"
            break

        if candle["high"] >= target:
            raw_exit_price = target
            exit_time = candle["timestamp"]
            result = "TARGET"
            break

    if raw_exit_price is None:
        if candles_after_entry.empty:
            raw_exit_price = entry_price
            exit_time = entry_time
            result = "ENTRY_AT_DAY_END"
        else:
            final_candle = (
                candles_after_entry.iloc[-1]
            )

            raw_exit_price = float(
                final_candle["close"]
            )

            exit_time = final_candle[
                "timestamp"
            ]

            result = "DAY_END_EXIT"

    exit_price = raw_exit_price * (
        1 - slippage_rate
    )

    gross_pnl = (
        exit_price - entry_price
    ) * quantity

    buy_turnover = (
        entry_price * quantity
    )

    sell_turnover = (
        exit_price * quantity
    )

    total_turnover = (
        buy_turnover + sell_turnover
    )

    cost_breakdown = calculate_intraday_costs(
        buy_price=entry_price,
        sell_price=exit_price,
        quantity=quantity,
    )

    transaction_costs = float(
        cost_breakdown["total_costs"]
    )

    net_pnl = (
        gross_pnl - transaction_costs
    )

    pnl_per_share = (
        net_pnl / quantity
        if quantity > 0
        else 0.0
    )

    ending_capital = (
        starting_capital + net_pnl
    )

    return {
        "result": result,
        "opening_high": round(
            opening_high,
            2,
        ),
        "opening_low": round(
            opening_low,
            2,
        ),
        "entry_time": str(entry_time),
        "entry_price": round(
            entry_price,
            2,
        ),
        "stop_loss": round(
            stop_loss,
            2,
        ),
        "target": round(
            target,
            2,
        ),
        "exit_time": str(exit_time),
        "exit_price": round(
            exit_price,
            2,
        ),
        "quantity": quantity,
        "gross_pnl": round(
            gross_pnl,
            2,
        ),
        "transaction_costs": round(
            transaction_costs,
            2,
        ),
        "brokerage": cost_breakdown["brokerage"],
    "stt": cost_breakdown["stt"],
    "exchange_charges": (
        cost_breakdown["exchange_charges"]
    ),
    "sebi_charges": (
        cost_breakdown["sebi_charges"]
    ),
    "stamp_duty": (
        cost_breakdown["stamp_duty"]
    ),
    "gst": cost_breakdown["gst"],

    "net_pnl": round(
        net_pnl,
        2,
    ),
        "net_pnl": round(
            net_pnl,
            2,
        ),
        "pnl_per_share": round(
            pnl_per_share,
            2,
        ),
        "starting_capital": round(
            starting_capital,
            2,
        ),
        "ending_capital": round(
            ending_capital,
            2,
        ),
        "slippage_bps": slippage_bps,
        "transaction_cost_rate": (
            transaction_cost_rate
        ),
    }


if __name__ == "__main__":
    market = MarketData()

    candles = market.get_historical_data(
        groww_symbol="NSE-RELIANCE",
        start_time="2026-07-10 09:15:00",
        end_time="2026-07-10 15:30:00",
        interval=(
            market.groww
            .CANDLE_INTERVAL_MIN_5
        ),
    )

    if not candles:
        print("Could not fetch candle data.")
    else:
        result = backtest_orb(
            candles_response=candles,
            starting_capital=100000.0,
            risk_per_trade_percent=0.5,
            slippage_bps=5.0,
            transaction_cost_rate=0.001,
        )

        print(
            "\n===== ORB BACKTEST V2 =====\n"
        )

        if result:
            for key, value in result.items():
                print(f"{key}: {value}")
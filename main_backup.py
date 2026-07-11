import time
from typing import Any, Dict, List, Tuple

import pandas as pd

from dashboard import Dashboard
from indicators import calculate_indicators
from market_clock import can_open_new_trade, market_status
from market_data import MarketData
from paper_trader import PaperTrader
from risk_manager import RiskManager
from watchlist import WATCHLIST


MINIMUM_SCORE = 70
REQUEST_DELAY_SECONDS = 1.0

# Historical test session.
# This version creates paper trades only.
TEST_START_TIME = "2026-07-10 09:15:00"
TEST_END_TIME = "2026-07-10 15:30:00"


def check_signal(
    dataframe: pd.DataFrame,
) -> Tuple[str, int, pd.Series]:
    latest = dataframe.iloc[-1]
    score = 0

    if latest["ema_20"] > latest["ema_50"]:
        score += 25

    if latest["close"] > latest["vwap"]:
        score += 20

    if latest["macd"] > latest["macd_signal"]:
        score += 25

    if 55 <= latest["rsi"] <= 70:
        score += 20

    if latest["atr"] > 1:
        score += 10

    action = "BUY" if score >= MINIMUM_SCORE else "WAIT"

    return action, score, latest


def scan_market(
    market: MarketData,
) -> List[Dict[str, Any]]:
    scan_results: List[Dict[str, Any]] = []

    for symbol in WATCHLIST:
        print(f"Scanning {symbol}...")

        candles = market.get_historical_data(
            groww_symbol=f"NSE-{symbol}",
            start_time=TEST_START_TIME,
            end_time=TEST_END_TIME,
            interval=market.groww.CANDLE_INTERVAL_MIN_5,
        )

        if not candles or not candles.get("candles"):
            print(f"{symbol}: no candle data.")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        dataframe = calculate_indicators(candles)

        if dataframe.empty:
            print(f"{symbol}: indicator calculation failed.")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        action, score, latest = check_signal(dataframe)

        result = {
            "symbol": symbol,
            "action": action,
            "score": score,
            "price": float(latest["close"]),
            "atr": float(latest["atr"]),
            "rsi": float(latest["rsi"]),
        }

        scan_results.append(result)

        print(
            f"{symbol} | "
            f"Price: ₹{result['price']:.2f} | "
            f"Score: {score}/100 | "
            f"Signal: {action}"
        )

        time.sleep(REQUEST_DELAY_SECONDS)

    return scan_results


def open_paper_trades(
    scan_results: List[Dict[str, Any]],
    trader: PaperTrader,
    risk_manager: RiskManager,
) -> None:
    for result in scan_results:
        if result["action"] != "BUY":
            continue

        symbol = result["symbol"]

        if trader.get_open_position(symbol) is not None:
            print(f"{symbol}: paper position already open.")
            continue

        if not risk_manager.can_open_trade(
            daily_realized_pnl=trader.total_realized_pnl(),
            current_open_positions=len(trader.open_positions),
        ):
            continue

        entry_price = result["price"]
        atr = result["atr"]

        stop_loss = entry_price - atr
        target_price = entry_price + (2 * atr)

        plan = risk_manager.trade_plan(
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
        )

        quantity = int(plan["quantity"])

        if quantity <= 0:
            print(f"{symbol}: quantity calculated as zero.")
            continue

        opened = trader.open_trade(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target_price,
        )

        if opened:
            print(
                f"{symbol} risk plan | "
                f"Qty: {quantity} | "
                f"Risk: ₹{plan['risk_amount']:.2f} | "
                f"Position: ₹{plan['position_value']:.2f} | "
                f"R:R: {plan['risk_reward_ratio']}"
            )


def build_watchlist_display(
    scan_results: List[Dict[str, Any]],
) -> List[str]:
    display_rows: List[str] = []

    for result in scan_results:
        display_rows.append(
            f"{result['symbol']:12} "
            f"₹{result['price']:.2f} | "
            f"Score {result['score']:3}/100 | "
            f"{result['action']}"
        )

    return display_rows


def main() -> None:
    current_status = market_status()

    print("\n==============================")
    print("GROWW CLAUDE PAPER TRADER")
    print("==============================")
    print(f"Market status: {current_status}")

    if not can_open_new_trade():
        print(
            "New paper trades are disabled because "
            "the market is closed."
        )
        return

    market = MarketData()

    trader = PaperTrader(
        starting_balance=100000.0,
        log_file="logs/paper_trades.csv",
    )

    risk_manager = RiskManager(
        account_balance=trader.starting_balance,
        risk_per_trade_percent=0.5,
        max_daily_loss_percent=2.0,
        max_position_percent=20.0,
        max_open_positions=2,
    )

    print("\nStarting market scan...\n")

    scan_results = scan_market(market)

    open_paper_trades(
        scan_results=scan_results,
        trader=trader,
        risk_manager=risk_manager,
    )

    watchlist_display = build_watchlist_display(scan_results)

    Dashboard.show(
        balance=trader.cash_balance,
        pnl=trader.total_realized_pnl(),
        positions=trader.open_positions,
        watchlist=watchlist_display,
    )


if __name__ == "__main__":
    main()
import time
from datetime import date, timedelta
from typing import Any, Dict, List

from backtester import backtest_orb
from market_data import MarketData


REQUEST_DELAY_SECONDS = 1.5
MAX_RETRIES = 3


def trading_days(
    start_date: date,
    end_date: date,
) -> List[date]:
    days: List[date] = []
    current = start_date

    while current <= end_date:
        if current.weekday() < 5:
            days.append(current)

        current += timedelta(days=1)

    return days


def fetch_candles_with_retry(
    market: MarketData,
    symbol: str,
    day_text: str,
) -> Dict[str, Any]:
    for attempt in range(1, MAX_RETRIES + 1):
        candles = market.get_historical_data(
            groww_symbol=f"NSE-{symbol}",
            start_time=f"{day_text} 09:15:00",
            end_time=f"{day_text} 15:30:00",
            interval=market.groww.CANDLE_INTERVAL_MIN_5,
        )

        if candles and candles.get("candles"):
            return candles

        if attempt < MAX_RETRIES:
            wait_time = REQUEST_DELAY_SECONDS * attempt
            print(
                f"Retrying {day_text} in "
                f"{wait_time:.1f} seconds..."
            )
            time.sleep(wait_time)

    return {}


def run_multi_day_backtest(
    symbol: str,
    start_date: date,
    end_date: date,
) -> List[Dict[str, Any]]:
    market = MarketData()
    results: List[Dict[str, Any]] = []

    for trading_day in trading_days(start_date, end_date):
        day_text = trading_day.strftime("%Y-%m-%d")

        print(f"Testing {symbol} on {day_text}...")

        candles = fetch_candles_with_retry(
            market=market,
            symbol=symbol,
            day_text=day_text,
        )

        time.sleep(REQUEST_DELAY_SECONDS)

        if not candles:
            print("No data after retries.")
            continue

        result = backtest_orb(candles)

        if result is not None:
            result["date"] = day_text
            results.append(result)

    return results


def calculate_max_drawdown(
    trades: List[Dict[str, Any]],
) -> float:
    running_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0

    for trade in trades:
        running_pnl += float(
            trade.get("pnl_per_share", 0)
        )

        if running_pnl > peak_pnl:
            peak_pnl = running_pnl

        drawdown = peak_pnl - running_pnl

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return max_drawdown


def print_summary(
    results: List[Dict[str, Any]],
) -> None:
    trades = [
        result
        for result in results
        if result.get("result") != "NO_TRADE"
    ]

    wins = [
        trade
        for trade in trades
        if trade.get("pnl_per_share", 0) > 0
    ]

    losses = [
        trade
        for trade in trades
        if trade.get("pnl_per_share", 0) < 0
    ]

    breakeven_trades = [
        trade
        for trade in trades
        if trade.get("pnl_per_share", 0) == 0
    ]

    no_trade_days = [
        result
        for result in results
        if result.get("result") == "NO_TRADE"
    ]

    total_pnl = sum(
        float(trade.get("pnl_per_share", 0))
        for trade in trades
    )

    win_rate = (
        len(wins) / len(trades) * 100
        if trades
        else 0
    )

    average_pnl = (
        total_pnl / len(trades)
        if trades
        else 0
    )

    average_win = (
        sum(
            float(trade.get("pnl_per_share", 0))
            for trade in wins
        ) / len(wins)
        if wins
        else 0
    )

    average_loss = (
        sum(
            float(trade.get("pnl_per_share", 0))
            for trade in losses
        ) / len(losses)
        if losses
        else 0
    )

    gross_profit = sum(
        float(trade.get("pnl_per_share", 0))
        for trade in wins
    )

    gross_loss = abs(
        sum(
            float(trade.get("pnl_per_share", 0))
            for trade in losses
        )
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else 0
    )

    max_drawdown = calculate_max_drawdown(trades)

    print("\n===== MULTI-DAY BACKTEST SUMMARY =====\n")

    print(f"Trading days tested : {len(results)}")
    print(f"Total trades        : {len(trades)}")
    print(f"No-trade days       : {len(no_trade_days)}")
    print(f"Winning trades      : {len(wins)}")
    print(f"Losing trades       : {len(losses)}")
    print(f"Breakeven trades    : {len(breakeven_trades)}")
    print(f"Win rate            : {win_rate:.2f}%")
    print(f"Total P&L/share     : ₹{total_pnl:.2f}")
    print(f"Average P&L/share   : ₹{average_pnl:.2f}")
    print(f"Average win/share   : ₹{average_win:.2f}")
    print(f"Average loss/share  : ₹{average_loss:.2f}")
    print(f"Profit factor       : {profit_factor:.2f}")
    print(f"Max drawdown/share  : ₹{max_drawdown:.2f}")

    print("\n===== INDIVIDUAL RESULTS =====\n")

    for result in results:
        print(
            f"{result.get('date')} | "
            f"{result.get('result')} | "
            f"Entry: {result.get('entry_price', '-')} | "
            f"Exit: {result.get('exit_price', '-')} | "
            f"P&L/share: ₹{result.get('pnl_per_share', 0)}"
        )


if __name__ == "__main__":
    results = run_multi_day_backtest(
        symbol="RELIANCE",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 7, 10),
    )

    print_summary(results)
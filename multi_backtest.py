import time
from datetime import date, timedelta
from typing import Any, Dict, List

from backtester import backtest_orb
from data.market_data import MarketData


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
    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        candles = market.get_historical_data(
            groww_symbol=f"NSE-{symbol}",
            start_time=(
                f"{day_text} 09:15:00"
            ),
            end_time=(
                f"{day_text} 15:30:00"
            ),
            interval=(
                market.groww
                .CANDLE_INTERVAL_MIN_5
            ),
        )

        if candles and candles.get("candles"):
            return candles

        if attempt < MAX_RETRIES:
            wait_time = (
                REQUEST_DELAY_SECONDS * attempt
            )

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
    starting_capital: float = 100000.0,
) -> List[Dict[str, Any]]:
    market = MarketData()
    results: List[Dict[str, Any]] = []

    current_capital = starting_capital

    for trading_day in trading_days(
        start_date,
        end_date,
    ):
        day_text = trading_day.strftime(
            "%Y-%m-%d"
        )

        print(
            f"Testing {symbol} on {day_text} | "
            f"Capital: ₹{current_capital:.2f}"
        )

        candles = fetch_candles_with_retry(
            market=market,
            symbol=symbol,
            day_text=day_text,
        )

        time.sleep(REQUEST_DELAY_SECONDS)

        if not candles:
            print("No data after retries.")
            continue

        result = backtest_orb(
            candles_response=candles,
            starting_capital=current_capital,
            risk_per_trade_percent=0.5,
            slippage_bps=5.0,
            transaction_cost_rate=0.001,
        )

        if result is None:
            continue

        result["date"] = day_text

        result["capital_before_trade"] = round(
            current_capital,
            2,
        )

        if result.get("result") not in {
            "NO_TRADE",
            "INSUFFICIENT_CAPITAL",
        }:
            current_capital = float(
                result.get(
                    "ending_capital",
                    current_capital,
                )
            )

        result["capital_after_trade"] = round(
            current_capital,
            2,
        )

        results.append(result)

    return results


def calculate_max_drawdown(
    trades: List[Dict[str, Any]],
    starting_capital: float,
) -> float:
    equity = starting_capital
    peak_equity = starting_capital
    max_drawdown = 0.0

    for trade in trades:
        equity += float(
            trade.get("net_pnl", 0.0)
        )

        if equity > peak_equity:
            peak_equity = equity

        drawdown = peak_equity - equity

        if drawdown > max_drawdown:
            max_drawdown = drawdown

    return max_drawdown


def print_summary(
    results: List[Dict[str, Any]],
    initial_capital: float = 100000.0,
) -> None:
    trades = [
        result
        for result in results
        if result.get("result")
        not in {
            "NO_TRADE",
            "INSUFFICIENT_CAPITAL",
        }
    ]

    wins = [
        trade
        for trade in trades
        if float(
            trade.get("net_pnl", 0)
        ) > 0
    ]

    losses = [
        trade
        for trade in trades
        if float(
            trade.get("net_pnl", 0)
        ) < 0
    ]

    breakeven_trades = [
        trade
        for trade in trades
        if float(
            trade.get("net_pnl", 0)
        ) == 0
    ]

    no_trade_days = [
        result
        for result in results
        if result.get("result") == "NO_TRADE"
    ]

    insufficient_capital_days = [
        result
        for result in results
        if result.get("result")
        == "INSUFFICIENT_CAPITAL"
    ]

    total_net_pnl = sum(
        float(
            trade.get("net_pnl", 0)
        )
        for trade in trades
    )

    total_gross_pnl = sum(
        float(
            trade.get("gross_pnl", 0)
        )
        for trade in trades
    )

    total_costs = sum(
        float(
            trade.get(
                "transaction_costs",
                0,
            )
        )
        for trade in trades
    )

    win_rate = (
        len(wins) / len(trades) * 100
        if trades
        else 0.0
    )

    average_pnl = (
        total_net_pnl / len(trades)
        if trades
        else 0.0
    )

    average_win = (
        sum(
            float(
                trade.get("net_pnl", 0)
            )
            for trade in wins
        ) / len(wins)
        if wins
        else 0.0
    )

    average_loss = (
        sum(
            float(
                trade.get("net_pnl", 0)
            )
            for trade in losses
        ) / len(losses)
        if losses
        else 0.0
    )

    gross_profit = sum(
        float(
            trade.get("net_pnl", 0)
        )
        for trade in wins
    )

    gross_loss = abs(
        sum(
            float(
                trade.get("net_pnl", 0)
            )
            for trade in losses
        )
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else 0.0
    )

    ending_capital = (
        initial_capital + total_net_pnl
    )

    return_percent = (
        total_net_pnl
        / initial_capital
        * 100
        if initial_capital > 0
        else 0.0
    )

    max_drawdown = calculate_max_drawdown(
        trades=trades,
        starting_capital=initial_capital,
    )

    max_drawdown_percent = (
        max_drawdown
        / initial_capital
        * 100
        if initial_capital > 0
        else 0.0
    )

    print(
        "\n===== MULTI-DAY "
        "BACKTEST V2 SUMMARY =====\n"
    )

    print(
        f"Trading days tested : "
        f"{len(results)}"
    )

    print(
        f"Total trades        : "
        f"{len(trades)}"
    )

    print(
        f"No-trade days       : "
        f"{len(no_trade_days)}"
    )

    print(
        f"Insufficient capital: "
        f"{len(insufficient_capital_days)}"
    )

    print(
        f"Winning trades      : "
        f"{len(wins)}"
    )

    print(
        f"Losing trades       : "
        f"{len(losses)}"
    )

    print(
        f"Breakeven trades    : "
        f"{len(breakeven_trades)}"
    )

    print(
        f"Win rate            : "
        f"{win_rate:.2f}%"
    )

    print(
        f"Starting capital    : "
        f"₹{initial_capital:.2f}"
    )

    print(
        f"Ending capital      : "
        f"₹{ending_capital:.2f}"
    )

    print(
        f"Gross P&L           : "
        f"₹{total_gross_pnl:.2f}"
    )

    print(
        f"Transaction costs   : "
        f"₹{total_costs:.2f}"
    )

    print(
        f"Net P&L             : "
        f"₹{total_net_pnl:.2f}"
    )

    print(
        f"Return              : "
        f"{return_percent:.2f}%"
    )

    print(
        f"Average net P&L     : "
        f"₹{average_pnl:.2f}"
    )

    print(
        f"Average winner      : "
        f"₹{average_win:.2f}"
    )

    print(
        f"Average loser       : "
        f"₹{average_loss:.2f}"
    )

    print(
        f"Profit factor       : "
        f"{profit_factor:.2f}"
    )

    print(
        f"Maximum drawdown    : "
        f"₹{max_drawdown:.2f}"
    )

    print(
        f"Max drawdown percent: "
        f"{max_drawdown_percent:.2f}%"
    )

    print(
        "\n===== INDIVIDUAL RESULTS =====\n"
    )

    for result in results:
        print(
            f"{result.get('date')} | "
            f"{result.get('result')} | "
            f"Qty: "
            f"{result.get('quantity', 0)} | "
            f"Gross: "
            f"₹{result.get('gross_pnl', 0)} | "
            f"Costs: "
            f"₹{result.get('transaction_costs', 0)} | "
            f"Net: "
            f"₹{result.get('net_pnl', 0)} | "
            f"Capital: "
            f"₹{result.get('capital_after_trade', '-')}"
        )


if __name__ == "__main__":
    INITIAL_CAPITAL = 100000.0

    results = run_multi_day_backtest(
        symbol="RELIANCE",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 7, 10),
        starting_capital=INITIAL_CAPITAL,
    )

    print_summary(
        results=results,
        initial_capital=INITIAL_CAPITAL,
    )
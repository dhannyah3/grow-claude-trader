import time
import json
from pathlib import Path
from datetime import time as clock_time
from typing import Any, Dict, List, Tuple

import pandas as pd

from strategies.claude_analyzer import ClaudeAnalyzer
from utils.dashboard import Dashboard
from strategies.indicators import calculate_indicators
from core.market_clock import (
    can_open_new_trade,
    market_status,
    now_in_india,
)
from data.market_data import MarketData
from core.paper_trader import PaperTrader
from core.risk_manager import RiskManager
from watchlist import WATCHLIST


MINIMUM_SCORE = 70
MINIMUM_CLAUDE_CONFIDENCE = 70

SCAN_INTERVAL_SECONDS = 60
REQUEST_DELAY_SECONDS = 1.5
MONITOR_INTERVAL_SECONDS = 10

FORCE_EXIT_TIME = clock_time(15, 20)
MINIMUM_CANDLES = 50

CLAUDE_REVIEWS_FILE = Path("logs/claude_reviews.json")

def save_claude_review(
    symbol: str,
    review: dict,
) -> None:

    if CLAUDE_REVIEWS_FILE.exists():

        try:
            reviews = json.loads(
                CLAUDE_REVIEWS_FILE.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            reviews = {}

    else:
        reviews = {}

    reviews[symbol] = review

    CLAUDE_REVIEWS_FILE.write_text(
        json.dumps(
            reviews,
            indent=4,
        ),
        encoding="utf-8",
    )


def get_today_time_range() -> Tuple[str, str]:
    current_time = now_in_india()
    day_text = current_time.strftime("%Y-%m-%d")

    start_time = f"{day_text} 09:15:00"
    end_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

    return start_time, end_time


def check_signal(
    dataframe: pd.DataFrame,
) -> Tuple[str, int, pd.Series, float]:
    latest = dataframe.iloc[-1]

    opening_candles = dataframe[
        dataframe["timestamp"].dt.time < clock_time(9, 30)
    ]

    if opening_candles.empty:
        return "WAIT", 0, latest, 0.0

    opening_high = float(opening_candles["high"].max())

    recent_volume_average = (
        dataframe["volume"]
        .tail(20)
        .mean()
    )

    score = 0

    if latest["close"] > opening_high:
        score += 30

    if latest["ema_20"] > latest["ema_50"]:
        score += 20

    if latest["close"] > latest["vwap"]:
        score += 15

    if latest["macd"] > latest["macd_signal"]:
        score += 15

    if 55 <= latest["rsi"] <= 70:
        score += 10

    if (
        recent_volume_average > 0
        and latest["volume"]
        >= recent_volume_average * 1.5
    ):
        score += 10

    action = (
        "BUY"
        if score >= MINIMUM_SCORE
        else "WAIT"
    )

    return action, score, latest, opening_high


def scan_market(
    market: MarketData,
) -> List[Dict[str, Any]]:
    start_time, end_time = get_today_time_range()
    scan_results: List[Dict[str, Any]] = []

    for symbol in WATCHLIST:
        print(f"Scanning {symbol}...")

        candles = market.get_historical_data(
            groww_symbol=f"NSE-{symbol}",
            start_time=start_time,
            end_time=end_time,
            interval=market.groww.CANDLE_INTERVAL_MIN_1,
        )

        if not candles or not candles.get("candles"):
            print(f"{symbol}: no candle data.")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        dataframe = calculate_indicators(candles)

        if len(dataframe) < MINIMUM_CANDLES:
            print(f"{symbol}: not enough candles.")

            scan_results.append(
                {
                    "symbol": symbol,
                    "action": "WAIT",
                    "score": 0,
                    "price": None,
                    "reason": "Not enough candles",
                }
            )

            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        action, score, latest, opening_high = (
            check_signal(dataframe)
        )

        result = {
            "symbol": symbol,
            "action": action,
            "score": score,
            "price": float(latest["close"]),
            "atr": float(latest["atr"]),
            "rsi": float(latest["rsi"]),
            "ema_20": float(latest["ema_20"]),
            "ema_50": float(latest["ema_50"]),
            "vwap": float(latest["vwap"]),
            "macd": float(latest["macd"]),
            "macd_signal": float(
                latest["macd_signal"]
            ),
            "opening_high": opening_high,
            "claude_approved": False,
            "claude_confidence": 0,
            "claude_reason": "",
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


def get_claude_review(
    claude: ClaudeAnalyzer,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    symbol = result["symbol"]

    setup = {
        "price": result.get("price"),
        "score": result.get("score"),
        "rsi": result.get("rsi"),
        "atr": result.get("atr"),
        "ema_20": result.get("ema_20"),
        "ema_50": result.get("ema_50"),
        "vwap": result.get("vwap"),
        "macd": result.get("macd"),
        "macd_signal": result.get("macd_signal"),
        "opening_high": result.get("opening_high"),
    }

    try:
        return claude.review_setup(
            symbol=symbol,
            setup=setup,
        )
    except Exception as error:
        print(
            f"Claude review failed for "
            f"{symbol}: {error}"
        )

        return {
            "approved": False,
            "confidence": 0,
            "reason": "Claude request failed.",
        }


def open_paper_trades(
    scan_results: List[Dict[str, Any]],
    market: MarketData,
    trader: PaperTrader,
    risk_manager: RiskManager,
    claude: ClaudeAnalyzer,
) -> None:
    if not can_open_new_trade():
        print("New entries are currently disabled.")
        return

    for result in scan_results:
        if result.get("action") != "BUY":
            continue

        symbol = result["symbol"]

        if trader.get_open_position(symbol) is not None:
            print(
                f"{symbol}: paper position "
                f"already open."
            )
            continue

        if not risk_manager.can_open_trade(
            daily_realized_pnl=(
                trader.total_realized_pnl()
            ),
            current_open_positions=len(
                trader.open_positions
            ),
        ):
            break

        review = get_claude_review(
            claude=claude,
            result=result,
        )
        save_claude_review(
    symbol=result["symbol"],
    review=review,
)
        approved = bool(
            review.get("approved", False)
        )

        confidence = int(
            review.get("confidence", 0)
        )

        reason = str(
            review.get("reason", "")
        )

        result["claude_approved"] = approved
        result["claude_confidence"] = confidence
        result["claude_reason"] = reason

        if (
            not approved
            or confidence
            < MINIMUM_CLAUDE_CONFIDENCE
        ):
            print(
                f"Claude rejected {symbol} | "
                f"Confidence: {confidence}% | "
                f"Reason: {reason}"
            )
            continue

        print(
            f"Claude approved {symbol} | "
            f"Confidence: {confidence}% | "
            f"Reason: {reason}"
        )

        quote = market.get_live_quote(symbol)

        if (
            not quote
            or quote.get("last_price") is None
        ):
            print(
                f"{symbol}: live quote unavailable."
            )
            continue

        entry_price = float(
            quote["last_price"]
        )

        atr = float(
            result.get("atr", 0)
        )

        if atr <= 0:
            print(
                f"{symbol}: invalid ATR."
            )
            continue

        stop_loss = entry_price - atr
        target_price = entry_price + (2 * atr)

        plan = risk_manager.trade_plan(
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
        )

        quantity = int(
            plan["quantity"]
        )

        if quantity <= 0:
            print(
                f"{symbol}: calculated "
                f"quantity is zero."
            )
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
                f"{symbol} paper trade opened | "
                f"Qty: {quantity} | "
                f"Entry: ₹{entry_price:.2f} | "
                f"Stop: ₹{stop_loss:.2f} | "
                f"Target: ₹{target_price:.2f} | "
                f"Risk: ₹{plan['risk_amount']:.2f}"
            )


def monitor_positions(
    market: MarketData,
    trader: PaperTrader,
) -> None:
    symbols = list(
        trader.open_positions.keys()
    )

    for symbol in symbols:
        quote = market.get_live_quote(symbol)

        if (
            not quote
            or quote.get("last_price") is None
        ):
            print(
                f"{symbol}: monitoring quote "
                f"unavailable."
            )
            continue

        current_price = float(
            quote["last_price"]
        )

        position = trader.get_open_position(
            symbol
        )

        if position is not None:
            unrealized_pnl = (
                current_price
                - position["entry_price"]
            ) * position["quantity"]

            print(
                f"{symbol} | "
                f"Current: ₹{current_price:.2f} | "
                f"Unrealized P&L: "
                f"₹{unrealized_pnl:.2f}"
            )

        trader.check_exit(
            symbol=symbol,
            current_price=current_price,
        )


def close_all_positions(
    market: MarketData,
    trader: PaperTrader,
    reason: str,
) -> None:
    symbols = list(
        trader.open_positions.keys()
    )

    for symbol in symbols:
        quote = market.get_live_quote(symbol)

        if (
            not quote
            or quote.get("last_price") is None
        ):
            print(
                f"{symbol}: closing quote "
                f"unavailable."
            )
            continue

        trader.close_trade(
            symbol=symbol,
            exit_price=float(
                quote["last_price"]
            ),
            exit_reason=reason,
        )


def build_watchlist_display(
    scan_results: List[Dict[str, Any]],
) -> List[str]:
    rows: List[str] = []

    for result in scan_results:
        price = result.get("price")

        price_text = (
            f"₹{price:.2f}"
            if price is not None
            else "No price"
        )

        confidence = result.get(
            "claude_confidence",
            0,
        )

        approval_text = (
            "APPROVED"
            if result.get(
                "claude_approved",
                False,
            )
            else "NOT REVIEWED/REJECTED"
        )

        rows.append(
            f"{result['symbol']:12} "
            f"{price_text:12} | "
            f"Score "
            f"{result.get('score', 0):3}/100 | "
            f"{result.get('action', 'WAIT'):4} | "
            f"Claude: {approval_text} "
            f"{confidence}%"
        )

    return rows


def main() -> None:
    market = MarketData()
    claude = ClaudeAnalyzer()

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

    latest_scan: List[Dict[str, Any]] = []
    last_scan_time = 0.0

    print(
        "Starting automatic "
        "Claude paper trader..."
    )

    while True:
        current_time = now_in_india()
        status = market_status(current_time)

        if status in (
            "CLOSED_WEEKEND",
            "CLOSED",
        ):
            print(
                f"Market status: {status}"
            )
            print("Bot stopped.")
            break

        if (
            current_time.time()
            >= FORCE_EXIT_TIME
        ):
            close_all_positions(
                market=market,
                trader=trader,
                reason="DAY_END_EXIT",
            )

            print(
                "All paper positions "
                "closed for the day."
            )
            break

        monitor_positions(
            market=market,
            trader=trader,
        )

        current_timestamp = time.time()

        should_scan = (
            can_open_new_trade(current_time)
            and (
                current_timestamp
                - last_scan_time
                >= SCAN_INTERVAL_SECONDS
            )
        )

        if should_scan:
            latest_scan = scan_market(market)

            open_paper_trades(
                scan_results=latest_scan,
                market=market,
                trader=trader,
                risk_manager=risk_manager,
                claude=claude,
            )

            last_scan_time = current_timestamp

        Dashboard.show(
            balance=trader.cash_balance,
            pnl=trader.total_realized_pnl(),
            positions=trader.open_positions,
            watchlist=build_watchlist_display(
                latest_scan
            ),
        )

        print(
            f"Market status: {status}"
        )
        print(
            "Press Control + C "
            "to stop the bot."
        )

        time.sleep(
            MONITOR_INTERVAL_SECONDS
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\nPaper trader stopped manually."
        )
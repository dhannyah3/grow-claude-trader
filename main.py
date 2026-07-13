from dotenv import load_dotenv

load_dotenv()

import json
import time
from datetime import time as clock_time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from analytics.adaptive_filter import AdaptiveTradeFilter
from analytics.market_regime import MarketRegime
from analytics.performance_coach import PerformanceCoach
from core.market_clock import (
    can_open_new_trade,
    market_status,
    now_in_india,
)
from core.paper_trader import PaperTrader
from core.risk_manager import RiskManager
from data.market_data import MarketData
from intelligence.market_brain import MarketBrain
from intelligence.market_intelligence import MarketIntelligence
from strategies.claude_analyzer import ClaudeAnalyzer
from strategies.factory import StrategyFactory
from strategies.indicators import calculate_indicators
from utils.dashboard import Dashboard
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
    review: Dict[str, Any],
) -> None:
    CLAUDE_REVIEWS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    reviews: Dict[str, Any] = {}

    if CLAUDE_REVIEWS_FILE.exists():
        try:
            reviews = json.loads(
                CLAUDE_REVIEWS_FILE.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
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

    return (
        f"{day_text} 09:15:00",
        current_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    )


def check_signal(
    dataframe: pd.DataFrame,
) -> Tuple[str, int, pd.Series, float]:
    """
    Legacy ORB scoring helper.

    The live scanner now uses StrategyFactory instead,
    but this remains available for compatibility.
    """

    latest = dataframe.iloc[-1]

    opening_candles = dataframe[
        dataframe["timestamp"].dt.time
        < clock_time(9, 30)
    ]

    if opening_candles.empty:
        return "WAIT", 0, latest, 0.0

    opening_high = float(
        opening_candles["high"].max()
    )

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
    market_regime: MarketRegime,
    market_intelligence: MarketIntelligence,
    market_brain: MarketBrain,
) -> List[Dict[str, Any]]:
    """
    Scan the watchlist and let MarketBrain choose
    the strategy used for each symbol.
    """

    start_time, end_time = get_today_time_range()
    scan_results: List[Dict[str, Any]] = []

    for symbol in WATCHLIST:
        print(f"Scanning {symbol}...")

        candles = market.get_historical_data(
            groww_symbol=f"NSE-{symbol}",
            start_time=start_time,
            end_time=end_time,
            interval=(
                market.groww
                .CANDLE_INTERVAL_MIN_1
            ),
        )

        if (
            not candles
            or not candles.get("candles")
        ):
            print(f"{symbol}: no candle data.")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        dataframe = calculate_indicators(
            candles
        )

        if len(dataframe) < MINIMUM_CANDLES:
            print(
                f"{symbol}: not enough candles."
            )

            scan_results.append(
                {
                    "symbol": symbol,
                    "action": "WAIT",
                    "score": 0,
                    "price": None,
                    "strategy": None,
                    "strategy_reason": (
                        "Not enough candles."
                    ),
                    "claude_approved": False,
                    "claude_confidence": 0,
                    "claude_reason": "",
                }
            )

            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        indicator_dataframe = (
            dataframe.dropna(
                subset=[
                    "ema_20",
                    "ema_50",
                    "rsi",
                    "vwap",
                    "atr",
                    "macd",
                    "macd_signal",
                ]
            )
        )

        if indicator_dataframe.empty:
            print(
                f"{symbol}: indicators are not ready."
            )

            scan_results.append(
                {
                    "symbol": symbol,
                    "action": "WAIT",
                    "score": 0,
                    "price": None,
                    "strategy": None,
                    "strategy_reason": (
                        "Indicators unavailable."
                    ),
                    "claude_approved": False,
                    "claude_confidence": 0,
                    "claude_reason": "",
                }
            )

            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        latest = indicator_dataframe.iloc[-1]
        first_candle = dataframe.iloc[0]

        regime_input = latest.to_dict()
        regime_input["open"] = float(
            first_candle["open"]
        )

        try:
            regime_data = market_regime.analyze(
                latest=regime_input,
                previous_close=None,
            )

            intelligence = (
                market_intelligence.analyze(
                    dataframe=indicator_dataframe,
                    regime=regime_data,
                )
            )

            try:
                brain_decision = (
                    market_brain.decide(
                        regime_data=regime_data,
                        intelligence=intelligence,
                    )
                )
            except TypeError:
                # Backward compatibility with MarketBrain v1.
                brain_decision = (
                    market_brain.decide(
                        regime_data=regime_data,
                    )
                )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            print(
                f"{symbol}: market analysis "
                f"failed: {error}"
            )
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        selected_strategy = str(
            brain_decision.get(
                "recommended_strategy",
                "VWAP_PULLBACK",
            )
        )

        try:
            strategy = StrategyFactory.get(
                selected_strategy
            )
        except ValueError as error:
            print(f"{symbol}: {error}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        strategy_signal = strategy.analyze(
            dataframe
        )

        action = str(
            strategy_signal.get(
                "action",
                "WAIT",
            )
        ).upper()

        score = int(
            strategy_signal.get(
                "score",
                0,
            )
        )

        signal_reason = str(
            strategy_signal.get(
                "reason",
                "",
            )
        )

        if not brain_decision.get(
            "should_trade",
            False,
        ):
            action = "WAIT"
            signal_reason = (
                "MarketBrain rejected trading. "
                + signal_reason
            )

        strategy_metadata = (
            strategy_signal.get(
                "metadata",
                {},
            )
        )

        opening_high = (
            strategy_metadata.get(
                "opening_high"
            )
            if isinstance(
                strategy_metadata,
                dict,
            )
            else None
        )

        result = {
            "symbol": symbol,
            "action": action,
            "score": score,
            "price": float(
                latest["close"]
            ),
            "atr": float(
                latest["atr"]
            ),
            "rsi": float(
                latest["rsi"]
            ),
            "ema_20": float(
                latest["ema_20"]
            ),
            "ema_50": float(
                latest["ema_50"]
            ),
            "vwap": float(
                latest["vwap"]
            ),
            "macd": float(
                latest["macd"]
            ),
            "macd_signal": float(
                latest["macd_signal"]
            ),
            "opening_high": opening_high,
            "day_open": float(
                first_candle["open"]
            ),
            "strategy": selected_strategy,
            "strategy_class": (
                type(strategy).__name__
            ),
            "strategy_reason": signal_reason,
            "strategy_metadata": (
                strategy_metadata
            ),
            "suggested_entry": (
                strategy_signal.get(
                    "entry_price"
                )
            ),
            "suggested_stop_loss": (
                strategy_signal.get(
                    "stop_loss"
                )
            ),
            "suggested_target": (
                strategy_signal.get(
                    "target"
                )
            ),
            "market_regime": regime_data,
            "market_intelligence": intelligence,
            "market_quality": (
                intelligence.get(
                    "market_quality",
                    0,
                )
            ),
            "rsi_state": intelligence.get(
                "rsi_state",
                "UNKNOWN",
            ),
            "macd_state": intelligence.get(
                "macd_state",
                "UNKNOWN",
            ),
            "vwap_state": intelligence.get(
                "vwap_state",
                "UNKNOWN",
            ),
            "volume_state": intelligence.get(
                "volume_state",
                "UNKNOWN",
            ),
            "market_brain": brain_decision,
            "brain_confidence": (
                brain_decision.get(
                    "confidence",
                    0,
                )
            ),
            "brain_risk_multiplier": (
                brain_decision.get(
                    "risk_multiplier",
                    1.0,
                )
            ),
            "claude_approved": False,
            "claude_confidence": 0,
            "claude_reason": "",
        }

        scan_results.append(result)

        print(
            f"{symbol} | "
            f"Price: ₹{result['price']:.2f} | "
            f"Quality: "
            f"{result['market_quality']}/100 | "
            f"Regime: "
            f"{regime_data['trend']} | "
            f"Strategy: "
            f"{selected_strategy} | "
            f"Score: {score}/100 | "
            f"Signal: {action} | "
            f"Reason: {signal_reason}"
        )

        time.sleep(REQUEST_DELAY_SECONDS)

    return scan_results


def get_claude_review(
    claude: ClaudeAnalyzer,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    symbol = result["symbol"]

    setup = {
        "strategy": result.get("strategy"),
        "price": result.get("price"),
        "score": result.get("score"),
        "market_quality": result.get(
            "market_quality"
        ),
        "rsi": result.get("rsi"),
        "rsi_state": result.get(
            "rsi_state"
        ),
        "atr": result.get("atr"),
        "ema_20": result.get("ema_20"),
        "ema_50": result.get("ema_50"),
        "vwap": result.get("vwap"),
        "vwap_state": result.get(
            "vwap_state"
        ),
        "macd": result.get("macd"),
        "macd_signal": result.get(
            "macd_signal"
        ),
        "macd_state": result.get(
            "macd_state"
        ),
        "volume_state": result.get(
            "volume_state"
        ),
        "opening_high": result.get(
            "opening_high"
        ),
        "strategy_reason": result.get(
            "strategy_reason"
        ),
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
    performance_coach: PerformanceCoach,
    adaptive_filter: AdaptiveTradeFilter,
) -> None:
    """
    Open paper trades from already analyzed scanner results.

    The scanner has already produced:
    - market regime;
    - market intelligence;
    - MarketBrain decision;
    - selected strategy;
    - strategy entry, stop, and target.
    """

    if not can_open_new_trade():
        print("New entries are currently disabled.")
        return

    for result in scan_results:
        if result.get("action") != "BUY":
            continue

        symbol = str(
            result.get(
                "symbol",
                "",
            )
        ).strip()

        if not symbol:
            print(
                "Skipping result without a symbol."
            )
            continue

        if (
            trader.get_open_position(symbol)
            is not None
        ):
            print(
                f"{symbol}: paper position "
                "already open."
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
            print(
                "Risk manager rejected "
                "new trades."
            )
            break

        review = get_claude_review(
            claude=claude,
            result=result,
        )

        save_claude_review(
            symbol=symbol,
            review=review,
        )

        approved = bool(
            review.get(
                "approved",
                False,
            )
        )

        confidence = int(
            review.get(
                "confidence",
                0,
            )
        )

        claude_reason = str(
            review.get(
                "reason",
                "",
            )
        )

        result["claude_approved"] = approved
        result["claude_confidence"] = (
            confidence
        )
        result["claude_reason"] = (
            claude_reason
        )

        if (
            not approved
            or confidence
            < MINIMUM_CLAUDE_CONFIDENCE
        ):
            print(
                f"Claude rejected {symbol} | "
                f"Confidence: {confidence}% | "
                f"Reason: {claude_reason}"
            )
            continue

        print(
            f"Claude approved {symbol} | "
            f"Confidence: {confidence}% | "
            f"Reason: {claude_reason}"
        )

        selected_strategy = str(
            result.get(
                "strategy",
                "UNKNOWN",
            )
        )

        regime_data = result.get(
            "market_regime",
            {},
        )

        brain_decision = result.get(
            "market_brain",
            {},
        )

        intelligence = result.get(
            "market_intelligence",
            {},
        )

        if not brain_decision.get(
            "should_trade",
            False,
        ):
            print(
                f"{symbol}: MarketBrain "
                "rejected the trade."
            )
            continue

        performance_report = (
            performance_coach.analyze()
        )

        market_condition = str(
            regime_data.get(
                "trend",
                "UNKNOWN",
            )
        )

        adaptive_decision = (
            adaptive_filter.evaluate(
                strategy=selected_strategy,
                confidence=confidence,
                market_condition=(
                    market_condition
                ),
                performance_report=(
                    performance_report
                ),
                regime_data=regime_data,
            )
        )

        print(
            f"Adaptive filter for {symbol}:"
        )

        for adaptive_reason in (
            adaptive_decision["reasons"]
        ):
            print(f"- {adaptive_reason}")

        if not adaptive_decision[
            "take_trade"
        ]:
            print(
                f"{symbol}: trade rejected by "
                "adaptive filter."
            )
            continue

        brain_multiplier = float(
            brain_decision.get(
                "risk_multiplier",
                1.0,
            )
        )

        adaptive_multiplier = float(
            adaptive_decision.get(
                "position_multiplier",
                1.0,
            )
        )

        quality = float(
            intelligence.get(
                "market_quality",
                0,
            )
        )

        quality_multiplier = max(
            0.5,
            min(
                quality / 100,
                1.0,
            ),
        )

        final_position_multiplier = (
            brain_multiplier
            * adaptive_multiplier
            * quality_multiplier
        )

        final_position_multiplier = max(
            0.0,
            min(
                final_position_multiplier,
                1.0,
            ),
        )

        result["adaptive_take_trade"] = (
            adaptive_decision[
                "take_trade"
            ]
        )
        result["adaptive_reasons"] = (
            adaptive_decision["reasons"]
        )
        result["brain_multiplier"] = (
            brain_multiplier
        )
        result["adaptive_multiplier"] = (
            adaptive_multiplier
        )
        result["quality_multiplier"] = (
            quality_multiplier
        )
        result["position_multiplier"] = (
            round(
                final_position_multiplier,
                4,
            )
        )

        if final_position_multiplier <= 0:
            print(
                f"{symbol}: final position "
                "multiplier is zero."
            )
            continue

        quote = market.get_live_quote(
            symbol
        )

        if (
            not quote
            or quote.get("last_price")
            is None
        ):
            print(
                f"{symbol}: live quote "
                "unavailable."
            )
            continue

        entry_price = float(
            quote["last_price"]
        )

        atr = float(
            result.get(
                "atr",
                0,
            )
            or 0
        )

        if entry_price <= 0 or atr <= 0:
            print(
                f"{symbol}: invalid price "
                "or ATR."
            )
            continue

        suggested_stop_loss = result.get(
            "suggested_stop_loss"
        )
        suggested_target = result.get(
            "suggested_target"
        )

        stop_loss = (
            float(suggested_stop_loss)
            if suggested_stop_loss
            else entry_price - atr
        )

        target_price = (
            float(suggested_target)
            if suggested_target
            else entry_price + (2 * atr)
        )

        if not (
            0 < stop_loss < entry_price
            < target_price
        ):
            print(
                f"{symbol}: invalid strategy "
                "stop or target."
            )
            continue

        plan = risk_manager.trade_plan(
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
        )

        base_quantity = int(
            plan.get(
                "quantity",
                0,
            )
        )

        quantity = int(
            base_quantity
            * final_position_multiplier
        )

        if quantity <= 0:
            print(
                f"{symbol}: adjusted quantity "
                "is zero."
            )
            continue

        opened = trader.open_trade(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target_price,
        )

        if not opened:
            print(
                f"{symbol}: paper trade "
                "was not opened."
            )
            continue

        adjusted_risk = (
            float(
                plan.get(
                    "risk_amount",
                    0.0,
                )
            )
            * final_position_multiplier
        )

        print(
            f"{symbol} paper trade opened | "
            f"Strategy: {selected_strategy} | "
            f"Qty: {quantity} | "
            f"Base Qty: {base_quantity} | "
            f"Brain: {brain_multiplier:.2f} | "
            f"Adaptive: "
            f"{adaptive_multiplier:.2f} | "
            f"Quality: "
            f"{quality_multiplier:.2f} | "
            f"Final: "
            f"{final_position_multiplier:.2f} | "
            f"Entry: ₹{entry_price:.2f} | "
            f"Stop: ₹{stop_loss:.2f} | "
            f"Target: ₹{target_price:.2f} | "
            f"Estimated Risk: "
            f"₹{adjusted_risk:.2f}"
        )


def monitor_positions(
    market: MarketData,
    trader: PaperTrader,
) -> None:
    symbols = list(
        trader.open_positions.keys()
    )

    for symbol in symbols:
        quote = market.get_live_quote(
            symbol
        )

        if (
            not quote
            or quote.get("last_price")
            is None
        ):
            print(
                f"{symbol}: monitoring quote "
                "unavailable."
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
        quote = market.get_live_quote(
            symbol
        )

        if (
            not quote
            or quote.get("last_price")
            is None
        ):
            print(
                f"{symbol}: closing quote "
                "unavailable."
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
            f"₹{float(price):.2f}"
            if price is not None
            else "No price"
        )

        action = str(
            result.get(
                "action",
                "WAIT",
            )
        ).upper()

        score = int(
            result.get(
                "score",
                0,
            )
        )

        strategy = str(
            result.get(
                "strategy",
                "UNSELECTED",
            )
            or "UNSELECTED"
        )

        quality = int(
            result.get(
                "market_quality",
                0,
            )
            or 0
        )

        reason = str(
            result.get(
                "strategy_reason",
                result.get(
                    "reason",
                    "",
                ),
            )
        )

        claude_confidence = int(
            result.get(
                "claude_confidence",
                0,
            )
        )

        if action != "BUY":
            claude_status = "NOT NEEDED"

        elif result.get(
            "claude_approved",
            False,
        ):
            claude_status = (
                f"APPROVED "
                f"{claude_confidence}%"
            )

        elif claude_confidence > 0:
            claude_status = (
                f"REJECTED "
                f"{claude_confidence}%"
            )

        else:
            claude_status = "PENDING"

        if len(reason) > 42:
            reason = (
                reason[:39]
                + "..."
            )

        rows.append(
            f"{result['symbol']:12} "
            f"{price_text:12} | "
            f"{strategy:14} | "
            f"Q {quality:3}/100 | "
            f"S {score:3}/100 | "
            f"{action:4} | "
            f"Claude: {claude_status} | "
            f"{reason}"
        )

    return rows


def main() -> None:
    market = MarketData()
    market_regime = MarketRegime()
    market_intelligence = (
        MarketIntelligence()
    )
    market_brain = MarketBrain()
    claude = ClaudeAnalyzer()

    performance_coach = (
        PerformanceCoach()
    )

    adaptive_filter = (
        AdaptiveTradeFilter(
            minimum_confidence=80,
            minimum_win_rate=50.0,
            minimum_sample_size=5,
            weak_market_multiplier=0.5,
        )
    )

    trader = PaperTrader(
        starting_balance=100000.0,
        log_file="logs/paper_trades.csv",
    )

    risk_manager = RiskManager(
        account_balance=(
            trader.starting_balance
        ),
        risk_per_trade_percent=0.5,
        max_daily_loss_percent=2.0,
        max_position_percent=20.0,
        max_open_positions=2,
    )

    latest_scan: List[
        Dict[str, Any]
    ] = []

    last_scan_time = 0.0

    print(
        "Starting automatic "
        "Claude paper trader..."
    )

    while True:
        current_time = now_in_india()
        status = market_status(
            current_time
        )

        if status in {
            "CLOSED_WEEKEND",
            "CLOSED",
        }:
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
            can_open_new_trade(
                current_time
            )
            and (
                current_timestamp
                - last_scan_time
                >= SCAN_INTERVAL_SECONDS
            )
        )

        if should_scan:
            latest_scan = scan_market(
                market=market,
                market_regime=(
                    market_regime
                ),
                market_intelligence=(
                    market_intelligence
                ),
                market_brain=(
                    market_brain
                ),
            )

            open_paper_trades(
                scan_results=latest_scan,
                market=market,
                trader=trader,
                risk_manager=risk_manager,
                claude=claude,
                performance_coach=(
                    performance_coach
                ),
                adaptive_filter=(
                    adaptive_filter
                ),
            )

            last_scan_time = (
                current_timestamp
            )

        elif (
            status == "NO_NEW_ENTRIES"
            and not latest_scan
        ):
            latest_scan = [
                {
                    "symbol": "MARKET",
                    "price": None,
                    "strategy": (
                        "ENTRY_WINDOW_CLOSED"
                    ),
                    "score": 0,
                    "market_quality": 0,
                    "action": "WAIT",
                    "strategy_reason": (
                        "New entries are disabled "
                        "for the rest of the "
                        "session."
                    ),
                    "claude_approved": False,
                    "claude_confidence": 0,
                    "claude_reason": "",
                }
            ]

        Dashboard.show(
            balance=trader.cash_balance,
            pnl=(
                trader.total_realized_pnl()
            ),
            positions=(
                trader.open_positions
            ),
            watchlist=(
                build_watchlist_display(
                    latest_scan
                )
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
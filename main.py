from dotenv import load_dotenv

load_dotenv()

import json
import time
from datetime import time as clock_time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from execution.sell_execution import (
    execute_paper_sell,
)

from analytics.adaptive_filter import AdaptiveTradeFilter
from analytics.market_learning import MarketLearning
from analytics.market_regime import MarketRegime
from analytics.recommendation_engine import (
    RecommendationEngine,
)
from analytics.performance_coach import PerformanceCoach
from core.dynamic_position_sizer import (
    DynamicPositionSizer,
)
from core.market_clock import (
    can_open_new_trade,
    market_status,
    now_in_india,
)
from core.paper_trader import PaperTrader
from core.portfolio_heat_manager import (
    PortfolioHeatManager,
)
from core.risk_manager import RiskManager
from core.safety_manager import SafetyManager
from core.trade_lifecycle import TradeLifecycle
from data.market_data import MarketData
from intelligence.market_brain import MarketBrain
from intelligence.market_intelligence import MarketIntelligence
from strategies.claude_analyzer import ClaudeAnalyzer
from strategies.factory import StrategyFactory
from strategies.indicators import calculate_indicators
from utils.dashboard import Dashboard
from watchlist import WATCHLIST
from execution.order_executor import OrderExecutor
from execution.order_manager import OrderManager
from execution.position_sync import PositionSynchronizer
from execution.live_execution_controller import (
    LiveExecutionController,
)


MINIMUM_SCORE = 70
MINIMUM_CLAUDE_CONFIDENCE = 70

SCAN_INTERVAL_SECONDS = 60
REQUEST_DELAY_SECONDS = 1.5
MONITOR_INTERVAL_SECONDS = 10
POSITION_SYNC_INTERVAL_SECONDS = 300

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



def prepare_learning_trades(
    closed_trades: Any,
) -> List[Dict[str, Any]]:
    """
    Normalize PaperTrader history for MarketLearning.

    Older CSV-loaded trades may not contain metadata,
    R multiples, or holding time. Missing values are
    calculated where possible and otherwise defaulted
    safely.
    """
    if not isinstance(
        closed_trades,
        list,
    ):
        return []

    normalized_trades: List[
        Dict[str, Any]
    ] = []

    for original_trade in closed_trades:
        if not isinstance(
            original_trade,
            dict,
        ):
            continue

        trade = dict(
            original_trade
        )

        metadata = trade.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        trade["strategy"] = str(
            trade.get(
                "strategy",
                metadata.get(
                    "strategy",
                    "UNKNOWN",
                ),
            )
        ).strip().upper()

        trade["market_condition"] = str(
            trade.get(
                "market_condition",
                metadata.get(
                    "market_condition",
                    "UNKNOWN",
                ),
            )
        ).strip().upper()

        if "r_multiple" not in trade:
            try:
                entry_price = float(
                    trade.get(
                        "entry_price",
                        0.0,
                    )
                    or 0.0
                )

                stop_loss = float(
                    trade.get(
                        "initial_stop_loss",
                        trade.get(
                            "stop_loss",
                            0.0,
                        ),
                    )
                    or 0.0
                )

                quantity = int(
                    trade.get(
                        "quantity",
                        0,
                    )
                    or 0
                )

                initial_risk = (
                    entry_price
                    - stop_loss
                ) * quantity

                pnl = float(
                    trade.get(
                        "pnl",
                        0.0,
                    )
                    or 0.0
                )

                trade["r_multiple"] = (
                    pnl / initial_risk
                    if initial_risk > 0
                    else 0.0
                )

            except (
                TypeError,
                ValueError,
            ):
                trade["r_multiple"] = 0.0

        if "holding_minutes" not in trade:
            try:
                entry_time = pd.to_datetime(
                    trade.get(
                        "entry_time"
                    )
                )

                exit_time = pd.to_datetime(
                    trade.get(
                        "exit_time"
                    )
                )

                holding_minutes = (
                    exit_time
                    - entry_time
                ).total_seconds() / 60.0

                trade["holding_minutes"] = max(
                    0.0,
                    float(
                        holding_minutes
                    ),
                )

            except (
                TypeError,
                ValueError,
            ):
                trade["holding_minutes"] = 0.0

        normalized_trades.append(
            trade
        )

    return normalized_trades


def build_trade_recommendation(
    market_learning: MarketLearning,
    recommendation_engine: RecommendationEngine,
    trader: PaperTrader,
    strategy: str,
    market_condition: str,
    claude_confidence: int,
) -> Dict[str, Any]:
    """
    Build a recommendation for the strategy selected
    for the current signal.

    During the paper-learning cold start, fewer than
    20 historical trades produce INSUFFICIENT_DATA.
    The system then permits a reduced-size exploratory
    paper trade so it can collect evidence safely.
    """
    learning_trades = prepare_learning_trades(
        getattr(
            trader,
            "closed_trades",
            [],
        )
    )

    market_learning.load_trades(
        learning_trades
    )

    normalized_strategy = str(
        strategy
    ).strip().upper()

    normalized_market = str(
        market_condition
    ).strip().upper()

    statistics = (
        market_learning
        .strategy_market_statistics(
            strategy=normalized_strategy,
            market_condition=normalized_market,
        )
    )

    statistics_source = (
        "STRATEGY_MARKET"
    )

    if not statistics:
        statistics = (
            market_learning
            .strategy_statistics(
                normalized_strategy
            )
        )

        statistics_source = (
            "STRATEGY_OVERALL"
        )

    recommendation_input = (
        {
            normalized_strategy: (
                statistics
            )
        }
        if statistics
        else {}
    )

    recommendation = (
        recommendation_engine.recommend(
            recommendation_input
        )
    )

    recommendation[
        "statistics_source"
    ] = statistics_source

    recommendation[
        "market_condition"
    ] = normalized_market

    if recommendation.get(
        "decision"
    ) == "INSUFFICIENT_DATA":
        cold_start_confidence = max(
            60.0,
            min(
                float(
                    claude_confidence
                ),
                74.99,
            ),
        )

        existing_reasons = list(
            recommendation.get(
                "reasons",
                [],
            )
        )

        recommendation.update(
            {
                "decision": "TAKE_TRADE",
                "recommendation": (
                    "TAKE_TRADE"
                ),
                "decision_confidence": (
                    cold_start_confidence
                ),
                "risk_level": "HIGH",
                "selected_strategy": (
                    normalized_strategy
                ),
                "learning_active": False,
                "cold_start_mode": True,
                "reasons": (
                    existing_reasons
                    + [
                        (
                            "Paper-learning cold start: "
                            "allowing a reduced-size "
                            "exploratory trade."
                        )
                    ]
                ),
            }
        )

    else:
        recommendation[
            "cold_start_mode"
        ] = False

    return recommendation

def open_paper_trades(
    scan_results: List[Dict[str, Any]],
    market: MarketData,
    trader: PaperTrader,
    lifecycle: TradeLifecycle,
    risk_manager: RiskManager,
    claude: ClaudeAnalyzer,
    performance_coach: PerformanceCoach,
    adaptive_filter: AdaptiveTradeFilter,
    market_learning: MarketLearning,
    recommendation_engine: RecommendationEngine,
    dynamic_position_sizer: DynamicPositionSizer,
    portfolio_heat_manager: PortfolioHeatManager,
    live_execution_controller: LiveExecutionController,
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

        pre_dynamic_quantity = int(
            base_quantity
            * final_position_multiplier
        )

        recommendation = (
            build_trade_recommendation(
                market_learning=(
                    market_learning
                ),
                recommendation_engine=(
                    recommendation_engine
                ),
                trader=trader,
                strategy=selected_strategy,
                market_condition=(
                    market_condition
                ),
                claude_confidence=(
                    confidence
                ),
            )
        )

        position_result = (
            dynamic_position_sizer
            .size_position(
                recommendation=(
                    recommendation
                ),
                base_quantity=(
                    pre_dynamic_quantity
                ),
            )
        )

        if not position_result.get(
            "allowed",
            False,
        ):
            print(
                f"{symbol}: "
                f"{position_result.get('reason', 'Position blocked.')}"
            )
            continue

        quantity = int(
            position_result.get(
                "adjusted_quantity",
                0,
            )
        )

        dynamic_multiplier = float(
            position_result.get(
                "position_multiplier",
                0.0,
            )
            or 0.0
        )

        combined_position_multiplier = (
            final_position_multiplier
            * dynamic_multiplier
        )

        if quantity <= 0:
            print(
                f"{symbol}: dynamic position "
                "quantity is zero."
            )
            continue

        result["recommendation"] = (
            recommendation
        )
        result["position_sizing"] = (
            position_result
        )
        result["dynamic_multiplier"] = (
            dynamic_multiplier
        )
        result[
            "combined_position_multiplier"
        ] = round(
            combined_position_multiplier,
            4,
        )

        adjusted_risk = (
            float(
                plan.get(
                    "risk_amount",
                    0.0,
                )
            )
            * combined_position_multiplier
        )

        proposed_sector = str(
            result.get(
                "sector",
                result.get(
                    "industry",
                    "UNKNOWN",
                ),
            )
            or "UNKNOWN"
        ).strip().upper()

        open_position_risk = []

        for open_position in (
            trader.open_positions.values()
        ):
            if not isinstance(
                open_position,
                dict,
            ):
                continue

            open_metadata = open_position.get(
                "metadata",
                {},
            )

            if not isinstance(
                open_metadata,
                dict,
            ):
                open_metadata = {}

            open_position_risk.append(
                {
                    "risk_amount": float(
                        open_metadata.get(
                            "adjusted_risk",
                            0.0,
                        )
                        or 0.0
                    ),
                    "sector": str(
                        open_metadata.get(
                            "sector",
                            "UNKNOWN",
                        )
                        or "UNKNOWN"
                    ).strip().upper(),
                }
            )

        heat_result = (
            portfolio_heat_manager.evaluate(
                account_balance=float(
                    trader.starting_balance
                ),
                proposed_risk_amount=(
                    adjusted_risk
                ),
                open_positions=(
                    open_position_risk
                ),
                proposed_sector=(
                    proposed_sector
                ),
            )
        )

        if not heat_result.get(
            "allowed",
            False,
        ):
            print(
                f"{symbol}: portfolio heat "
                f"blocked trade | "
                f"{heat_result.get('reason', 'Risk limit exceeded.')}"
            )
            continue

        result["portfolio_heat"] = (
            heat_result
        )
        result["adjusted_risk"] = (
            adjusted_risk
        )
        result["sector"] = proposed_sector

        execution_result = (
            live_execution_controller.execute_buy(
                symbol=symbol,
                quantity=quantity,
                price=entry_price,
                metadata={
                    "strategy": selected_strategy,
                    "market_condition": (
                        market_condition
                    ),
                    "sector": proposed_sector,
                    "paper_trade": True,
                },
            )
        )

        if not execution_result.get(
            "success",
            False,
        ):
            execution_details = (
                execution_result.get(
                    "execution",
                    {},
                )
                or {}
            )

            print(
                f"{symbol}: simulated BUY "
                f"execution failed | "
                f"{execution_details.get('reason', 'Unknown reason')}"
            )
            continue

        execution_details = (
            execution_result.get(
                "execution",
                {},
            )
            or {}
        )

        execution_order = (
            execution_result.get(
                "order",
                {},
            )
            or {}
        )

        order_status = str(
            execution_order.get(
                "status",
                execution_details.get(
                    "status",
                    "UNKNOWN",
                ),
            )
        )

        internal_order_id = (
            execution_order.get(
                "internal_order_id"
            )
        )

        broker_order_id = (
            execution_order.get(
                "broker_order_id"
            )
        )

        result["execution"] = (
            execution_details
        )
        result["execution_order"] = (
            execution_order
        )
        result["internal_order_id"] = (
            internal_order_id
        )
        result["broker_order_id"] = (
            broker_order_id
        )
        result["order_status"] = (
            order_status
        )

        print(
            f"{symbol}: BUY execution "
            f"registered | "
            f"Mode: "
            f"{execution_details.get('mode', 'UNKNOWN')} | "
            f"Status: {order_status} | "
            f"Internal Order ID: "
            f"{internal_order_id}"
        )

        opened = trader.open_trade(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target=target_price,
            metadata={
                "strategy": selected_strategy,
                "strategy_score": int(
                    result.get(
                        "score",
                        0,
                    )
                    or 0
                ),
                "market_condition": (
                    market_condition
                ),
                "market_regime": regime_data,
                "market_intelligence": (
                    intelligence
                ),
                "market_brain": brain_decision,
                "claude_review": {
                    "approved": approved,
                    "confidence": confidence,
                    "reason": claude_reason,
                },
                "position_multiplier": round(
                    combined_position_multiplier,
                    4,
                ),
                "pre_dynamic_multiplier": round(
                    final_position_multiplier,
                    4,
                ),
                "dynamic_multiplier": (
                    dynamic_multiplier
                ),
                "recommendation": (
                    recommendation
                ),
                "position_sizing": (
                    position_result
                ),
                "portfolio_heat": (
                    heat_result
                ),
                "adjusted_risk": (
                    adjusted_risk
                ),
                "sector": proposed_sector,
                "execution": (
                    execution_details
                ),
                "execution_order": (
                    execution_order
                ),
                "internal_order_id": (
                    internal_order_id
                ),
                "broker_order_id": (
                    broker_order_id
                ),
                "order_status": (
                    order_status
                ),
                "brain_multiplier": (
                    brain_multiplier
                ),
                "adaptive_multiplier": (
                    adaptive_multiplier
                ),
                "quality_multiplier": (
                    quality_multiplier
                ),
                "adaptive_decision": (
                    adaptive_decision
                ),
                "indicators": {
                    "rsi": result.get(
                        "rsi"
                    ),
                    "atr": result.get(
                        "atr"
                    ),
                    "ema_20": result.get(
                        "ema_20"
                    ),
                    "ema_50": result.get(
                        "ema_50"
                    ),
                    "vwap": result.get(
                        "vwap"
                    ),
                    "macd": result.get(
                        "macd"
                    ),
                    "macd_signal": (
                        result.get(
                            "macd_signal"
                        )
                    ),
                    "opening_high": (
                        result.get(
                            "opening_high"
                        )
                    ),
                },
            },
        )

        if not opened:
            print(
                f"{symbol}: paper trade "
                "was not opened."
            )
            continue

        lifecycle_opened = (
            lifecycle.open_trade(
                symbol=symbol,
                strategy=selected_strategy,
                quantity=quantity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target=target_price,

                metadata={
                    "strategy": (
                        selected_strategy
                    ),
                    "market_condition": (
                        market_condition
                    ),
                    "market_regime": (
                        regime_data
                    ),
                    "market_intelligence": (
                        intelligence
                    ),
                    "market_brain": (
                        brain_decision
                    ),
                    "claude_review": {
                        "approved": approved,
                        "confidence": confidence,
                        "reason": claude_reason,
                    },
                    "recommendation": (
                        recommendation
                    ),
                    "position_sizing": (
                        position_result
                    ),
                    "portfolio_heat": (
                        heat_result
                    ),
                    "adjusted_risk": (
                        adjusted_risk
                    ),
                    "sector": proposed_sector,
                    "execution": (
                        execution_details
                    ),
                    "execution_order": (
                        execution_order
                    ),
                    "internal_order_id": (
                        internal_order_id
                    ),
                    "broker_order_id": (
                        broker_order_id
                    ),
                    "order_status": (
                        order_status
                    ),
                    "position_multiplier": round(
                        combined_position_multiplier,
                        4,
                    ),
                    "indicators": {
                        "rsi": result.get(
                            "rsi"
                        ),
                        "atr": result.get(
                            "atr"
                        ),
                        "ema_20": result.get(
                            "ema_20"
                        ),
                        "ema_50": result.get(
                            "ema_50"
                        ),
                        "vwap": result.get(
                            "vwap"
                        ),
                        "macd": result.get(
                            "macd"
                        ),
                        "macd_signal": (
                            result.get(
                                "macd_signal"
                            )
                        ),
                        "opening_high": (
                            result.get(
                                "opening_high"
                            )
                        ),
                    },
                },
            )
        )

        if not lifecycle_opened:
            print(
                f"{symbol}: lifecycle mirror failed. "
                "Closing paper trade to keep "
                "state consistent."
            )

            trader.close_trade(
                symbol=symbol,
                exit_price=entry_price,
                exit_reason=(
                    "LIFECYCLE_SYNC_FAILED"
                ),
            )
            continue

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
            f"Pre-Dynamic: "
            f"{final_position_multiplier:.2f} | "
            f"Dynamic: "
            f"{dynamic_multiplier:.2f} | "
            f"Combined: "
            f"{combined_position_multiplier:.2f} | "
            f"Decision: "
            f"{recommendation.get('decision', 'UNKNOWN')} | "
            f"Entry: ₹{entry_price:.2f} | "
            f"Stop: ₹{stop_loss:.2f} | "
            f"Target: ₹{target_price:.2f} | "
            f"Estimated Risk: "
            f"₹{adjusted_risk:.2f}"
        )


def monitor_positions(
    market: MarketData,
    trader: PaperTrader,
    lifecycle: TradeLifecycle,
    live_execution_controller: LiveExecutionController,
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

        lifecycle_update = (
            lifecycle.update_price(
                symbol=symbol,
                current_price=current_price,
            )
        )

        if not lifecycle_update.get(
            "updated",
            False,
        ):
            print(
                lifecycle_update.get(
                    "reason",
                    f"{symbol}: lifecycle "
                    "update failed.",
                )
            )
            continue

        # -------------------------
        # Synchronize stop loss
        # -------------------------

        lifecycle_stop = float(
            lifecycle_update.get(
                "stop_loss",
                0.0,
            )
            or 0.0
        )

        paper_position = (
            trader.get_open_position(
                symbol
            )
        )

        if (
            paper_position is not None
            and lifecycle_stop
            > float(
                paper_position[
                    "stop_loss"
                ]
            )
        ):
            trader.update_stop_loss(
                symbol=symbol,
                stop_loss=lifecycle_stop,
            )

        # -------------------------
        # Execute partial exit
        # -------------------------

        partial_exit = (
            lifecycle_update.get(
                "partial_exit",
                {},
            )
        )

        if (
            isinstance(
                partial_exit,
                dict,
            )
            and partial_exit.get(
                "execute",
                False,
            )
        ):
            partial_quantity = int(
                partial_exit.get(
                    "quantity",
                    0,
                )
            )

            partial_price = float(
                partial_exit.get(
                    "exit_price",
                    current_price,
                )
            )

            partial_reason = str(
                partial_exit.get(
                    "reason",
                    "PARTIAL_TARGET",
                )
            )

            sell_result = execute_paper_sell(
                controller=(
                    live_execution_controller
                ),
                symbol=symbol,
                quantity=partial_quantity,
                price=partial_price,
                reason=partial_reason,
                metadata={
                    "partial_exit": True,
                },
            )

            if not sell_result.get(
                "success",
                False,
            ):
                print(
                    f"{symbol}: partial SELL "
                    "execution registration failed."
                )
                continue

            partial_result = (
                trader.partial_close_trade(
                    symbol=symbol,
                    exit_price=partial_price,
                    quantity=partial_quantity,
                    exit_reason=partial_reason,
                )
            )

            if partial_result is None:
                print(
                    f"{symbol}: partial exit "
                    "execution failed."
                )

            else:
                print(
                    f"{symbol}: partial profit "
                    f"booked | Qty: "
                    f"{partial_result['quantity']} | "
                    f"Remaining: "
                    f"{partial_result['remaining_quantity']} | "
                    f"Partial P&L: ₹"
                    f"{partial_result['partial_pnl']:.2f}"
                )

        print(
            f"{symbol} | "
            f"Current: ₹{current_price:.2f} | "
            f"Remaining Qty: "
            f"{lifecycle_update.get('remaining_quantity', 0)} | "
            f"Unrealized P&L: ₹"
            f"{lifecycle_update.get('unrealized_pnl', 0.0):.2f} | "
            f"Partial P&L: ₹"
            f"{lifecycle_update.get('partial_realized_pnl', 0.0):.2f} | "
            f"Stop: ₹{lifecycle_stop:.2f}"
        )

        # -------------------------
        # Check complete exit
        # -------------------------

        paper_position = (
            trader.get_open_position(
                symbol
            )
        )

        if paper_position is None:
            continue

        exit_signal = str(
            lifecycle_update.get(
                "exit_signal",
                "",
            )
            or ""
        ).strip().upper()

        if not exit_signal:
            if current_price <= float(
                paper_position["stop_loss"]
            ):
                exit_signal = "STOP_LOSS"

            elif current_price >= float(
                paper_position["target"]
            ):
                exit_signal = "TARGET"

        if not exit_signal:
            continue

        remaining_quantity = int(
            paper_position.get(
                "quantity",
                0,
            )
            or 0
        )

        if remaining_quantity <= 0:
            print(
                f"{symbol}: invalid remaining "
                "quantity for full exit."
            )
            continue

        sell_result = execute_paper_sell(
            controller=(
                live_execution_controller
            ),
            symbol=symbol,
            quantity=remaining_quantity,
            price=current_price,
            reason=exit_signal,
            metadata={
                "partial_exit": False,
                "full_exit": True,
            },
        )

        if not sell_result.get(
            "success",
            False,
        ):
            print(
                f"{symbol}: full SELL execution "
                "registration failed."
            )
            continue

        closed_trade = trader.close_trade(
            symbol=symbol,
            exit_price=current_price,
            exit_reason=exit_signal,
        )

        if closed_trade is None:
            print(
                f"{symbol}: paper full exit "
                "failed after SELL registration."
            )
            continue

        if lifecycle.has_open_trade(
            symbol
        ):
            lifecycle.close_trade(
                symbol=symbol,
                exit_price=current_price,
                exit_reason=exit_signal,
            )

        sell_order = (
            sell_result.get(
                "order",
                {},
            )
            or {}
        )

        print(
            f"{symbol}: full SELL registered | "
            f"Reason: {exit_signal} | "
            f"Qty: {remaining_quantity} | "
            f"Status: "
            f"{sell_order.get('status', 'UNKNOWN')} | "
            f"Internal Order ID: "
            f"{sell_order.get('internal_order_id')}"
        )
            

def close_all_positions(
    market: MarketData,
    trader: PaperTrader,
    lifecycle: TradeLifecycle,
    live_execution_controller: LiveExecutionController,
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

        exit_price = float(
            quote["last_price"]
        )

        position = trader.get_open_position(
            symbol
        )

        if position is None:
            continue

        quantity = int(
            position.get(
                "quantity",
                0,
            )
            or 0
        )

        if quantity <= 0:
            print(
                f"{symbol}: invalid quantity "
                "for day-end exit."
            )
            continue

        sell_result = execute_paper_sell(
            controller=(
                live_execution_controller
            ),
            symbol=symbol,
            quantity=quantity,
            price=exit_price,
            reason=reason,
            metadata={
                "full_exit": True,
                "day_end_exit": True,
            },
        )

        if not sell_result.get(
            "success",
            False,
        ):
            print(
                f"{symbol}: day-end SELL "
                "registration failed."
            )
            continue

        closed_trade = trader.close_trade(
            symbol=symbol,
            exit_price=exit_price,
            exit_reason=reason,
        )

        if (
            closed_trade is not None
            and lifecycle.has_open_trade(
                symbol
            )
        ):
            lifecycle.close_trade(
                symbol=symbol,
                exit_price=exit_price,
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


def run_position_synchronization(
    market: MarketData,
    trader: PaperTrader,
    live_execution_controller: LiveExecutionController,
    live_trading: bool,
) -> Dict[str, Any]:
    """
    Compare internal positions with Groww positions.

    In paper mode, broker reconciliation is skipped
    because paper positions do not exist at Groww.
    """
    if not live_trading:
        return {
            "skipped": True,
            "reason": (
                "Position synchronization skipped "
                "because live trading is disabled."
            ),
            "synchronized": True,
            "mismatches": 0,
            "comparisons": [],
        }

    broker_positions = (
        market.get_broker_positions()
    )

    if broker_positions is None:
        return {
            "skipped": False,
            "synchronized": False,
            "mismatches": 0,
            "comparisons": [],
            "reason": (
                "Broker positions could not "
                "be fetched."
            ),
        }

    internal_positions = (
        trader.get_open_positions()
    )

    result = (
        live_execution_controller
        .synchronize_positions(
            internal_positions=(
                internal_positions
            ),
            broker_positions=(
                broker_positions
            ),
        )
    )

    if result.get(
        "synchronized",
        False,
    ):
        print(
            "Position synchronization: "
            "all positions matched."
        )

    else:
        print(
            "Position synchronization "
            f"found {result.get('mismatches', 0)} "
            "mismatch(es)."
        )

        for comparison in result.get(
            "comparisons",
            [],
        ):
            if comparison.get(
                "status"
            ) == "MATCHED":
                continue

            print(
                f"- {comparison.get('symbol', 'UNKNOWN')}: "
                f"{comparison.get('status', 'UNKNOWN')}"
            )

    return result


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

    market_learning = MarketLearning()

    recommendation_engine = (
        RecommendationEngine()
    )

    dynamic_position_sizer = (
        DynamicPositionSizer()
    )

    portfolio_heat_manager = (
        PortfolioHeatManager(
            max_total_risk_percent=2.0,
            max_open_positions=2,
            max_sector_positions=1,
        )
    )

    trader = PaperTrader(
        starting_balance=100000.0,
        log_file="logs/paper_trades.csv",
    )
    
    live_trading_enabled = False

    order_executor = OrderExecutor(
        groww_client=None,
        live_trading=(
            live_trading_enabled
        ),
    )

    order_manager = OrderManager()

    position_sync = PositionSynchronizer()

    live_execution_controller = LiveExecutionController(
        executor=order_executor,
        order_manager=order_manager,
        position_sync=position_sync,
    )

    startup_sync_result = (
        run_position_synchronization(
            market=market,
            trader=trader,
            live_execution_controller=(
                live_execution_controller
            ),
            live_trading=(
                live_trading_enabled
            ),
        )
    )

    if startup_sync_result.get(
        "skipped",
        False,
    ):
        print(
            startup_sync_result.get(
                "reason",
                "Position synchronization skipped.",
            )
        )

    lifecycle = TradeLifecycle()

    for symbol, position in (
        trader.open_positions.items()
    ):
        metadata = position.get(
            "metadata",
            {},
        )

        lifecycle.open_trade(
            symbol=symbol,
            strategy=str(
                metadata.get(
                    "strategy",
                    "UNKNOWN",
                )
            ),
            quantity=int(
                position["quantity"]
            ),
            entry_price=float(
                position["entry_price"]
            ),
            stop_loss=float(
                position["stop_loss"]
            ),
            target=float(
                position["target"]
            ),
            metadata=metadata,
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

    safety_manager = SafetyManager(
        max_trades_per_day=5,
        max_daily_loss=2000.0,
        max_consecutive_losses=3,
        max_api_failures=5,
        max_broker_failures=3,
    )

    latest_scan: List[
        Dict[str, Any]
    ] = []

    last_scan_time = 0.0
    last_position_sync_time = 0.0

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
                lifecycle=lifecycle,
                live_execution_controller=(
                    live_execution_controller
                ),
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
            lifecycle=lifecycle,
            live_execution_controller=(
                live_execution_controller
            ),
        )

        current_timestamp = time.time()

        should_sync_positions = (
            current_timestamp
            - last_position_sync_time
            >= POSITION_SYNC_INTERVAL_SECONDS
        )

        if should_sync_positions:
            sync_result = (
                run_position_synchronization(
                    market=market,
                    trader=trader,
                    live_execution_controller=(
                        live_execution_controller
                    ),
                    live_trading=(
                        live_trading_enabled
                    ),
                )
            )

            if not sync_result.get(
                "skipped",
                False,
            ):
                print(
                    "Runtime position "
                    "synchronization completed."
                )

            last_position_sync_time = (
                current_timestamp
            )

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
                lifecycle=lifecycle,
                risk_manager=risk_manager,
                claude=claude,
                performance_coach=(
                    performance_coach
                ),
                adaptive_filter=(
                    adaptive_filter
                ),
                market_learning=(
                    market_learning
                ),
                recommendation_engine=(
                    recommendation_engine
                ),
                dynamic_position_sizer=(
                    dynamic_position_sizer
                ),
                portfolio_heat_manager=(
                    portfolio_heat_manager
                ),
                live_execution_controller=(
                    live_execution_controller
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
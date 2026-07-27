from dotenv import load_dotenv

load_dotenv()

import json
import time
from datetime import time as clock_time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from market_intelligence.live_snapshot_builder import (
    LiveSnapshotBuilder,
)

from decision.decision_context import (
    DecisionContext,
)

from execution.decision_pipeline import (
    DecisionPipeline,
)

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
from scanner.market_scanner import scan_market
from execution.order_executor import OrderExecutor
from execution.order_manager import OrderManager
from execution.position_sync import PositionSynchronizer
from execution.live_execution_controller import (
    LiveExecutionController,
)
from execution.trade_entry_manager import (
    open_paper_trades,
)

from execution.position_monitor import (
    monitor_positions,
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




def close_all_positions(
    market: MarketData,
    trader: PaperTrader,
    lifecycle: TradeLifecycle,
    live_execution_controller: LiveExecutionController,
    safety_manager: SafetyManager,
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

        if closed_trade is not None:
            safety_manager.record_trade_closed(
                pnl=float(
                    closed_trade.get(
                        "pnl",
                        0.0,
                    )
                    or 0.0
                )
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

    decision_pipeline = DecisionPipeline()

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

        shutdown_decision = (
            safety_manager.should_shutdown(
                current_daily_pnl=(
                    trader.total_realized_pnl()
                )
            )
        )

        if shutdown_decision.get(
            "shutdown",
            False,
        ):
            shutdown_reason = str(
                shutdown_decision.get(
                    "reason",
                    "Safety shutdown.",
                )
            )

            print(
                "SAFETY SHUTDOWN: "
                f"{shutdown_reason}"
            )

            close_all_positions(
                market=market,
                trader=trader,
                lifecycle=lifecycle,
                live_execution_controller=(
                    live_execution_controller
                ),
                safety_manager=(
                    safety_manager
                ),
                reason="SAFETY_SHUTDOWN",
            )

            print(
                "Bot stopped by "
                "SafetyManager."
            )
            break

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
                safety_manager=(
                    safety_manager
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
            safety_manager=(
                safety_manager
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

            print("\n===== SCAN RESULTS =====")
            print(latest_scan)
            print(
                f"Total scan results: {len(latest_scan)}"
            )

            if latest_scan:
                snapshot = LiveSnapshotBuilder.build(
                    latest_scan
                )

                decision_context = DecisionContext.build(
                    scan_results=latest_scan,
                    trader=trader,
                )

                sector_map = decision_context.get(
                    "sector_map",
                    {},
                )

                if sector_map:
                    decision_result = (
                        decision_pipeline.run(
                            snapshot=snapshot.to_dict(),
                            sector_map=sector_map,
                            total_capital=(
                                decision_context[
                                    "total_capital"
                                ]
                            ),
                            prices=decision_context[
                                "prices"
                            ],
                            available_capital=(
                                decision_context[
                                    "total_capital"
                                ]
                            ),
                            current_open_positions=0,
                            maximum_open_positions=3,
                            existing_daily_risk=0.0,
                            existing_portfolio_exposure=(
                                0.0
                            ),
                            existing_sector_exposure={},
                        )
                    )

                    print(
                        "\n===== LIVE DECISION "
                        "PIPELINE ====="
                    )
                    print(
                        decision_result.summary
                    )

                else:
                    print(
                        "\nDecision pipeline skipped: "
                        "sector map is empty."
                    )

            else:
                print(
                    "\nDecision pipeline skipped: "
                    "no valid scan results."
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
                safety_manager=(
                    safety_manager
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
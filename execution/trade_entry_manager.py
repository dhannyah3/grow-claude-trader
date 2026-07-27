from typing import Any, Dict, List

from analytics.adaptive_filter import AdaptiveTradeFilter
from analytics.market_learning import MarketLearning
from analytics.performance_coach import PerformanceCoach
from analytics.recommendation_engine import RecommendationEngine
from core.dynamic_position_sizer import DynamicPositionSizer
from core.paper_trader import PaperTrader
from core.portfolio_heat_manager import PortfolioHeatManager
from core.risk_manager import RiskManager
from core.safety_manager import SafetyManager
from core.trade_lifecycle import TradeLifecycle
from data.market_data import MarketData
from execution.live_execution_controller import (
    LiveExecutionController,
)
from intelligence.market_brain import MarketBrain
from strategies.claude_analyzer import ClaudeAnalyzer

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
    safety_manager: SafetyManager,
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
        safety_decision = (
            safety_manager.can_open_trade(
                current_daily_pnl=(
                    trader.total_realized_pnl()
                )
            )
        )

        if not safety_decision.get(
            "allowed",
            False,
        ):
            print(
                "Safety Manager blocked "
                f"new trades: "
                f"{safety_decision.get('reason', 'Unknown reason')}"
            )
            break

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

        safety_manager.record_trade_opened()

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


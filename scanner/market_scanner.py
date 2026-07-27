import time
from datetime import time as clock_time
from typing import Any, Dict, List, Tuple

import pandas as pd

from analytics.market_regime import MarketRegime
from core.market_clock import now_in_india
from data.market_data import MarketData
from intelligence.market_brain import MarketBrain
from intelligence.market_intelligence import MarketIntelligence
from strategies.factory import StrategyFactory
from strategies.indicators import calculate_indicators
from watchlist import WATCHLIST

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

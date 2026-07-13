from datetime import date, timedelta
from typing import Any, Dict, Optional

from analytics.market_regime import MarketRegime
from data.market_data import MarketData
from intelligence.market_brain import MarketBrain
from strategies.factory import StrategyFactory
from strategies.indicators import calculate_indicators


SYMBOL = "RELIANCE"
ANALYSIS_DATE = date(2026, 7, 10)


def previous_weekday(day: date) -> date:
    previous_day = day - timedelta(days=1)

    while previous_day.weekday() >= 5:
        previous_day -= timedelta(days=1)

    return previous_day


def fetch_day_candles(
    market: MarketData,
    symbol: str,
    trading_day: date,
) -> Optional[Dict[str, Any]]:
    day_text = trading_day.strftime("%Y-%m-%d")

    return market.get_historical_data(
        groww_symbol=f"NSE-{symbol}",
        start_time=f"{day_text} 09:15:00",
        end_time=f"{day_text} 15:30:00",
        interval=market.groww.CANDLE_INTERVAL_MIN_5,
    )


def main() -> None:
    market = MarketData()
    regime_detector = MarketRegime()
    brain = MarketBrain()

    previous_date = previous_weekday(
        ANALYSIS_DATE
    )

    print(
        f"\nFetching {SYMBOL} data for "
        f"{ANALYSIS_DATE}..."
    )

    current_candles = fetch_day_candles(
        market=market,
        symbol=SYMBOL,
        trading_day=ANALYSIS_DATE,
    )

    previous_candles = fetch_day_candles(
        market=market,
        symbol=SYMBOL,
        trading_day=previous_date,
    )

    if (
        not current_candles
        or not current_candles.get("candles")
    ):
        print(
            "No candles returned for the "
            "analysis date."
        )
        return

    if (
        not previous_candles
        or not previous_candles.get("candles")
    ):
        print(
            "No candles returned for the "
            "previous trading date."
        )
        return

    full_dataframe = calculate_indicators(
        current_candles
    )

    previous_dataframe = calculate_indicators(
        previous_candles
    )

    if full_dataframe.empty:
        print(
            "Current-day dataframe is empty."
        )
        return

    if previous_dataframe.empty:
        print(
            "Previous-day dataframe is empty."
        )
        return

    indicator_ready_dataframe = (
        full_dataframe.dropna(
            subset=[
                "ema_20",
                "ema_50",
                "rsi",
                "vwap",
                "atr",
            ]
        )
    )

    if indicator_ready_dataframe.empty:
        print(
            "Not enough candles to calculate "
            "all required indicators."
        )
        return

    latest = (
        indicator_ready_dataframe.iloc[-1]
    )

    first_candle = (
        full_dataframe.iloc[0]
    )

    previous_close = float(
        previous_dataframe.iloc[-1]["close"]
    )

    regime_input = latest.to_dict()

    regime_input["open"] = float(
        first_candle["open"]
    )

    regime = regime_detector.analyze(
        latest=regime_input,
        previous_close=previous_close,
    )

    decision = brain.decide(
        regime_data=regime,
    )

    strategy = StrategyFactory.get(
        decision["recommended_strategy"]
    )

    strategy_signal = strategy.analyze(
        full_dataframe
    )

    print("\n" + "=" * 60)
    print("GROW CLAUDE TRADER — MARKET BRIEF")
    print("=" * 60)

    print(f"Symbol              : {SYMBOL}")
    print(f"Analysis date       : {ANALYSIS_DATE}")
    print(
        f"Previous close      : "
        f"₹{previous_close:.2f}"
    )
    print(
        f"Latest timestamp    : "
        f"{latest['timestamp']}"
    )
    print(
        f"Day open            : "
        f"₹{float(first_candle['open']):.2f}"
    )
    print(
        f"Latest close        : "
        f"₹{float(latest['close']):.2f}"
    )
    print(
        f"EMA 20              : "
        f"{float(latest['ema_20']):.2f}"
    )
    print(
        f"EMA 50              : "
        f"{float(latest['ema_50']):.2f}"
    )
    print(
        f"RSI                 : "
        f"{float(latest['rsi']):.2f}"
    )
    print(
        f"VWAP                : "
        f"{float(latest['vwap']):.2f}"
    )
    print(
        f"ATR                 : "
        f"{float(latest['atr']):.2f}"
    )

    print("\n----- MARKET REGIME -----")

    print(
        f"Trend               : "
        f"{regime['trend']}"
    )
    print(
        f"Trend strength      : "
        f"{regime.get('trend_strength', 'UNKNOWN')}"
    )
    print(
        f"Volatility          : "
        f"{regime['volatility']}"
    )
    print(
        f"Gap                 : "
        f"{regime['gap']}"
    )
    print(
        f"Gap percent         : "
        f"{regime['gap_percent']:.2f}%"
    )
    print(
        f"ATR percent         : "
        f"{regime['atr_percent']:.2f}%"
    )

    print("\n----- MARKET BRAIN -----")

    print(
        f"Should trade        : "
        f"{decision['should_trade']}"
    )
    print(
        f"Recommended strategy: "
        f"{decision['recommended_strategy']}"
    )
    print(
        f"Confidence          : "
        f"{decision['confidence']}%"
    )
    print(
        f"Risk multiplier     : "
        f"{decision['risk_multiplier']}x"
    )

    print("\nReasons:")

    for reason in decision["reasons"]:
        print(f"- {reason}")

    print("\n----- STRATEGY SIGNAL -----")

    print(
        f"Loaded strategy     : "
        f"{type(strategy).__name__}"
    )
    print(
        f"Action              : "
        f"{strategy_signal['action']}"
    )
    print(
        f"Score               : "
        f"{strategy_signal['score']}"
    )
    print(
        f"Reason              : "
        f"{strategy_signal['reason']}"
    )
    print(
        f"Metadata            : "
        f"{strategy_signal['metadata']}"
    )

    print("=" * 60)


if __name__ == "__main__":
    main()

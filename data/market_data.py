from typing import Any, Dict, Optional

from growwapi import GrowwAPI

from config import config
from indicators import calculate_indicators


class MarketData:
    def __init__(self):
        self.groww = GrowwAPI(config.GROWW_ACCESS_TOKEN)

    def get_live_quote(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            return self.groww.get_quote(
                symbol,
                self.groww.EXCHANGE_NSE,
                self.groww.SEGMENT_CASH,
            )
        except Exception as error:
            print(f"Error fetching quote for {symbol}: {error}")
            return None

    def get_historical_data(
        self,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        interval: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            return self.groww.get_historical_candles(
                self.groww.EXCHANGE_NSE,
                self.groww.SEGMENT_CASH,
                groww_symbol,
                start_time,
                end_time,
                interval,
            )
        except Exception as error:
            print(
                f"Error fetching historical data "
                f"for {groww_symbol}: {error}"
            )
            return None


if __name__ == "__main__":
    market = MarketData()

    print("\n===== LIVE QUOTE =====")

    quote = market.get_live_quote("RELIANCE")

    if quote:
        print(f"Price    : ₹{quote.get('last_price')}")
        print(f"Change % : {quote.get('day_change_perc')}")
        print(f"Volume   : {quote.get('volume')}")
    else:
        print("No live quote returned.")

    print("\n===== HISTORICAL CANDLES =====")

    candles = market.get_historical_data(
        groww_symbol="NSE-RELIANCE",
        start_time="2026-07-10 09:15:00",
        end_time="2026-07-10 15:30:00",
        interval=market.groww.CANDLE_INTERVAL_MIN_5,
    )

    if candles:
        dataframe = calculate_indicators(candles)

        if dataframe.empty:
            print("No candle rows available.")
        else:
            latest = dataframe.iloc[-1]

            print("\n===== LATEST INDICATOR VALUES =====\n")

            print(f"Timestamp      : {latest['timestamp']}")
            print(f"Close          : {latest['close']}")
            print(f"EMA 20         : {latest['ema_20']}")
            print(f"EMA 50         : {latest['ema_50']}")
            print(f"RSI            : {latest['rsi']}")
            print(f"VWAP           : {latest['vwap']}")
            print(f"ATR            : {latest['atr']}")
            print(f"MACD           : {latest['macd']}")
            print(f"MACD Signal    : {latest['macd_signal']}")
            print(f"MACD Histogram : {latest['macd_histogram']}")
    else:
        print("No historical candle data returned.")
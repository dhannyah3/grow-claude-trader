from typing import Any, Dict, List, Optional

from growwapi import GrowwAPI

from config import config
from watchlist import WATCHLIST


class MarketScanner:
    def __init__(self):
        self.groww = GrowwAPI(config.GROWW_ACCESS_TOKEN)

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        try:
            quote = self.groww.get_quote(
                symbol,
                self.groww.EXCHANGE_NSE,
                self.groww.SEGMENT_CASH,
            )
            return quote

        except Exception as e:
            print(f"❌ {symbol}: {e}")
            return None

    def scan(self) -> List[Dict[str, Any]]:
        results = []

        for symbol in WATCHLIST:
            quote = self.get_quote(symbol)

            if quote is None:
                continue

            results.append({
                "symbol": symbol,
                "last_price": quote.get("last_price"),
                "day_change": quote.get("day_change"),
                "day_change_perc": quote.get("day_change_perc"),
                "volume": quote.get("volume"),
                "open": quote.get("ohlc", {}).get("open"),
                "high": quote.get("ohlc", {}).get("high"),
                "low": quote.get("ohlc", {}).get("low"),
                "previous_close": quote.get("ohlc", {}).get("close"),
            })

        return results


if __name__ == "__main__":

    scanner = MarketScanner()

    stocks = scanner.scan()

    print("\n==============================")
    print(f"Scanned {len(stocks)} stocks")
    print("==============================\n")

    for stock in stocks:
        print(
            f"{stock['symbol']:12}"
            f" Price: ₹{stock['last_price']:<10}"
            f" Change: {stock['day_change_perc']:.2f}%"
            f" Volume: {stock['volume']}"
        )
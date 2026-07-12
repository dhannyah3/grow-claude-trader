import time
from typing import Any, Dict, List, Optional

from growwapi import GrowwAPI

from config import config
from watchlist import WATCHLIST


CACHE_SECONDS = 180
REQUEST_DELAY_SECONDS = 0.3


class MarketScanner:
    # Shared cache survives new MarketScanner instances
    # during Streamlit reruns.
    _shared_cache: List[Dict[str, Any]] = []
    _shared_cache_time: float = 0.0

    def __init__(self) -> None:
        self.groww = GrowwAPI(config.GROWW_ACCESS_TOKEN)

    def get_quote(
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
            print(f"❌ {symbol}: {error}")
            return None

    def scan(
        self,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        cache_age = (
            time.time()
            - MarketScanner._shared_cache_time
        )

        cache_is_valid = (
            MarketScanner._shared_cache
            and cache_age < CACHE_SECONDS
        )

        if cache_is_valid and not force_refresh:
            return [
                stock.copy()
                for stock in MarketScanner._shared_cache
            ]

        results: List[Dict[str, Any]] = []

        for symbol in WATCHLIST:
            quote = self.get_quote(symbol)

            if quote is not None:
                ohlc = quote.get("ohlc") or {}

                results.append(
                    {
                        "symbol": symbol,
                        "last_price": quote.get("last_price"),
                        "day_change": quote.get("day_change"),
                        "day_change_perc": quote.get(
                            "day_change_perc"
                        ),
                        "volume": quote.get("volume"),
                        "open": ohlc.get("open"),
                        "high": ohlc.get("high"),
                        "low": ohlc.get("low"),
                        "previous_close": ohlc.get("close"),
                    }
                )

            time.sleep(REQUEST_DELAY_SECONDS)

        if results:
            MarketScanner._shared_cache = [
                stock.copy()
                for stock in results
            ]

            MarketScanner._shared_cache_time = (
                time.time()
            )
            self._cache = results
            self._cache_time = time.time()

        return results

    @classmethod
    def clear_cache(cls) -> None:
        cls._shared_cache = []
        cls._shared_cache_time = 0.0


if __name__ == "__main__":
    scanner = MarketScanner()
    stocks = scanner.scan(force_refresh=True)

    print("\n==============================")
    print(f"Scanned {len(stocks)} stocks")
    print("==============================\n")

    for stock in stocks:
        price = stock.get("last_price")
        change = stock.get("day_change_perc")
        volume = stock.get("volume")

        price_text = (
            f"₹{float(price):.2f}"
            if price is not None
            else "N/A"
        )

        change_text = (
            f"{float(change):.2f}%"
            if change is not None
            else "N/A"
        )

        print(
            f"{stock['symbol']:12}"
            f" Price: {price_text:12}"
            f" Change: {change_text:10}"
            f" Volume: {volume}"
        )
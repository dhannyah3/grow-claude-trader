from typing import Any, Dict, List, Optional

from growwapi import GrowwAPI

from config import config
from strategies.indicators import calculate_indicators


class MarketData:
    def __init__(self) -> None:
        self.groww = GrowwAPI(
            config.GROWW_ACCESS_TOKEN
        )

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
            print(
                f"Error fetching quote for "
                f"{symbol}: {error}"
            )
            return None

    def get_historical_data(
        self,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        interval: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            return (
                self.groww
                .get_historical_candles(
                    self.groww.EXCHANGE_NSE,
                    self.groww.SEGMENT_CASH,
                    groww_symbol,
                    start_time,
                    end_time,
                    interval,
                )
            )

        except Exception as error:
            print(
                f"Error fetching historical "
                f"data for {groww_symbol}: "
                f"{error}"
            )
            return None

    def get_broker_positions(
        self,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch and normalize current Groww cash positions.

        This method is read-only. It does not place,
        modify, or close any broker orders.
        """
        try:
            response = (
                self.groww
                .get_positions_for_user(
                    segment=(
                        self.groww
                        .SEGMENT_CASH
                    ),
                )
            )

        except Exception as error:
            print(
                "Error fetching broker "
                f"positions: {error}"
            )
            return None

        if not isinstance(
            response,
            dict,
        ):
            print(
                "Unexpected broker position "
                "response format."
            )
            return None

        raw_positions = response.get(
            "positions",
            [],
        )

        if not isinstance(
            raw_positions,
            list,
        ):
            print(
                "Broker positions field "
                "is not a list."
            )
            return None

        normalized_positions: List[
            Dict[str, Any]
        ] = []

        for position in raw_positions:
            if not isinstance(
                position,
                dict,
            ):
                continue

            symbol = str(
                position.get(
                    "trading_symbol",
                    position.get(
                        "symbol",
                        "",
                    ),
                )
                or ""
            ).strip().upper()

            try:
                quantity = int(
                    position.get(
                        "quantity",
                        position.get(
                            "net_quantity",
                            0,
                        ),
                    )
                    or 0
                )

            except (
                TypeError,
                ValueError,
            ):
                quantity = 0

            try:
                average_price = float(
                    position.get(
                        "average_price",
                        position.get(
                            "buy_average_price",
                            0.0,
                        ),
                    )
                    or 0.0
                )

            except (
                TypeError,
                ValueError,
            ):
                average_price = 0.0

            if (
                not symbol
                or quantity == 0
            ):
                continue

            normalized_positions.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "average_price": (
                        average_price
                    ),
                    "raw": position,
                }
            )

        return normalized_positions


if __name__ == "__main__":
    market = MarketData()

    print("\n===== LIVE QUOTE =====")

    quote = market.get_live_quote(
        "RELIANCE"
    )

    if quote:
        print(
            f"Price    : "
            f"₹{quote.get('last_price')}"
        )
        print(
            f"Change % : "
            f"{quote.get('day_change_perc')}"
        )
        print(
            f"Volume   : "
            f"{quote.get('volume')}"
        )

    else:
        print(
            "No live quote returned."
        )

    print(
        "\n===== HISTORICAL CANDLES ====="
    )

    candles = market.get_historical_data(
        groww_symbol="NSE-RELIANCE",
        start_time=(
            "2026-07-10 09:15:00"
        ),
        end_time=(
            "2026-07-10 15:30:00"
        ),
        interval=(
            market.groww
            .CANDLE_INTERVAL_MIN_5
        ),
    )

    if candles:
        dataframe = (
            calculate_indicators(
                candles
            )
        )

        if dataframe.empty:
            print(
                "No candle rows available."
            )

        else:
            latest = dataframe.iloc[-1]

            print(
                "\n===== LATEST "
                "INDICATOR VALUES =====\n"
            )

            print(
                f"Timestamp      : "
                f"{latest['timestamp']}"
            )
            print(
                f"Close          : "
                f"{latest['close']}"
            )
            print(
                f"EMA 20         : "
                f"{latest['ema_20']}"
            )
            print(
                f"EMA 50         : "
                f"{latest['ema_50']}"
            )
            print(
                f"RSI            : "
                f"{latest['rsi']}"
            )
            print(
                f"VWAP           : "
                f"{latest['vwap']}"
            )
            print(
                f"ATR            : "
                f"{latest['atr']}"
            )
            print(
                f"MACD           : "
                f"{latest['macd']}"
            )
            print(
                f"MACD Signal    : "
                f"{latest['macd_signal']}"
            )
            print(
                f"MACD Histogram : "
                f"{latest['macd_histogram']}"
            )

    else:
        print(
            "No historical candle "
            "data returned."
        )

    print(
        "\n===== BROKER POSITIONS ====="
    )

    broker_positions = (
        market.get_broker_positions()
    )

    if broker_positions is None:
        print(
            "Broker positions "
            "could not be fetched."
        )

    elif not broker_positions:
        print(
            "No broker positions."
        )

    else:
        for position in (
            broker_positions
        ):
            print(
                f"{position['symbol']} | "
                f"Qty: "
                f"{position['quantity']} | "
                f"Average Price: "
                f"₹{position['average_price']:.2f}"
            )
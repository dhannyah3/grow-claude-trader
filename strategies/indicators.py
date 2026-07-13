from typing import Optional

import pandas as pd


def candles_to_dataframe(
    candles_response: dict,
) -> pd.DataFrame:
    """
    Convert Groww candles into a clean DataFrame.

    Supported formats:

    6 values:
    timestamp, open, high, low, close, volume

    7 values:
    timestamp, open, high, low, close, volume,
    open_interest
    """

    if not isinstance(candles_response, dict):
        return pd.DataFrame()

    candles = candles_response.get(
        "candles",
        [],
    )

    if not candles:
        return pd.DataFrame()

    normalized_candles = []

    for candle in candles:
        if not isinstance(
            candle,
            (list, tuple),
        ):
            print(
                "Skipping invalid candle: "
                f"{candle}"
            )
            continue

        if len(candle) == 6:
            normalized_candles.append(
                list(candle) + [None]
            )

        elif len(candle) >= 7:
            normalized_candles.append(
                list(candle[:7])
            )

        else:
            print(
                "Skipping incomplete candle "
                f"with {len(candle)} values: "
                f"{candle}"
            )

    if not normalized_candles:
        return pd.DataFrame()

    dataframe = pd.DataFrame(
        normalized_candles,
        columns=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_interest",
        ],
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        errors="coerce",
    )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_interest",
    ]

    for column in numeric_columns:
        dataframe[column] = pd.to_numeric(
            dataframe[column],
            errors="coerce",
        )

    dataframe = dataframe.dropna(
        subset=[
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    )

    dataframe = (
        dataframe
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    return dataframe


def add_ema(
    dataframe: pd.DataFrame,
    period: int,
    column_name: Optional[str] = None,
) -> pd.DataFrame:
    name = column_name or f"ema_{period}"

    dataframe[name] = dataframe["close"].ewm(
        span=period,
        adjust=False,
    ).mean()

    return dataframe


def add_rsi(
    dataframe: pd.DataFrame,
    period: int = 14,
) -> pd.DataFrame:
    change = dataframe["close"].diff()

    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    relative_strength = (
        average_gain / average_loss
    )

    dataframe["rsi"] = 100 - (
        100 / (1 + relative_strength)
    )

    return dataframe


def add_vwap(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    typical_price = (
        dataframe["high"]
        + dataframe["low"]
        + dataframe["close"]
    ) / 3

    cumulative_value = (
        typical_price
        * dataframe["volume"]
    ).cumsum()

    cumulative_volume = (
        dataframe["volume"].cumsum()
    )

    dataframe["vwap"] = (
        cumulative_value
        / cumulative_volume.replace(0, pd.NA)
    )

    return dataframe


def add_atr(
    dataframe: pd.DataFrame,
    period: int = 14,
) -> pd.DataFrame:
    previous_close = (
        dataframe["close"].shift(1)
    )

    high_low = (
        dataframe["high"]
        - dataframe["low"]
    )

    high_close = (
        dataframe["high"]
        - previous_close
    ).abs()

    low_close = (
        dataframe["low"]
        - previous_close
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close,
        ],
        axis=1,
    ).max(axis=1)

    dataframe["atr"] = true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    return dataframe


def add_macd(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    ema_12 = dataframe["close"].ewm(
        span=12,
        adjust=False,
    ).mean()

    ema_26 = dataframe["close"].ewm(
        span=26,
        adjust=False,
    ).mean()

    dataframe["macd"] = (
        ema_12 - ema_26
    )

    dataframe["macd_signal"] = (
        dataframe["macd"].ewm(
            span=9,
            adjust=False,
        ).mean()
    )

    dataframe["macd_histogram"] = (
        dataframe["macd"]
        - dataframe["macd_signal"]
    )

    return dataframe


def calculate_indicators(
    candles_response: dict,
) -> pd.DataFrame:
    dataframe = candles_to_dataframe(
        candles_response
    )

    if dataframe.empty:
        return dataframe

    dataframe = add_ema(
        dataframe,
        20,
    )

    dataframe = add_ema(
        dataframe,
        50,
    )

    dataframe = add_rsi(
        dataframe,
    )

    dataframe = add_vwap(
        dataframe,
    )

    dataframe = add_atr(
        dataframe,
    )

    dataframe = add_macd(
        dataframe,
    )

    return dataframe

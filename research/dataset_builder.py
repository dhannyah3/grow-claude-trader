"""
Dataset Builder

Loads historical data, calculates technical indicators,
adds research features, and returns a clean dataset.
"""

from typing import Optional

import pandas as pd

from research.historical_data_manager import (
    HistoricalDataManager,
)
from strategies.indicators import (
    calculate_indicators,
)


class DatasetBuilder:
    def __init__(
        self,
        historical_manager: Optional[
            HistoricalDataManager
        ] = None,
    ) -> None:
        self.historical = (
            historical_manager
            or HistoricalDataManager()
        )

    def build_dataset(
        self,
        symbol: str,
        interval_name: str,
        year: int,
    ) -> pd.DataFrame:
        dataframe = self.historical.load(
            symbol=symbol,
            interval_name=interval_name,
            year=year,
        )

        if dataframe.empty:
            print("No historical data found.")
            return dataframe

        dataframe = self._prepare_timestamp(
            dataframe
        )

        indicator_input = {
            "candles": dataframe[
                [
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            ].values.tolist()
        }

        dataframe = calculate_indicators(
            indicator_input
        )

        if dataframe.empty:
            print(
                "Indicator calculation "
                "returned no rows."
            )
            return dataframe

        dataframe = self._prepare_timestamp(
            dataframe
        )

        dataframe = self._add_features(
            dataframe
        )

        return dataframe

    def _prepare_timestamp(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        df = dataframe.copy()

        if "timestamp" not in df.columns:
            raise ValueError(
                "Dataset does not contain "
                "a timestamp column."
            )

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        df = df.dropna(
            subset=["timestamp"]
        )

        df = df.sort_values(
            "timestamp"
        )

        df = df.reset_index(
            drop=True
        )

        return df

    def _add_features(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        df = dataframe.copy()

        df["day_of_week"] = (
            df["timestamp"].dt.day_name()
        )

        df["day_of_week_number"] = (
            df["timestamp"].dt.dayofweek
        )

        df["month"] = (
            df["timestamp"].dt.month
        )

        df["hour"] = (
            df["timestamp"].dt.hour
        )

        df["minute"] = (
            df["timestamp"].dt.minute
        )

        df["time_minutes"] = (
            df["hour"] * 60
            + df["minute"]
        )

        df["ema_distance"] = (
            (
                df["close"]
                - df["ema_20"]
            )
            / df["ema_20"]
        ) * 100

        df["ema_trend_distance"] = (
            (
                df["ema_20"]
                - df["ema_50"]
            )
            / df["ema_50"]
        ) * 100

        df["vwap_distance"] = (
            (
                df["close"]
                - df["vwap"]
            )
            / df["vwap"]
        ) * 100

        df["atr_percent"] = (
            df["atr"]
            / df["close"]
        ) * 100

        rolling_volume = (
            df["volume"]
            .rolling(
                window=20,
                min_periods=1,
            )
            .mean()
        )

        df["volume_ratio"] = (
            df["volume"]
            / rolling_volume.replace(
                0,
                pd.NA,
            )
        )

        df["candle_range"] = (
            df["high"]
            - df["low"]
        )

        df["candle_range_percent"] = (
            df["candle_range"]
            / df["close"]
        ) * 100

        df["candle_body"] = (
            df["close"]
            - df["open"]
        )

        df["candle_body_percent"] = (
            df["candle_body"]
            / df["open"]
        ) * 100

        df["bullish_candle"] = (
            df["close"]
            > df["open"]
        ).astype(int)

        df = df.replace(
            [float("inf"), float("-inf")],
            pd.NA,
        )

        return df

    def save_dataset(
        self,
        dataframe: pd.DataFrame,
        symbol: str,
        interval_name: str,
        year: int,
    ) -> str:
        if dataframe.empty:
            raise ValueError(
                "Cannot save an empty dataset."
            )

        output_directory = (
            self.historical.base_directory
            / str(symbol).strip().upper()
            / str(interval_name)
        )

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_file = (
            output_directory
            / f"{int(year)}_features.csv"
        )

        dataframe.to_csv(
            output_file,
            index=False,
        )

        return str(output_file)


if __name__ == "__main__":
    builder = DatasetBuilder()

    dataset = builder.build_dataset(
        symbol="RELIANCE",
        interval_name="5m",
        year=2026,
    )

    print()
    print("=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)

    if dataset.empty:
        print("Dataset is empty.")

    else:
        print(dataset.tail())

        print()
        print("Rows:", len(dataset))
        print("Columns:")

        for column in dataset.columns:
            print("-", column)

        saved_file = builder.save_dataset(
            dataframe=dataset,
            symbol="RELIANCE",
            interval_name="5m",
            year=2026,
        )

        print()
        print(
            "Feature dataset saved to:",
            saved_file,
        )
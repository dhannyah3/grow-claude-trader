"""
Historical data manager for research and backtesting.

Responsibilities:
- download historical Groww candles;
- normalize candle data;
- save data by symbol, interval, and year;
- avoid duplicate rows;
- reload saved datasets.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from data.market_data import MarketData


class HistoricalDataManager:
    def __init__(
        self,
        market: Optional[MarketData] = None,
        base_directory: str = "data/historical/NSE",
    ) -> None:
        self.market = market or MarketData()

        self.base_directory = Path(
            base_directory
        )

        self.base_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def download(
        self,
        symbol: str,
        start_time: str,
        end_time: str,
        interval: str,
        interval_name: str,
    ) -> pd.DataFrame:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        response = self.market.get_historical_data(
            groww_symbol=(
                f"NSE-{normalized_symbol}"
            ),
            start_time=start_time,
            end_time=end_time,
            interval=interval,
        )

        dataframe = self._response_to_dataframe(
            response
        )

        if dataframe.empty:
            print(
                f"{normalized_symbol}: "
                "no historical rows downloaded."
            )
            return dataframe

        dataframe = self._clean_dataframe(
            dataframe
        )

        self.save_by_year(
            symbol=normalized_symbol,
            interval_name=interval_name,
            dataframe=dataframe,
        )

        print(
            f"{normalized_symbol}: "
            f"{len(dataframe)} rows downloaded."
        )

        return dataframe

    def save_by_year(
        self,
        symbol: str,
        interval_name: str,
        dataframe: pd.DataFrame,
    ) -> List[Path]:
        if dataframe.empty:
            return []

        normalized_symbol = self._normalize_symbol(
            symbol
        )

        destination = (
            self.base_directory
            / normalized_symbol
            / str(interval_name)
        )

        destination.mkdir(
            parents=True,
            exist_ok=True,
        )

        working = dataframe.copy()

        working["year"] = (
            working["timestamp"].dt.year
        )

        saved_files: List[Path] = []

        for year, year_data in (
            working.groupby("year")
        ):
            output_file = (
                destination
                / f"{int(year)}.csv"
            )

            year_data = (
                year_data.drop(
                    columns=["year"]
                )
            )

            if output_file.exists():
                existing = pd.read_csv(
                    output_file
                )

                existing[
                    "timestamp"
                ] = pd.to_datetime(
                    existing["timestamp"],
                    errors="coerce",
                )

                combined = pd.concat(
                    [
                        existing,
                        year_data,
                    ],
                    ignore_index=True,
                )

            else:
                combined = year_data

            combined = (
                self._clean_dataframe(
                    combined
                )
            )

            combined.to_csv(
                output_file,
                index=False,
            )

            saved_files.append(
                output_file
            )

            print(
                f"Saved {len(combined)} rows "
                f"to {output_file}"
            )

        return saved_files

    def load(
        self,
        symbol: str,
        interval_name: str,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        directory = (
            self.base_directory
            / normalized_symbol
            / str(interval_name)
        )

        if not directory.exists():
            return pd.DataFrame()

        if year is not None:
            files = [
                directory / f"{int(year)}.csv"
            ]

        else:
            files = sorted(
                directory.glob("*.csv")
            )

        dataframes: List[
            pd.DataFrame
        ] = []

        for file_path in files:
            if not file_path.exists():
                continue

            dataframe = pd.read_csv(
                file_path
            )

            dataframes.append(
                dataframe
            )

        if not dataframes:
            return pd.DataFrame()

        combined = pd.concat(
            dataframes,
            ignore_index=True,
        )

        return self._clean_dataframe(
            combined
        )

    def _response_to_dataframe(
        self,
        response: Optional[
            Dict[str, Any]
        ],
    ) -> pd.DataFrame:
        if not response:
            return pd.DataFrame()

        candles = response.get(
            "candles",
            []
        )

        if not isinstance(
            candles,
            list,
        ):
            return pd.DataFrame()

        if not candles:
            return pd.DataFrame()

        first_row = candles[0]

        if isinstance(
            first_row,
            dict,
        ):
            dataframe = pd.DataFrame(
                candles
            )

        else:
            column_count = len(
                first_row
            )

            possible_columns = {
                6: [
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ],
                7: [
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "open_interest",
                ],
            }

            columns = possible_columns.get(
                column_count
            )

            if columns is None:
                raise ValueError(
                    "Unsupported Groww candle "
                    f"format with {column_count} fields."
                )

            dataframe = pd.DataFrame(
                candles,
                columns=columns,
            )

        return dataframe

    def _clean_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        if dataframe.empty:
            return dataframe.copy()

        cleaned = dataframe.copy()

        cleaned["timestamp"] = (
            pd.to_datetime(
                cleaned["timestamp"],
                errors="coerce",
            )
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
            if column not in cleaned.columns:
                continue

            cleaned[column] = pd.to_numeric(
                cleaned[column],
                errors="coerce",
            )

        required_columns = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]

        available_required = [
            column
            for column in required_columns
            if column in cleaned.columns
        ]

        cleaned = cleaned.dropna(
            subset=available_required
        )

        cleaned = cleaned.drop_duplicates(
            subset=["timestamp"],
            keep="last",
        )

        cleaned = cleaned.sort_values(
            "timestamp"
        )

        cleaned = cleaned.reset_index(
            drop=True
        )

        return cleaned

    def _normalize_symbol(
        self,
        symbol: str,
    ) -> str:
        return str(
            symbol
        ).strip().upper()


if __name__ == "__main__":
    manager = HistoricalDataManager()

    dataframe = manager.download(
        symbol="RELIANCE",
        start_time="2026-07-14 09:15:00",
        end_time="2026-07-14 15:30:00",
        interval=(
            manager.market.groww
            .CANDLE_INTERVAL_MIN_5
        ),
        interval_name="5m",
    )

    print(
        "\nDownloaded rows:",
        len(dataframe),
    )

    restored = manager.load(
        symbol="RELIANCE",
        interval_name="5m",
        year=2026,
    )

    print(
        "Restored rows:",
        len(restored),
    )
"""
Multi-Year Historical Downloader

Downloads 5-minute historical data month by month,
merges it into yearly CSV files, skips completed months,
retries failures, and prints a summary.

Start with one symbol and one year before scaling up.
"""

import calendar
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from research.historical_data_manager import (
    HistoricalDataManager,
)


DEFAULT_SYMBOLS: List[str] = [
    "RELIANCE",
]

DEFAULT_YEARS: List[int] = [
    2025,
]

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
REQUEST_DELAY_SECONDS = 1.5


class MultiYearDownloader:
    def __init__(
        self,
        manager: Optional[
            HistoricalDataManager
        ] = None,
        interval_name: str = "5m",
    ) -> None:
        self.manager = (
            manager
            or HistoricalDataManager()
        )

        self.interval_name = str(
            interval_name
        )

        self.interval = (
            self.manager.market.groww
            .CANDLE_INTERVAL_MIN_5
        )

        self.summary: Dict[
            str,
            Any,
        ] = {
            "symbols_requested": 0,
            "years_requested": 0,
            "months_requested": 0,
            "months_downloaded": 0,
            "months_skipped": 0,
            "months_failed": 0,
            "rows_downloaded": 0,
            "files_updated": 0,
            "failures": [],
        }

    def download_many(
        self,
        symbols: List[str],
        years: List[int],
    ) -> Dict[str, Any]:
        started_at = time.time()

        normalized_symbols = [
            self._normalize_symbol(
                symbol
            )
            for symbol in symbols
            if str(symbol).strip()
        ]

        normalized_years = sorted(
            {
                int(year)
                for year in years
            }
        )

        self.summary[
            "symbols_requested"
        ] = len(
            normalized_symbols
        )

        self.summary[
            "years_requested"
        ] = (
            len(normalized_symbols)
            * len(normalized_years)
        )

        for symbol in (
            normalized_symbols
        ):
            for year in (
                normalized_years
            ):
                self.download_year(
                    symbol=symbol,
                    year=year,
                )

        self.summary[
            "elapsed_seconds"
        ] = round(
            time.time()
            - started_at,
            2,
        )

        return dict(
            self.summary
        )

    def download_year(
        self,
        symbol: str,
        year: int,
    ) -> None:
        symbol = self._normalize_symbol(
            symbol
        )

        year = int(year)

        print()
        print("=" * 60)
        print(
            f"Downloading {symbol} "
            f"for {year}"
        )
        print("=" * 60)

        for month in range(
            1,
            13,
        ):
            self.summary[
                "months_requested"
            ] += 1

            if self._month_already_complete(
                symbol=symbol,
                year=year,
                month=month,
            ):
                self.summary[
                    "months_skipped"
                ] += 1

                print(
                    f"{symbol} {year}-{month:02d}: "
                    "already downloaded, skipping."
                )
                continue

            dataframe = (
                self._download_month_with_retry(
                    symbol=symbol,
                    year=year,
                    month=month,
                )
            )

            if dataframe is None:
                self.summary[
                    "months_failed"
                ] += 1

                self.summary[
                    "failures"
                ].append(
                    {
                        "symbol": symbol,
                        "year": year,
                        "month": month,
                    }
                )
                continue

            if dataframe.empty:
                print(
                    f"{symbol} {year}-{month:02d}: "
                    "no rows returned."
                )
                continue

            saved_files = (
                self.manager.save_by_year(
                    symbol=symbol,
                    interval_name=(
                        self.interval_name
                    ),
                    dataframe=dataframe,
                )
            )

            self.summary[
                "months_downloaded"
            ] += 1

            self.summary[
                "rows_downloaded"
            ] += len(
                dataframe
            )

            self.summary[
                "files_updated"
            ] += len(
                saved_files
            )

            print(
                f"{symbol} {year}-{month:02d}: "
                f"{len(dataframe)} rows saved."
            )

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

    def _download_month_with_retry(
        self,
        symbol: str,
        year: int,
        month: int,
    ) -> Optional[
        pd.DataFrame
    ]:
        start_time, end_time = (
            self._month_range(
                year=year,
                month=month,
            )
        )

        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):
            print(
                f"{symbol} {year}-{month:02d}: "
                f"attempt {attempt}/"
                f"{MAX_RETRIES}"
            )

            response = (
                self.manager.market
                .get_historical_data(
                    groww_symbol=(
                        f"NSE-{symbol}"
                    ),
                    start_time=start_time,
                    end_time=end_time,
                    interval=self.interval,
                )
            )

            if response:
                dataframe = (
                    self.manager
                    ._response_to_dataframe(
                        response
                    )
                )

                if not dataframe.empty:
                    return (
                        self.manager
                        ._clean_dataframe(
                            dataframe
                        )
                    )

                return pd.DataFrame()

            if attempt < MAX_RETRIES:
                print(
                    f"{symbol} {year}-{month:02d}: "
                    f"retrying in "
                    f"{RETRY_DELAY_SECONDS} seconds."
                )

                time.sleep(
                    RETRY_DELAY_SECONDS
                )

        print(
            f"{symbol} {year}-{month:02d}: "
            "download failed."
        )

        return None

    def _month_already_complete(
        self,
        symbol: str,
        year: int,
        month: int,
    ) -> bool:
        dataframe = self.manager.load(
            symbol=symbol,
            interval_name=(
                self.interval_name
            ),
            year=year,
        )

        if dataframe.empty:
            return False

        timestamps = pd.to_datetime(
            dataframe["timestamp"],
            errors="coerce",
        )

        month_rows = dataframe[
            (
                timestamps.dt.year
                == int(year)
            )
            & (
                timestamps.dt.month
                == int(month)
            )
        ]

        return not month_rows.empty

    def _month_range(
        self,
        year: int,
        month: int,
    ) -> Tuple[str, str]:
        last_day = calendar.monthrange(
            int(year),
            int(month),
        )[1]

        start = datetime(
            int(year),
            int(month),
            1,
            9,
            15,
            0,
        )

        end = datetime(
            int(year),
            int(month),
            last_day,
            15,
            30,
            0,
        )

        return (
            start.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            end.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )

    def _normalize_symbol(
        self,
        symbol: str,
    ) -> str:
        return str(
            symbol
        ).strip().upper()

    def print_summary(
        self,
    ) -> None:
        print()
        print("=" * 60)
        print("DOWNLOAD SUMMARY")
        print("=" * 60)

        print(
            "Symbols requested :",
            self.summary.get(
                "symbols_requested",
                0,
            ),
        )

        print(
            "Symbol-years      :",
            self.summary.get(
                "years_requested",
                0,
            ),
        )

        print(
            "Months requested  :",
            self.summary.get(
                "months_requested",
                0,
            ),
        )

        print(
            "Months downloaded :",
            self.summary.get(
                "months_downloaded",
                0,
            ),
        )

        print(
            "Months skipped    :",
            self.summary.get(
                "months_skipped",
                0,
            ),
        )

        print(
            "Months failed     :",
            self.summary.get(
                "months_failed",
                0,
            ),
        )

        print(
            "Rows downloaded   :",
            self.summary.get(
                "rows_downloaded",
                0,
            ),
        )

        print(
            "Files updated     :",
            self.summary.get(
                "files_updated",
                0,
            ),
        )

        print(
            "Elapsed seconds   :",
            self.summary.get(
                "elapsed_seconds",
                0.0,
            ),
        )

        failures = self.summary.get(
            "failures",
            [],
        )

        if failures:
            print()
            print("Failures:")

            for failure in failures:
                print(
                    "- "
                    f"{failure['symbol']} "
                    f"{failure['year']}-"
                    f"{failure['month']:02d}"
                )


if __name__ == "__main__":
    downloader = MultiYearDownloader()

    downloader.download_many(
        symbols=DEFAULT_SYMBOLS,
        years=DEFAULT_YEARS,
    )

    downloader.print_summary()

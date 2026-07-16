"""
Base Strategy Interface

Every research strategy should inherit from BaseStrategy
and implement the methods below.

The shared evaluator will handle:

- data iteration;
- entry and exit execution;
- slippage;
- costs;
- position sizing;
- dynamic balance;
- trade statistics;
- drawdown;
- reporting.

Each strategy only defines its own trading rules.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract interface for research strategies.
    """

    name: str = "BASE_STRATEGY"

    def __init__(
        self,
        entry_start_time: str = "09:30",
        entry_cutoff_time: str = "15:10",
        force_exit_time: str = "15:20",
    ) -> None:
        self.entry_start_time = pd.Timestamp(
            entry_start_time
        ).time()

        self.entry_cutoff_time = pd.Timestamp(
            entry_cutoff_time
        ).time()

        self.force_exit_time = pd.Timestamp(
            force_exit_time
        ).time()

        if not (
            self.entry_start_time
            < self.entry_cutoff_time
            <= self.force_exit_time
        ):
            raise ValueError(
                "Trading times must satisfy: "
                "entry start < entry cutoff <= force exit."
            )

    @abstractmethod
    def required_columns(
        self,
    ) -> set:
        """
        Return all dataframe columns required by the strategy.
        """
        raise NotImplementedError

    @abstractmethod
    def should_enter(
        self,
        row_index: int,
        row: pd.Series,
        day_data: pd.DataFrame,
    ) -> bool:
        """
        Return True when the current candle satisfies
        the strategy's entry conditions.
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_stop_loss(
        self,
        row: pd.Series,
        entry_price: float,
    ) -> float:
        """
        Calculate the initial stop-loss price.
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_target(
        self,
        row: pd.Series,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        """
        Calculate the initial target price.
        """
        raise NotImplementedError

    def should_force_exit(
        self,
        row: pd.Series,
    ) -> bool:
        """
        Return True when the position must be closed
        because the intraday force-exit time was reached.
        """
        current_time = (
            row["timestamp"].time()
        )

        return (
            current_time
            >= self.force_exit_time
        )

    def additional_trade_metadata(
        self,
        row: pd.Series,
    ) -> Dict[str, Any]:
        """
        Optional strategy-specific metadata saved with a trade.
        """
        return {
            "strategy": self.name,
        }

    def validate_dataframe(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Validate that the supplied dataset contains all columns
        required by this strategy.
        """
        missing = self.required_columns().difference(
            dataframe.columns
        )

        if missing:
            raise ValueError(
                "Dataset is missing columns: "
                + ", ".join(
                    sorted(missing)
                )
            )

    def can_open_new_position(
        self,
        row: pd.Series,
    ) -> bool:
        """
        Return True only during the permitted entry window.
        """
        current_time = (
            row["timestamp"].time()
        )

        return (
            self.entry_start_time
            <= current_time
            <= self.entry_cutoff_time
        )

    def get_exit_signal(
        self,
        row: pd.Series,
        position: Dict[str, Any],
    ) -> Optional[
        Dict[str, Any]
    ]:
        """
        Default stop, target, and forced-exit handling.

        Conservative assumption:
        if stop and target are both touched in one candle,
        the stop is counted first.
        """
        low = float(
            row["low"]
        )

        high = float(
            row["high"]
        )

        stop_loss = float(
            position["stop_loss"]
        )

        target = float(
            position["target"]
        )

        if low <= stop_loss:
            return {
                "raw_exit_price": (
                    stop_loss
                ),
                "exit_reason": (
                    "STOP_LOSS"
                ),
            }

        if high >= target:
            return {
                "raw_exit_price": (
                    target
                ),
                "exit_reason": (
                    "TARGET"
                ),
            }

        if self.should_force_exit(
            row
        ):
            return {
                "raw_exit_price": float(
                    row["close"]
                ),
                "exit_reason": (
                    "DAY_END_EXIT"
                ),
            }

        return None
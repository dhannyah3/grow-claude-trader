from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd


class BaseStrategy(ABC):
    """
    Common interface for every trading strategy.

    Each strategy must:
    - have a unique name;
    - analyze a prepared indicator dataframe;
    - return a consistent signal dictionary.
    """

    name = "BASE_STRATEGY"

    @abstractmethod
    def analyze(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Analyze market data and return a trade signal.

        Expected response format:

        {
            "strategy": "STRATEGY_NAME",
            "action": "BUY" | "SELL" | "WAIT",
            "score": 0,
            "entry_price": None,
            "stop_loss": None,
            "target": None,
            "reason": "",
            "metadata": {},
        }
        """

        raise NotImplementedError

    def wait_signal(
        self,
        reason: str,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Return a standard WAIT response.
        """

        return {
            "strategy": self.name,
            "action": "WAIT",
            "score": 0,
            "entry_price": None,
            "stop_loss": None,
            "target": None,
            "reason": reason,
            "metadata": metadata or {},
        }

    def trade_signal(
        self,
        action: str,
        score: int,
        entry_price: float,
        stop_loss: float,
        target: float,
        reason: str,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Return a standardized BUY or SELL signal.
        """

        normalized_action = action.upper()

        if normalized_action not in {
            "BUY",
            "SELL",
        }:
            raise ValueError(
                "Trade action must be BUY or SELL."
            )

        return {
            "strategy": self.name,
            "action": normalized_action,
            "score": int(score),
            "entry_price": round(
                float(entry_price),
                2,
            ),
            "stop_loss": round(
                float(stop_loss),
                2,
            ),
            "target": round(
                float(target),
                2,
            ),
            "reason": reason,
            "metadata": metadata or {},
        }
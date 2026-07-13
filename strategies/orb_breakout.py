from typing import Any, Dict

import pandas as pd

from strategies.base_strategy import BaseStrategy


class ORBBreakoutStrategy(BaseStrategy):
    """
    Opening Range Breakout strategy.
    """

    name = "ORB_BREAKOUT"

    def analyze(
        self,
        dataframe: pd.DataFrame,
    ) -> Dict[str, Any]:

        if dataframe.empty:
            return self.wait_signal(
                "No market data."
            )

        opening = dataframe[
            (
                dataframe["timestamp"].dt.time
                >= pd.Timestamp("09:15").time()
            )
            &
            (
                dataframe["timestamp"].dt.time
                < pd.Timestamp("09:30").time()
            )
        ]

        if opening.empty:
            return self.wait_signal(
                "Opening range unavailable."
            )

        opening_high = float(
            opening["high"].max()
        )

        latest = dataframe.iloc[-1]

        if latest["close"] <= opening_high:
            return self.wait_signal(
                "No breakout yet."
            )

        stop_loss = float(
            opening["low"].min()
        )

        risk = (
            latest["close"]
            - stop_loss
        )

        if risk <= 0:
            return self.wait_signal(
                "Invalid risk."
            )

        target = (
            latest["close"]
            + risk * 2
        )

        return self.trade_signal(
            action="BUY",
            score=85,
            entry_price=float(
                latest["close"]
            ),
            stop_loss=stop_loss,
            target=target,
            reason="ORB breakout confirmed.",
            metadata={
                "opening_high": opening_high,
            },
        )
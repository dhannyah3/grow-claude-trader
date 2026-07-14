"""
Market Learning Engine

Version 3

This module analyzes completed trades and
builds statistics that will eventually allow
the trading bot to improve itself.

Current version supports:

- Loading completed trades
- Grouping trades by strategy
- Grouping trades by market condition
- Counting trades
- Calculating win rate
- Calculating total and average P&L
- Calculating average wins and losses
- Calculating expectancy
- Calculating profit factor
- Calculating average R multiple
- Calculating average holding time

Future versions will add:

- Strategy + regime statistics
- Sample-size confidence
- MFE and MAE analysis
- ATR performance
- Regime-aware learning
- Profile optimization
"""

from collections import defaultdict
from typing import Any, DefaultDict, Dict, List


class MarketLearning:
    def __init__(self) -> None:
        self.strategy_stats: DefaultDict[
            str,
            List[Dict[str, Any]],
        ] = defaultdict(list)

        self.market_stats: DefaultDict[
            str,
            List[Dict[str, Any]],
        ] = defaultdict(list)

    def add_trade(
        self,
        trade: Dict[str, Any],
    ) -> None:
        if not isinstance(trade, dict):
            return

        strategy = str(
            trade.get(
                "strategy",
                "UNKNOWN",
            )
        ).strip().upper()

        market_condition = str(
            trade.get(
                "market_condition",
                "UNKNOWN",
            )
        ).strip().upper()

        self.strategy_stats[strategy].append(
            trade
        )

        self.market_stats[
            market_condition
        ].append(
            trade
        )

    def load_trades(
        self,
        trades: List[
            Dict[str, Any]
        ],
    ) -> None:
        self.strategy_stats.clear()
        self.market_stats.clear()

        if not isinstance(trades, list):
            return

        for trade in trades:
            self.add_trade(trade)

    def strategies(
        self,
    ) -> List[str]:
        return sorted(
            self.strategy_stats.keys()
        )

    def markets(
        self,
    ) -> List[str]:
        return sorted(
            self.market_stats.keys()
        )

    def strategy_trade_count(
        self,
        strategy: str,
    ) -> int:
        normalized_strategy = str(
            strategy
        ).strip().upper()

        return len(
            self.strategy_stats.get(
                normalized_strategy,
                [],
            )
        )

    def market_trade_count(
        self,
        market_condition: str,
    ) -> int:
        normalized_market = str(
            market_condition
        ).strip().upper()

        return len(
            self.market_stats.get(
                normalized_market,
                [],
            )
        )

    def summary(
        self,
    ) -> Dict[str, Any]:
        return {
            "strategies": {
                strategy: len(trades)
                for strategy, trades
                in self.strategy_stats.items()
            },
            "markets": {
                market: len(trades)
                for market, trades
                in self.market_stats.items()
            },
            "total_trades": sum(
                len(trades)
                for trades
                in self.strategy_stats.values()
            ),
        }

    def strategy_statistics(
        self,
        strategy: str,
    ) -> Dict[str, Any]:
        normalized_strategy = str(
            strategy
        ).strip().upper()

        trades = self.strategy_stats.get(
            normalized_strategy,
            [],
        )

        if not trades:
            return {}

        pnl_values = [
            self._to_float(
                trade.get(
                    "pnl",
                    0.0,
                )
            )
            for trade in trades
        ]

        r_values = [
            self._to_float(
                trade.get(
                    "r_multiple",
                    0.0,
                )
            )
            for trade in trades
        ]

        holding_minutes = [
            self._to_float(
                trade.get(
                    "holding_minutes",
                    0.0,
                )
            )
            for trade in trades
        ]

        wins = [
            pnl
            for pnl in pnl_values
            if pnl > 0
        ]

        losses = [
            pnl
            for pnl in pnl_values
            if pnl < 0
        ]

        breakeven = [
            pnl
            for pnl in pnl_values
            if pnl == 0
        ]

        total_trades = len(pnl_values)
        total_pnl = sum(pnl_values)

        average_pnl = (
            total_pnl / total_trades
            if total_trades
            else 0.0
        )

        average_win = self._average(wins)
        average_loss = self._average(losses)
        average_r = self._average(r_values)
        average_hold_minutes = (
            self._average(
                holding_minutes
            )
        )

        win_rate = (
            len(wins)
            / total_trades
            * 100
            if total_trades
            else 0.0
        )

        loss_rate = (
            len(losses)
            / total_trades
            * 100
            if total_trades
            else 0.0
        )

        breakeven_rate = (
            len(breakeven)
            / total_trades
            * 100
            if total_trades
            else 0.0
        )

        expectancy = (
            (
                win_rate
                / 100
            )
            * average_win
        ) + (
            (
                loss_rate
                / 100
            )
            * average_loss
        )

        gross_profit = sum(wins)
        gross_loss = abs(
            sum(losses)
        )

        if gross_loss == 0:
            profit_factor: Any = (
                "Infinity"
                if gross_profit > 0
                else 0.0
            )
        else:
            profit_factor = (
                gross_profit
                / gross_loss
            )

        return {
            "strategy": (
                normalized_strategy
            ),
            "trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(
                breakeven
            ),
            "win_rate": round(
                win_rate,
                2,
            ),
            "loss_rate": round(
                loss_rate,
                2,
            ),
            "breakeven_rate": round(
                breakeven_rate,
                2,
            ),
            "total_pnl": round(
                total_pnl,
                2,
            ),
            "gross_profit": round(
                gross_profit,
                2,
            ),
            "gross_loss": round(
                gross_loss,
                2,
            ),
            "average_pnl": round(
                average_pnl,
                2,
            ),
            "average_win": round(
                average_win,
                2,
            ),
            "average_loss": round(
                average_loss,
                2,
            ),
            "average_r": round(
                average_r,
                2,
            ),
            "average_hold_minutes": round(
                average_hold_minutes,
                2,
            ),
            "expectancy": round(
                expectancy,
                2,
            ),
            "profit_factor": (
                round(
                    profit_factor,
                    2,
                )
                if isinstance(
                    profit_factor,
                    float,
                )
                else profit_factor
            ),
        }

    def all_strategy_statistics(
        self,
    ) -> Dict[
        str,
        Dict[str, Any],
    ]:
        return {
            strategy: (
                self.strategy_statistics(
                    strategy
                )
            )
            for strategy in (
                self.strategies()
            )
        }

    @staticmethod
    def _average(
        values: List[float],
    ) -> float:
        if not values:
            return 0.0

        return sum(values) / len(values)

    @staticmethod
    def _to_float(
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return 0.0


if __name__ == "__main__":
    learner = MarketLearning()

    learner.load_trades(
        [
            {
                "strategy": (
                    "ORB_BREAKOUT"
                ),
                "market_condition": (
                    "TRENDING"
                ),
                "pnl": 500,
                "r_multiple": 2.8,
                "holding_minutes": 42,
            },
            {
                "strategy": (
                    "ORB_BREAKOUT"
                ),
                "market_condition": (
                    "TRENDING"
                ),
                "pnl": -100,
                "r_multiple": -1.0,
                "holding_minutes": 18,
            },
            {
                "strategy": (
                    "VWAP_PULLBACK"
                ),
                "market_condition": (
                    "RANGE_BOUND"
                ),
                "pnl": 250,
                "r_multiple": 1.7,
                "holding_minutes": 26,
            },
        ]
    )

    print("\nSUMMARY:")
    print(learner.summary())

    print("\nSTRATEGIES:")
    print(learner.strategies())

    print("\nMARKETS:")
    print(learner.markets())

    print("\nORB STATISTICS:")
    print(
        learner.strategy_statistics(
            "ORB_BREAKOUT"
        )
    )

    print("\nVWAP STATISTICS:")
    print(
        learner.strategy_statistics(
            "VWAP_PULLBACK"
        )
    )

    print(
        "\nALL STRATEGY STATISTICS:"
    )

    print(
        learner.all_strategy_statistics()
    )
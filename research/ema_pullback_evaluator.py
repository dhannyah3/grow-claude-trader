"""
EMA Pullback Strategy Evaluator

Tests a long-only EMA20 pullback strategy using:

- EMA20 above EMA50 trend filter;
- configurable EMA pullback lookback;
- EMA reclaim confirmation;
- RSI and volume filters;
- ATR-based stop and target;
- realistic slippage and trading costs;
- dynamic risk-based position sizing;
- capital-based position limits;
- dynamic account balance;
- forced intraday exit at or before 15:20.

The evaluator reuses the tested sizing, accounting,
cost, drawdown, and reporting methods from StrategyEvaluator.
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from research.dataset_builder import DatasetBuilder
from research.strategy_evaluator import StrategyEvaluator


class EMAPullbackEvaluator:
    def __init__(
        self,
        initial_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_position_percent: float = 20.0,
        slippage_bps: float = 5.0,
    ) -> None:
        self.base_evaluator = StrategyEvaluator(
            initial_balance=initial_balance,
            risk_per_trade_percent=risk_per_trade_percent,
            max_position_percent=max_position_percent,
            slippage_bps=slippage_bps,
        )

    def evaluate(
        self,
        dataframe: pd.DataFrame,
        minimum_rsi: float = 45.0,
        maximum_rsi: float = 70.0,
        maximum_ema_distance_percent: float = 0.30,
        stop_atr_multiplier: float = 1.0,
        target_atr_multiplier: float = 2.0,
        minimum_volume_ratio: float = 0.8,
        pullback_lookback_candles: int = 5,
        require_bullish_candle: bool = True,
        entry_start_time: str = "09:30",
        entry_cutoff_time: str = "15:10",
        force_exit_time: str = "15:20",
    ) -> Dict[str, Any]:
        if dataframe.empty:
            return self.base_evaluator._empty_result()

        if minimum_rsi > maximum_rsi:
            raise ValueError(
                "Minimum RSI cannot exceed maximum RSI."
            )

        if maximum_ema_distance_percent < 0:
            raise ValueError(
                "Maximum EMA distance cannot be negative."
            )

        if stop_atr_multiplier <= 0:
            raise ValueError(
                "Stop ATR multiplier must be greater than zero."
            )

        if target_atr_multiplier <= 0:
            raise ValueError(
                "Target ATR multiplier must be greater than zero."
            )

        if minimum_volume_ratio < 0:
            raise ValueError(
                "Minimum volume ratio cannot be negative."
            )

        if pullback_lookback_candles <= 0:
            raise ValueError(
                "Pullback lookback candles must be greater than zero."
            )

        required_columns = {
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "atr",
            "rsi",
            "ema_20",
            "ema_50",
            "volume_ratio",
        }

        missing = required_columns.difference(
            dataframe.columns
        )

        if missing:
            raise ValueError(
                "Dataset is missing columns: "
                + ", ".join(sorted(missing))
            )

        df = dataframe.copy()

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
        )

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "atr",
            "rsi",
            "ema_20",
            "ema_50",
            "volume_ratio",
        ]

        for column in numeric_columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df = df.dropna(
            subset=[
                "timestamp",
                *numeric_columns,
            ]
        )

        df = df.sort_values(
            "timestamp"
        ).reset_index(
            drop=True
        )

        df["trade_date"] = (
            df["timestamp"].dt.date
        )

        entry_start = pd.Timestamp(
            entry_start_time
        ).time()

        entry_cutoff = pd.Timestamp(
            entry_cutoff_time
        ).time()

        forced_exit = pd.Timestamp(
            force_exit_time
        ).time()

        if not (
            entry_start
            < entry_cutoff
            <= forced_exit
        ):
            raise ValueError(
                "Trading times must satisfy: "
                "entry start < entry cutoff <= force exit."
            )

        slippage_rate = (
            self.base_evaluator.slippage_bps
            / 10000.0
        )

        current_balance = float(
            self.base_evaluator.initial_balance
        )

        trades: List[
            Dict[str, Any]
        ] = []

        skipped_for_quantity = 0

        for trade_date, day_data in (
            df.groupby("trade_date")
        ):
            day_data = (
                day_data.sort_values(
                    "timestamp"
                )
                .reset_index(
                    drop=True
                )
            )

            if day_data.empty:
                continue

            position: Optional[
                Dict[str, Any]
            ] = None

            for row_index, row in (
                day_data.iterrows()
            ):
                current_time = (
                    row["timestamp"].time()
                )

                if current_time < entry_start:
                    continue

                if current_time > forced_exit:
                    break

                if position is None:
                    if current_time > entry_cutoff:
                        break

                    if row_index < 1:
                        continue

                    window_start = max(
                        0,
                        row_index
                        - pullback_lookback_candles,
                    )

                    recent_window = (
                        day_data.iloc[
                            window_start:row_index
                        ]
                    )

                    if recent_window.empty:
                        continue

                    close = float(
                        row["close"]
                    )

                    open_price = float(
                        row["open"]
                    )

                    low = float(
                        row["low"]
                    )

                    ema_20 = float(
                        row["ema_20"]
                    )

                    ema_50 = float(
                        row["ema_50"]
                    )

                    if ema_20 <= 0:
                        continue

                    ema_distance_percent = (
                        abs(close - ema_20)
                        / ema_20
                        * 100.0
                    )

                    recent_pullback = (
                        (
                            recent_window["low"]
                            <= recent_window["ema_20"]
                        )
                        | (
                            recent_window["close"]
                            <= recent_window["ema_20"]
                        )
                    ).any()

                    current_reclaim = (
                        low <= ema_20
                        and close > ema_20
                    )

                    bullish_candle = (
                        close > open_price
                    )

                    candle_confirmation = (
                        bullish_candle
                        if require_bullish_candle
                        else True
                    )

                    trend_confirmed = (
                        ema_20 > ema_50
                    )

                    entry_confirmed = (
                        trend_confirmed
                        and recent_pullback
                        and current_reclaim
                        and candle_confirmation
                        and ema_distance_percent
                        <= maximum_ema_distance_percent
                        and minimum_rsi
                        <= float(row["rsi"])
                        <= maximum_rsi
                        and float(
                            row["volume_ratio"]
                        )
                        >= minimum_volume_ratio
                        and float(row["atr"]) > 0
                    )

                    if not entry_confirmed:
                        continue

                    raw_entry_price = close

                    entry_price = (
                        raw_entry_price
                        * (
                            1.0
                            + slippage_rate
                        )
                    )

                    atr = float(
                        row["atr"]
                    )

                    stop_loss = (
                        entry_price
                        - atr
                        * stop_atr_multiplier
                    )

                    target = (
                        entry_price
                        + atr
                        * target_atr_multiplier
                    )

                    if not (
                        0
                        < stop_loss
                        < entry_price
                        < target
                    ):
                        continue

                    risk_per_share = (
                        entry_price
                        - stop_loss
                    )

                    quantity_details = (
                        self.base_evaluator
                        ._calculate_quantity(
                            account_balance=(
                                current_balance
                            ),
                            entry_price=entry_price,
                            risk_per_share=(
                                risk_per_share
                            ),
                        )
                    )

                    quantity = int(
                        quantity_details[
                            "quantity"
                        ]
                    )

                    if quantity <= 0:
                        skipped_for_quantity += 1
                        continue

                    position = {
                        "entry_time": (
                            row["timestamp"]
                        ),
                        "raw_entry_price": (
                            raw_entry_price
                        ),
                        "entry_price": (
                            entry_price
                        ),
                        "stop_loss": (
                            stop_loss
                        ),
                        "target": target,
                        "quantity": quantity,
                        "risk_budget": (
                            quantity_details[
                                "risk_budget"
                            ]
                        ),
                        "position_capital_limit": (
                            quantity_details[
                                "position_capital_limit"
                            ]
                        ),
                        "risk_based_quantity": (
                            quantity_details[
                                "risk_based_quantity"
                            ]
                        ),
                        "capital_based_quantity": (
                            quantity_details[
                                "capital_based_quantity"
                            ]
                        ),
                        "account_balance_before": (
                            current_balance
                        ),
                    }

                    continue

                low = float(
                    row["low"]
                )

                high = float(
                    row["high"]
                )

                raw_exit_price: Optional[
                    float
                ] = None

                exit_reason = ""

                # Conservative assumption:
                # if both stop and target are touched
                # in one candle, count the stop first.
                if low <= float(
                    position["stop_loss"]
                ):
                    raw_exit_price = float(
                        position["stop_loss"]
                    )
                    exit_reason = "STOP_LOSS"

                elif high >= float(
                    position["target"]
                ):
                    raw_exit_price = float(
                        position["target"]
                    )
                    exit_reason = "TARGET"

                elif current_time >= forced_exit:
                    raw_exit_price = float(
                        row["close"]
                    )
                    exit_reason = "DAY_END_EXIT"

                if raw_exit_price is None:
                    continue

                exit_price = (
                    raw_exit_price
                    * (
                        1.0
                        - slippage_rate
                    )
                )

                trade = (
                    self.base_evaluator
                    ._build_trade(
                        trade_date=trade_date,
                        position=position,
                        exit_time=(
                            row["timestamp"]
                        ),
                        raw_exit_price=(
                            raw_exit_price
                        ),
                        exit_price=exit_price,
                        exit_reason=exit_reason,
                    )
                )

                trade[
                    "ema_pullback_lookback_candles"
                ] = int(
                    pullback_lookback_candles
                )

                trade[
                    "maximum_ema_distance_percent"
                ] = float(
                    maximum_ema_distance_percent
                )

                current_balance = float(
                    trade[
                        "account_balance_after"
                    ]
                )

                trades.append(
                    trade
                )

                position = None
                break

            if position is not None:
                exit_candidates = day_data[
                    day_data[
                        "timestamp"
                    ].dt.time
                    <= forced_exit
                ]

                exit_candidates = (
                    exit_candidates[
                        exit_candidates[
                            "timestamp"
                        ]
                        >= position[
                            "entry_time"
                        ]
                    ]
                )

                if exit_candidates.empty:
                    continue

                last_row = (
                    exit_candidates.iloc[-1]
                )

                raw_exit_price = float(
                    last_row["close"]
                )

                exit_price = (
                    raw_exit_price
                    * (
                        1.0
                        - slippage_rate
                    )
                )

                trade = (
                    self.base_evaluator
                    ._build_trade(
                        trade_date=trade_date,
                        position=position,
                        exit_time=(
                            last_row[
                                "timestamp"
                            ]
                        ),
                        raw_exit_price=(
                            raw_exit_price
                        ),
                        exit_price=exit_price,
                        exit_reason=(
                            "DAY_END_EXIT"
                        ),
                    )
                )

                trade[
                    "ema_pullback_lookback_candles"
                ] = int(
                    pullback_lookback_candles
                )

                trade[
                    "maximum_ema_distance_percent"
                ] = float(
                    maximum_ema_distance_percent
                )

                current_balance = float(
                    trade[
                        "account_balance_after"
                    ]
                )

                trades.append(
                    trade
                )

        return (
            self.base_evaluator
            ._summarize(
                trades=trades,
                skipped_for_quantity=(
                    skipped_for_quantity
                ),
            )
        )


if __name__ == "__main__":
    builder = DatasetBuilder()

    dataset = builder.build_dataset(
        symbol="RELIANCE",
        interval_name="5m",
        year=2025,
    )

    evaluator = EMAPullbackEvaluator(
        initial_balance=100000.0,
        risk_per_trade_percent=0.5,
        max_position_percent=20.0,
        slippage_bps=5.0,
    )

    result = evaluator.evaluate(
        dataframe=dataset,
        minimum_rsi=45.0,
        maximum_rsi=70.0,
        maximum_ema_distance_percent=0.30,
        stop_atr_multiplier=1.0,
        target_atr_multiplier=2.0,
        minimum_volume_ratio=0.8,
        pullback_lookback_candles=5,
        require_bullish_candle=True,
        entry_start_time="09:30",
        entry_cutoff_time="15:10",
        force_exit_time="15:20",
    )

    print()
    print("=" * 60)
    print("EMA PULLBACK EVALUATION")
    print("=" * 60)

    for key, value in result.items():
        if key == "trades":
            continue

        print(
            f"{key}: {value}"
        )

    print()
    print("First 5 trades:")

    for trade in result["trades"][:5]:
        print(trade)

    invalid_day_end_exits = [
        trade
        for trade in result["trades"]
        if (
            trade["exit_reason"]
            == "DAY_END_EXIT"
            and pd.Timestamp(
                trade["exit_time"]
            ).time()
            > pd.Timestamp(
                "15:20"
            ).time()
        )
    ]

    if invalid_day_end_exits:
        raise AssertionError(
            "A DAY_END_EXIT occurred after 15:20."
        )

    print()
    print(
        "Exit-time validation passed: "
        "all DAY_END_EXIT trades occurred "
        "at or before 15:20."
    )
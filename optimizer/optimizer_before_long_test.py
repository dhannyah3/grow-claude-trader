import csv
import time
from datetime import date
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backtester import backtest_orb
from data.market_data import MarketData
from multi_backtest import (
    REQUEST_DELAY_SECONDS,
    fetch_candles_with_retry,
    trading_days,
)
from optimizer.parameter_grid import (
    ENTRY_CUTOFFS,
    RISK_REWARD_RATIOS,
    RSI_MAX_VALUES,
    RSI_MIN_VALUES,
    VOLUME_MULTIPLIERS,
)


SYMBOL = "RELIANCE"
START_DATE = date(2026, 7, 1)
END_DATE = date(2026, 7, 10)

STARTING_CAPITAL = 100000.0
RISK_PER_TRADE_PERCENT = 0.5
SLIPPAGE_BPS = 5.0

RESULTS_FILE = Path(
    "optimizer/results/orb_optimizer_results.csv"
)


def generate_parameter_sets() -> List[Tuple]:
    """
    Generate every possible parameter combination.
    """

    return list(
        product(
            RSI_MIN_VALUES,
            RSI_MAX_VALUES,
            ENTRY_CUTOFFS,
            RISK_REWARD_RATIOS,
            VOLUME_MULTIPLIERS,
        )
    )


def load_candle_cache(
    symbol: str,
    start_date: date,
    end_date: date,
) -> Dict[str, Dict[str, Any]]:
    """
    Download each trading day's candles once.

    The optimizer reuses this data for every parameter set.
    """

    market = MarketData()
    candle_cache: Dict[
        str,
        Dict[str, Any],
    ] = {}

    days = trading_days(
        start_date=start_date,
        end_date=end_date,
    )

    print(
        f"\nDownloading candles for "
        f"{len(days)} weekdays...\n"
    )

    for index, trading_day in enumerate(
        days,
        start=1,
    ):
        day_text = trading_day.strftime(
            "%Y-%m-%d"
        )

        print(
            f"[{index}/{len(days)}] "
            f"Fetching {symbol} on {day_text}..."
        )

        candles = fetch_candles_with_retry(
            market=market,
            symbol=symbol,
            day_text=day_text,
        )

        if candles and candles.get("candles"):
            candle_cache[day_text] = candles
        else:
            print(
                f"{day_text}: no candle data."
            )

        time.sleep(REQUEST_DELAY_SECONDS)

    print(
        f"\nCached {len(candle_cache)} "
        f"trading days.\n"
    )

    return candle_cache


def calculate_max_drawdown(
    net_pnls: List[float],
    starting_capital: float,
) -> float:
    equity = starting_capital
    peak_equity = starting_capital
    maximum_drawdown = 0.0

    for net_pnl in net_pnls:
        equity += net_pnl
        peak_equity = max(
            peak_equity,
            equity,
        )

        drawdown = peak_equity - equity

        maximum_drawdown = max(
            maximum_drawdown,
            drawdown,
        )

    return maximum_drawdown


def evaluate_parameter_set(
    candle_cache: Dict[
        str,
        Dict[str, Any],
    ],
    rsi_min: float,
    rsi_max: float,
    entry_cutoff: str,
    risk_reward_ratio: float,
    volume_multiplier: float,
) -> Dict[str, Any]:
    """
    Run one parameter set over all cached trading days.
    """

    current_capital = STARTING_CAPITAL
    trade_results: List[
        Dict[str, Any]
    ] = []

    for day_text in sorted(candle_cache):
        result = backtest_orb(
            candles_response=(
                candle_cache[day_text]
            ),
            starting_capital=current_capital,
            risk_per_trade_percent=(
                RISK_PER_TRADE_PERCENT
            ),
            risk_reward_ratio=(
                risk_reward_ratio
            ),
            slippage_bps=SLIPPAGE_BPS,
            rsi_min=rsi_min,
            rsi_max=rsi_max,
            entry_cutoff=entry_cutoff,
            volume_multiplier=(
                volume_multiplier
            ),
        )

        if result is None:
            continue

        if result.get("result") in {
            "NO_TRADE",
            "INSUFFICIENT_CAPITAL",
        }:
            continue

        net_pnl = float(
            result.get("net_pnl", 0.0)
        )

        current_capital += net_pnl
        trade_results.append(result)

    net_pnls = [
        float(
            trade.get("net_pnl", 0.0)
        )
        for trade in trade_results
    ]

    winning_pnls = [
        pnl
        for pnl in net_pnls
        if pnl > 0
    ]

    losing_pnls = [
        pnl
        for pnl in net_pnls
        if pnl < 0
    ]

    total_trades = len(net_pnls)
    winning_trades = len(winning_pnls)
    losing_trades = len(losing_pnls)

    total_net_pnl = sum(net_pnls)

    win_rate = (
        winning_trades
        / total_trades
        * 100
        if total_trades > 0
        else 0.0
    )

    gross_profit = sum(winning_pnls)

    gross_loss = abs(
        sum(losing_pnls)
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit / gross_loss
        )
    elif gross_profit > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    maximum_drawdown = (
        calculate_max_drawdown(
            net_pnls=net_pnls,
            starting_capital=(
                STARTING_CAPITAL
            ),
        )
    )

    return_percent = (
        total_net_pnl
        / STARTING_CAPITAL
        * 100
    )

    maximum_drawdown_percent = (
        maximum_drawdown
        / STARTING_CAPITAL
        * 100
    )

    average_net_pnl = (
        total_net_pnl / total_trades
        if total_trades > 0
        else 0.0
    )

    return {
        "rsi_min": rsi_min,
        "rsi_max": rsi_max,
        "entry_cutoff": entry_cutoff,
        "risk_reward_ratio": (
            risk_reward_ratio
        ),
        "volume_multiplier": (
            volume_multiplier
        ),
        "trades": total_trades,
        "wins": winning_trades,
        "losses": losing_trades,
        "win_rate": round(
            win_rate,
            2,
        ),
        "net_pnl": round(
            total_net_pnl,
            2,
        ),
        "return_percent": round(
            return_percent,
            4,
        ),
        "profit_factor": round(
            profit_factor,
            4,
        ),
        "max_drawdown": round(
            maximum_drawdown,
            2,
        ),
        "max_drawdown_percent": round(
            maximum_drawdown_percent,
            4,
        ),
        "average_net_pnl": round(
            average_net_pnl,
            2,
        ),
        "ending_capital": round(
            current_capital,
            2,
        ),
    }


def save_results(
    results: List[Dict[str, Any]],
) -> None:
    RESULTS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not results:
        print("No optimizer results to save.")
        return

    with RESULTS_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=list(
                results[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(results)

    print(
        f"\nSaved results to "
        f"{RESULTS_FILE}"
    )


def print_top_results(
    results: List[Dict[str, Any]],
    limit: int = 10,
) -> None:
    print(
        "\n===== TOP ORB PARAMETER SETS =====\n"
    )

    for rank, result in enumerate(
        results[:limit],
        start=1,
    ):
        print(
            f"{rank:2}. "
            f"Net: ₹{result['net_pnl']:.2f} | "
            f"PF: "
            f"{result['profit_factor']:.2f} | "
            f"Win: {result['win_rate']:.2f}% | "
            f"Trades: {result['trades']} | "
            f"DD: "
            f"₹{result['max_drawdown']:.2f} | "
            f"RSI: "
            f"{result['rsi_min']}-"
            f"{result['rsi_max']} | "
            f"Cutoff: "
            f"{result['entry_cutoff']} | "
            f"RR: "
            f"{result['risk_reward_ratio']} | "
            f"Volume: "
            f"{result['volume_multiplier']}x"
        )


def main() -> None:
    parameter_sets = (
        generate_parameter_sets()
    )

    print(
        f"\nGenerated "
        f"{len(parameter_sets)} "
        f"parameter sets."
    )

    candle_cache = load_candle_cache(
        symbol=SYMBOL,
        start_date=START_DATE,
        end_date=END_DATE,
    )

    if not candle_cache:
        print(
            "No candle data was downloaded. "
            "Optimizer stopped."
        )
        return

    optimization_results: List[
        Dict[str, Any]
    ] = []

    for index, parameters in enumerate(
        parameter_sets,
        start=1,
    ):
        (
            rsi_min,
            rsi_max,
            entry_cutoff,
            risk_reward_ratio,
            volume_multiplier,
        ) = parameters

        print(
            f"Testing {index}/"
            f"{len(parameter_sets)} | "
            f"RSI {rsi_min}-{rsi_max} | "
            f"Cutoff {entry_cutoff} | "
            f"RR {risk_reward_ratio} | "
            f"Volume "
            f"{volume_multiplier}x"
        )

        result = evaluate_parameter_set(
            candle_cache=candle_cache,
            rsi_min=rsi_min,
            rsi_max=rsi_max,
            entry_cutoff=entry_cutoff,
            risk_reward_ratio=(
                risk_reward_ratio
            ),
            volume_multiplier=(
                volume_multiplier
            ),
        )

        optimization_results.append(
            result
        )

    optimization_results.sort(
        key=lambda item: (
            item["trades"] >= 3,
            item["net_pnl"],
            item["profit_factor"],
        ),
        reverse=True,
    )

    save_results(
        optimization_results
    )

    print_top_results(
        optimization_results,
        limit=10,
    )


if __name__ == "__main__":
    main()
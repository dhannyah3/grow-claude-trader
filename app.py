from pathlib import Path
import json

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from core.market_clock import market_status, now_in_india
from data.scanner import MarketScanner
from watchlist import WATCHLIST


TRADE_LOG = Path("logs/paper_trades.csv")
OPEN_POSITIONS_FILE = Path("logs/open_positions.json")

STARTING_BALANCE = 100000.0
AUTO_REFRESH_MS = 60000


st.set_page_config(
    page_title="Groww Claude Paper Trader",
    page_icon="📈",
    layout="wide",
)

st_autorefresh(
    interval=AUTO_REFRESH_MS,
    key="dashboard_refresh",
)

st.title("📈 Groww Claude Paper Trader")
st.caption("Paper Trading Dashboard — No Real Orders")


def load_trades() -> pd.DataFrame:
    if not TRADE_LOG.exists() or TRADE_LOG.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(TRADE_LOG)
    except Exception as error:
        st.error(f"Could not read trade log: {error}")
        return pd.DataFrame()


def load_open_positions() -> pd.DataFrame:
    if (
        not OPEN_POSITIONS_FILE.exists()
        or OPEN_POSITIONS_FILE.stat().st_size == 0
    ):
        return pd.DataFrame()

    try:
        raw_text = OPEN_POSITIONS_FILE.read_text(
            encoding="utf-8"
        ).strip()

        if not raw_text:
            return pd.DataFrame()

        data = json.loads(raw_text)
    except Exception as error:
        st.error(f"Could not read open positions: {error}")
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    return pd.DataFrame(data.values())


india_time = now_in_india()
status = market_status(india_time)

st.write(
    f"### 🇮🇳 India Time: "
    f"{india_time.strftime('%d %b %Y %I:%M:%S %p')}"
)

if status == "OPEN":
    st.success("🟢 Market OPEN")
elif status == "NO_NEW_ENTRIES":
    st.warning("🟡 No New Entries")
else:
    st.error(f"🔴 Market Status: {status}")

st.divider()


trades = load_trades()
open_positions = load_open_positions()


required_trade_columns = [
    "entry_time",
    "exit_time",
    "symbol",
    "quantity",
    "entry_price",
    "exit_price",
    "stop_loss",
    "target",
    "pnl",
    "exit_reason",
]

for column in required_trade_columns:
    if column not in trades.columns:
        trades[column] = pd.Series(dtype="object")

if not trades.empty:
    trades["pnl"] = pd.to_numeric(
        trades["pnl"],
        errors="coerce",
    ).fillna(0.0)


realized_pnl = (
    float(trades["pnl"].sum())
    if not trades.empty
    else 0.0
)

closed_trades = len(trades)

winning_trades = (
    int((trades["pnl"] > 0).sum())
    if not trades.empty
    else 0
)

losing_trades = (
    int((trades["pnl"] < 0).sum())
    if not trades.empty
    else 0
)

win_rate = (
    winning_trades / closed_trades * 100
    if closed_trades > 0
    else 0.0
)


scanner_data = []
live_results = []
price_map = {}

try:
    scanner = MarketScanner()
    live_results = scanner.scan()

    price_map = {
        stock.get("symbol"): stock.get("last_price")
        for stock in live_results
        if stock.get("symbol") is not None
    }

    for stock in live_results:
        change = stock.get("day_change_perc")

        if change is None:
            score = 0
            signal = "⚪ WAIT"
        elif change >= 1.5:
            score = 80
            signal = "🟢 WATCH"
        elif change <= -1.5:
            score = 20
            signal = "🔴 WEAK"
        else:
            score = 50
            signal = "⚪ WAIT"

        scanner_data.append(
            {
                "Symbol": stock.get("symbol"),
                "Price": stock.get("last_price"),
                "Change %": round(change or 0, 2),
                "Volume": stock.get("volume"),
                "Score": score,
                "Signal": signal,
            }
        )

except Exception as error:
    st.error(f"Live scanner failed: {error}")


unrealized_pnl = 0.0
open_position_value = 0.0

if not open_positions.empty:
    numeric_position_columns = [
        "quantity",
        "entry_price",
        "stop_loss",
        "target",
    ]

    for column in numeric_position_columns:
        if column in open_positions.columns:
            open_positions[column] = pd.to_numeric(
                open_positions[column],
                errors="coerce",
            )

    open_positions["current_price"] = open_positions[
        "symbol"
    ].map(price_map)

    open_positions["current_price"] = pd.to_numeric(
        open_positions["current_price"],
        errors="coerce",
    )

    open_positions["unrealized_pnl"] = (
        open_positions["current_price"]
        - open_positions["entry_price"]
    ) * open_positions["quantity"]

    open_positions["pnl_percent"] = (
        (
            open_positions["current_price"]
            - open_positions["entry_price"]
        )
        / open_positions["entry_price"]
        * 100
    )

    unrealized_pnl = float(
        open_positions["unrealized_pnl"]
        .fillna(0.0)
        .sum()
    )

    open_position_value = float(
        (
            open_positions["current_price"]
            * open_positions["quantity"]
        )
        .fillna(0.0)
        .sum()
    )


paper_balance = STARTING_BALANCE + realized_pnl
total_pnl = realized_pnl + unrealized_pnl


metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)

metric_1.metric(
    "💰 Paper Balance",
    f"₹{paper_balance:,.2f}",
)

metric_2.metric(
    "📈 Total P&L",
    f"₹{total_pnl:,.2f}",
    f"Unrealized ₹{unrealized_pnl:,.2f}",
)

metric_3.metric(
    "✅ Closed Trades",
    closed_trades,
)

metric_4.metric(
    "🎯 Win Rate",
    f"{win_rate:.2f}%",
)

metric_5.metric(
    "📌 Open Positions",
    len(open_positions),
)

st.divider()


st.subheader("📡 Live Scanner")

if scanner_data:
    scanner_df = pd.DataFrame(scanner_data)

    st.dataframe(
        scanner_df,
        width="stretch",
        hide_index=True,
        column_config={
            "Price": st.column_config.NumberColumn(
                format="₹%.2f"
            ),
            "Change %": st.column_config.NumberColumn(
                format="%.2f%%"
            ),
            "Volume": st.column_config.NumberColumn(
                format="%d"
            ),
            "Score": st.column_config.NumberColumn(
                format="%d"
            ),
        },
    )
else:
    st.info("No scanner data available.")

st.divider()


st.subheader("📌 Open Paper Positions")

if open_positions.empty:
    st.info("No open paper positions.")
else:
    display_positions = open_positions.copy()

    if "entry_time" in display_positions.columns:
        display_positions["entry_time"] = pd.to_datetime(
            display_positions["entry_time"],
            errors="coerce",
        )

    display_positions = display_positions.rename(
        columns={
            "symbol": "Symbol",
            "quantity": "Quantity",
            "entry_price": "Entry Price",
            "current_price": "Current Price",
            "unrealized_pnl": "Unrealized P&L",
            "pnl_percent": "P&L %",
            "stop_loss": "Stop Loss",
            "target": "Target",
            "entry_time": "Entry Time",
        }
    )

    display_columns = [
        "Symbol",
        "Quantity",
        "Entry Price",
        "Current Price",
        "Unrealized P&L",
        "P&L %",
        "Stop Loss",
        "Target",
        "Entry Time",
    ]

    available_columns = [
        column
        for column in display_columns
        if column in display_positions.columns
    ]

    st.dataframe(
        display_positions[available_columns],
        width="stretch",
        hide_index=True,
        column_config={
            "Entry Price": st.column_config.NumberColumn(
                format="₹%.2f"
            ),
            "Current Price": st.column_config.NumberColumn(
                format="₹%.2f"
            ),
            "Unrealized P&L": st.column_config.NumberColumn(
                format="₹%.2f"
            ),
            "P&L %": st.column_config.NumberColumn(
                format="%.2f%%"
            ),
            "Stop Loss": st.column_config.NumberColumn(
                format="₹%.2f"
            ),
            "Target": st.column_config.NumberColumn(
                format="₹%.2f"
            ),
        },
    )

    position_col_1, position_col_2 = st.columns(2)

    position_col_1.metric(
        "Open Position Value",
        f"₹{open_position_value:,.2f}",
    )

    position_col_2.metric(
        "Unrealized P&L",
        f"₹{unrealized_pnl:,.2f}",
    )

st.divider()


left, right = st.columns([3, 1])

with left:
    st.subheader("📜 Trade History")

    if trades.empty:
        st.info("No closed paper trades yet.")
    else:
        st.dataframe(
            trades,
            width="stretch",
            hide_index=True,
            column_config={
                "entry_price": st.column_config.NumberColumn(
                    "Entry Price",
                    format="₹%.2f",
                ),
                "exit_price": st.column_config.NumberColumn(
                    "Exit Price",
                    format="₹%.2f",
                ),
                "stop_loss": st.column_config.NumberColumn(
                    "Stop Loss",
                    format="₹%.2f",
                ),
                "target": st.column_config.NumberColumn(
                    "Target",
                    format="₹%.2f",
                ),
                "pnl": st.column_config.NumberColumn(
                    "P&L",
                    format="₹%.2f",
                ),
            },
        )

        st.subheader("📈 Equity Curve")

        equity_curve = (
            STARTING_BALANCE
            + trades["pnl"].cumsum()
        )

        equity_chart = pd.DataFrame(
            {
                "Paper Balance": equity_curve,
            }
        )

        st.line_chart(
            equity_chart,
            width="stretch",
        )

with right:
    st.subheader("📊 Performance")

    st.write(
        f"Winning Trades: **{winning_trades}**"
    )
    st.write(
        f"Losing Trades: **{losing_trades}**"
    )
    st.write(
        f"Realized P&L: **₹{realized_pnl:,.2f}**"
    )
    st.write(
        f"Unrealized P&L: **₹{unrealized_pnl:,.2f}**"
    )
    st.write(
        f"Total P&L: **₹{total_pnl:,.2f}**"
    )
    st.write(
        f"Open Positions: **{len(open_positions)}**"
    )

    st.divider()

    st.subheader("👀 Watchlist")

    for symbol in WATCHLIST:
        st.write(f"• {symbol}")

st.divider()

if st.button("🔄 Refresh Now"):
    st.rerun()
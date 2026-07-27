# AI Intraday Trading Platform - Production Architecture

## Vision

The trading platform follows a layered architecture.

Each layer has a single responsibility.

No business logic should be duplicated.

---

# Layer 1 — Market Data

Responsible for:

- Groww API
- Historical candles
- Live quotes
- Watchlist

Module:

data/
    market_data.py

---

# Layer 2 — Indicator Engine

Responsible for:

- EMA20
- EMA50
- RSI
- ATR
- VWAP
- MACD
- Volume

Module:

strategies/
    indicators.py

---

# Layer 3 — Strategy Engine

Responsible for:

- ORB
- VWAP Pullback
- Future strategies

Module:

strategies/
    factory.py

---

# Layer 4 — Market Intelligence

Responsible for:

- Market Regime
- Market Quality
- Trend
- RSI State
- VWAP State
- Volume State

Modules:

analytics/
intelligence/

---

# Layer 5 — Decision Layer

Responsible for:

- Stock Selection
- Portfolio Allocation
- Position Sizing
- Trade Priority
- Risk Budget

Modules:

decision/

---

# Layer 6 — AI Review

Responsible for:

Claude Approval

Module:

strategies/
    claude_analyzer.py

---

# Layer 7 — Risk Layer

Responsible for:

- Safety Manager
- Risk Manager
- Portfolio Heat
- Dynamic Position Size

Modules:

core/

---

# Layer 8 — Execution

Responsible for:

- Live Execution
- Paper Trading
- Order Manager
- Position Sync

Modules:

execution/

---

# Layer 9 — Analytics

Responsible for:

- Journal
- Performance
- Learning
- Recommendation

Modules:

analytics/

---

# Future Goal

main.py should only orchestrate modules.

Business logic belongs inside dedicated modules.
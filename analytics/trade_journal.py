import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TradeJournal:
    """
    Stores completed trades together with:

    - Strategy
    - Claude review
    - Technical indicators
    - Market regime
    - Market intelligence
    - MarketBrain decision
    - Position sizing information
    """

    def __init__(
        self,
        journal_file: str = "logs/trade_journal.json",
    ) -> None:
        self.journal_file = Path(
            journal_file
        )

        self.journal_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.journal_file.exists():
            self.journal_file.write_text(
                "[]",
                encoding="utf-8",
            )

    def load_entries(
        self,
    ) -> List[Dict[str, Any]]:
        if (
            not self.journal_file.exists()
            or self.journal_file.stat().st_size == 0
        ):
            return []

        try:
            raw_text = self.journal_file.read_text(
                encoding="utf-8",
            ).strip()

            if not raw_text:
                return []

            data = json.loads(
                raw_text
            )

            if not isinstance(
                data,
                list,
            ):
                print(
                    "Trade journal has an "
                    "invalid format."
                )
                return []

            return data

        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            print(
                "Could not load trade journal: "
                f"{error}"
            )
            return []

    def save_entries(
        self,
        entries: List[Dict[str, Any]],
    ) -> None:
        temporary_file = (
            self.journal_file.with_suffix(
                ".tmp"
            )
        )

        temporary_file.write_text(
            json.dumps(
                entries,
                indent=4,
            ),
            encoding="utf-8",
        )

        temporary_file.replace(
            self.journal_file
        )

    def add_entry(
        self,
        trade: Dict[str, Any],
        strategy: str,
        claude_review: Dict[str, Any],
        indicators: Dict[str, Any],
        market_condition: str,
        market_regime: Optional[
            Dict[str, Any]
        ] = None,
        market_intelligence: Optional[
            Dict[str, Any]
        ] = None,
        market_brain: Optional[
            Dict[str, Any]
        ] = None,
        position_multiplier: float = 1.0,
        strategy_score: int = 0,
    ) -> Dict[str, Any]:
        """
        Add a completed trade to the journal.

        The extra arguments are optional, so older
        code using the original method still works.
        """

        market_regime = (
            market_regime or {}
        )

        market_intelligence = (
            market_intelligence or {}
        )

        market_brain = (
            market_brain or {}
        )

        pnl = float(
            trade.get(
                "pnl",
                0.0,
            )
        )

        if pnl > 0:
            result = "WIN"

        elif pnl < 0:
            result = "LOSS"

        else:
            result = "BREAKEVEN"

        entry = {
            "journal_time": (
                datetime.now().isoformat()
            ),
            "symbol": str(
                trade.get(
                    "symbol",
                    "",
                )
            ),
            "strategy": str(
                strategy
            ),
            "entry_time": (
                self._serialize_datetime(
                    trade.get(
                        "entry_time"
                    )
                )
            ),
            "exit_time": (
                self._serialize_datetime(
                    trade.get(
                        "exit_time"
                    )
                )
            ),
            "quantity": int(
                trade.get(
                    "quantity",
                    0,
                )
            ),
            "entry_price": round(
                float(
                    trade.get(
                        "entry_price",
                        0.0,
                    )
                ),
                2,
            ),
            "exit_price": round(
                float(
                    trade.get(
                        "exit_price",
                        0.0,
                    )
                ),
                2,
            ),
            "stop_loss": round(
                float(
                    trade.get(
                        "stop_loss",
                        0.0,
                    )
                ),
                2,
            ),
            "target": round(
                float(
                    trade.get(
                        "target",
                        0.0,
                    )
                ),
                2,
            ),
            "pnl": round(
                pnl,
                2,
            ),
            "result": result,
            "exit_reason": str(
                trade.get(
                    "exit_reason",
                    "",
                )
            ),
            "claude": {
                "approved": bool(
                    claude_review.get(
                        "approved",
                        False,
                    )
                ),
                "confidence": int(
                    claude_review.get(
                        "confidence",
                        0,
                    )
                    or 0
                ),
                "reason": str(
                    claude_review.get(
                        "reason",
                        "",
                    )
                ),
            },
            "indicators": {
                "rsi": self._to_float(
                    indicators.get(
                        "rsi"
                    )
                ),
                "atr": self._to_float(
                    indicators.get(
                        "atr"
                    )
                ),
                "ema_20": self._to_float(
                    indicators.get(
                        "ema_20"
                    )
                ),
                "ema_50": self._to_float(
                    indicators.get(
                        "ema_50"
                    )
                ),
                "vwap": self._to_float(
                    indicators.get(
                        "vwap"
                    )
                ),
                "macd": self._to_float(
                    indicators.get(
                        "macd"
                    )
                ),
                "macd_signal": (
                    self._to_float(
                        indicators.get(
                            "macd_signal"
                        )
                    )
                ),
                "opening_high": (
                    self._to_float(
                        indicators.get(
                            "opening_high"
                        )
                    )
                ),
            },
            "market_condition": str(
                market_condition
            ),
            "market_regime": (
                market_regime
            ),
            "market_intelligence": (
                market_intelligence
            ),
            "market_brain": (
                market_brain
            ),
            "market_quality": int(
                market_intelligence.get(
                    "market_quality",
                    0,
                )
                or 0
            ),
            "strategy_score": int(
                strategy_score
                or 0
            ),
            "brain_confidence": int(
                market_brain.get(
                    "confidence",
                    0,
                )
                or 0
            ),
            "brain_risk_multiplier": (
                self._to_float(
                    market_brain.get(
                        "risk_multiplier",
                        1.0,
                    )
                )
            ),
            "position_multiplier": (
                self._to_float(
                    position_multiplier
                )
            ),
        }

        entries = self.load_entries()
        entries.append(entry)
        self.save_entries(entries)

        return entry

    def get_summary(
        self,
    ) -> Dict[str, Any]:
        entries = self.load_entries()

        total_entries = len(
            entries
        )

        wins = sum(
            1
            for entry in entries
            if entry.get("result") == "WIN"
        )

        losses = sum(
            1
            for entry in entries
            if entry.get("result") == "LOSS"
        )

        breakeven = sum(
            1
            for entry in entries
            if entry.get("result")
            == "BREAKEVEN"
        )

        total_pnl = sum(
            float(
                entry.get(
                    "pnl",
                    0.0,
                )
            )
            for entry in entries
        )

        win_rate = (
            wins
            / total_entries
            * 100
            if total_entries > 0
            else 0.0
        )

        return {
            "total_entries": total_entries,
            "wins": wins,
            "losses": losses,
            "breakeven": breakeven,
            "win_rate": round(
                win_rate,
                2,
            ),
            "total_pnl": round(
                total_pnl,
                2,
            ),
        }

    @staticmethod
    def _serialize_datetime(
        value: Any,
    ) -> str:
        if isinstance(
            value,
            datetime,
        ):
            return value.isoformat()

        if value is None:
            return ""

        return str(value)

    @staticmethod
    def _to_float(
        value: Any,
    ) -> float:
        try:
            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0.0


if __name__ == "__main__":
    journal = TradeJournal(
        journal_file=(
            "logs/test_trade_journal.json"
        )
    )

    test_trade = {
        "symbol": "RELIANCE",
        "entry_time": datetime.now(),
        "exit_time": datetime.now(),
        "quantity": 10,
        "entry_price": 1300.0,
        "exit_price": 1310.0,
        "stop_loss": 1290.0,
        "target": 1320.0,
        "pnl": 100.0,
        "exit_reason": "TARGET",
    }

    test_review = {
        "approved": True,
        "confidence": 90,
        "reason": (
            "Strong technical alignment."
        ),
    }

    test_indicators = {
        "rsi": 61.0,
        "atr": 5.0,
        "ema_20": 1305.0,
        "ema_50": 1298.0,
        "vwap": 1302.0,
        "macd": 1.5,
        "macd_signal": 1.1,
        "opening_high": 1308.0,
    }

    saved_entry = journal.add_entry(
        trade=test_trade,
        strategy="ORB_BREAKOUT",
        claude_review=test_review,
        indicators=test_indicators,
        market_condition="TRENDING",
        market_regime={
            "trend": "TRENDING",
            "trend_strength": "STRONG",
            "volatility": "MEDIUM",
            "gap": "NO_GAP",
        },
        market_intelligence={
            "market_quality": 82,
            "rsi_state": "BULLISH",
            "macd_state": "BULLISH",
            "vwap_state": "ABOVE",
            "volume_state": "HIGH",
        },
        market_brain={
            "confidence": 85,
            "risk_multiplier": 0.75,
            "recommended_strategy": (
                "ORB_BREAKOUT"
            ),
        },
        position_multiplier=0.60,
        strategy_score=85,
    )

    print(
        "\n===== SAVED JOURNAL ENTRY =====\n"
    )

    print(
        saved_entry
    )

    print(
        "\n===== JOURNAL SUMMARY =====\n"
    )

    print(
        journal.get_summary()
    )
"""
Central safety controls for the trading platform.

This module manages:
- emergency kill switch;
- daily trade limits;
- daily loss protection;
- consecutive-loss protection;
- API and broker failure counters;
- shutdown decisions;
- runtime health reporting.
"""

from datetime import date
from typing import Any, Dict, Optional


class SafetyManager:
    def __init__(
        self,
        max_trades_per_day: int = 5,
        max_daily_loss: float = 2000.0,
        max_consecutive_losses: int = 3,
        max_api_failures: int = 5,
        max_broker_failures: int = 3,
    ) -> None:
        self.max_trades_per_day = int(
            max_trades_per_day
        )

        self.max_daily_loss = abs(
            float(max_daily_loss)
        )

        self.max_consecutive_losses = int(
            max_consecutive_losses
        )

        self.max_api_failures = int(
            max_api_failures
        )

        self.max_broker_failures = int(
            max_broker_failures
        )

        self.kill_switch_enabled = False
        self.kill_switch_reason = ""

        self.trade_count = 0
        self.daily_realized_pnl = 0.0
        self.consecutive_losses = 0
        self.api_failures = 0
        self.broker_failures = 0

        self.current_day = date.today()

    def reset_if_new_day(self) -> None:
        today = date.today()

        if today == self.current_day:
            return

        self.current_day = today
        self.trade_count = 0
        self.daily_realized_pnl = 0.0
        self.consecutive_losses = 0
        self.api_failures = 0
        self.broker_failures = 0

        self.kill_switch_enabled = False
        self.kill_switch_reason = ""

    def enable_kill_switch(
        self,
        reason: str = "Manual emergency stop.",
    ) -> None:
        self.kill_switch_enabled = True
        self.kill_switch_reason = str(
            reason
        ).strip() or "Emergency stop."

    def disable_kill_switch(self) -> None:
        self.kill_switch_enabled = False
        self.kill_switch_reason = ""

    def record_trade_opened(self) -> None:
        self.reset_if_new_day()
        self.trade_count += 1

    def record_trade_closed(
        self,
        pnl: float,
    ) -> None:
        self.reset_if_new_day()

        pnl = float(pnl)
        self.daily_realized_pnl += pnl

        if pnl < 0:
            self.consecutive_losses += 1

        elif pnl > 0:
            self.consecutive_losses = 0

    def record_api_failure(self) -> None:
        self.reset_if_new_day()
        self.api_failures += 1

    def clear_api_failures(self) -> None:
        self.api_failures = 0

    def record_broker_failure(self) -> None:
        self.reset_if_new_day()
        self.broker_failures += 1

    def clear_broker_failures(self) -> None:
        self.broker_failures = 0

    def can_open_trade(
        self,
        current_daily_pnl: Optional[float] = None,
    ) -> Dict[str, Any]:
        self.reset_if_new_day()

        daily_pnl = (
            float(current_daily_pnl)
            if current_daily_pnl is not None
            else self.daily_realized_pnl
        )

        if self.kill_switch_enabled:
            return {
                "allowed": False,
                "reason": (
                    self.kill_switch_reason
                    or "Emergency kill switch enabled."
                ),
            }

        if self.trade_count >= (
            self.max_trades_per_day
        ):
            return {
                "allowed": False,
                "reason": (
                    "Maximum daily trade limit "
                    "has been reached."
                ),
            }

        if daily_pnl <= -self.max_daily_loss:
            return {
                "allowed": False,
                "reason": (
                    "Maximum daily loss limit "
                    "has been reached."
                ),
            }

        if self.consecutive_losses >= (
            self.max_consecutive_losses
        ):
            return {
                "allowed": False,
                "reason": (
                    "Consecutive-loss circuit "
                    "breaker is active."
                ),
            }

        if self.api_failures >= (
            self.max_api_failures
        ):
            return {
                "allowed": False,
                "reason": (
                    "API failure limit "
                    "has been reached."
                ),
            }

        if self.broker_failures >= (
            self.max_broker_failures
        ):
            return {
                "allowed": False,
                "reason": (
                    "Broker failure limit "
                    "has been reached."
                ),
            }

        return {
            "allowed": True,
            "reason": "Safety checks passed.",
        }

    def should_shutdown(
        self,
        current_daily_pnl: Optional[float] = None,
    ) -> Dict[str, Any]:
        self.reset_if_new_day()

        daily_pnl = (
            float(current_daily_pnl)
            if current_daily_pnl is not None
            else self.daily_realized_pnl
        )

        if self.kill_switch_enabled:
            return {
                "shutdown": True,
                "reason": (
                    self.kill_switch_reason
                    or "Emergency kill switch enabled."
                ),
            }

        if daily_pnl <= -self.max_daily_loss:
            return {
                "shutdown": True,
                "reason": (
                    "Daily loss limit reached."
                ),
            }

        if self.api_failures >= (
            self.max_api_failures
        ):
            return {
                "shutdown": True,
                "reason": (
                    "Too many API failures."
                ),
            }

        if self.broker_failures >= (
            self.max_broker_failures
        ):
            return {
                "shutdown": True,
                "reason": (
                    "Too many broker failures."
                ),
            }

        return {
            "shutdown": False,
            "reason": "Shutdown not required.",
        }

    def status(
        self,
        current_daily_pnl: Optional[float] = None,
    ) -> Dict[str, Any]:
        self.reset_if_new_day()

        daily_pnl = (
            float(current_daily_pnl)
            if current_daily_pnl is not None
            else self.daily_realized_pnl
        )

        trade_decision = self.can_open_trade(
            current_daily_pnl=daily_pnl
        )

        shutdown_decision = self.should_shutdown(
            current_daily_pnl=daily_pnl
        )

        return {
            "date": self.current_day.isoformat(),
            "healthy": (
                trade_decision["allowed"]
                and not shutdown_decision[
                    "shutdown"
                ]
            ),
            "kill_switch_enabled": (
                self.kill_switch_enabled
            ),
            "kill_switch_reason": (
                self.kill_switch_reason
            ),
            "trade_count": self.trade_count,
            "max_trades_per_day": (
                self.max_trades_per_day
            ),
            "daily_realized_pnl": daily_pnl,
            "max_daily_loss": (
                self.max_daily_loss
            ),
            "consecutive_losses": (
                self.consecutive_losses
            ),
            "max_consecutive_losses": (
                self.max_consecutive_losses
            ),
            "api_failures": self.api_failures,
            "max_api_failures": (
                self.max_api_failures
            ),
            "broker_failures": (
                self.broker_failures
            ),
            "max_broker_failures": (
                self.max_broker_failures
            ),
            "can_open_trade": (
                trade_decision["allowed"]
            ),
            "trade_block_reason": (
                trade_decision["reason"]
            ),
            "should_shutdown": (
                shutdown_decision["shutdown"]
            ),
            "shutdown_reason": (
                shutdown_decision["reason"]
            ),
        }


if __name__ == "__main__":
    safety = SafetyManager(
        max_trades_per_day=3,
        max_daily_loss=1000.0,
        max_consecutive_losses=2,
        max_api_failures=3,
        max_broker_failures=2,
    )

    print("Initial status:")
    print(safety.status())

    safety.record_trade_opened()
    safety.record_trade_closed(-300.0)

    safety.record_trade_opened()
    safety.record_trade_closed(-400.0)

    print("\nAfter two losses:")
    print(safety.status())

    safety.enable_kill_switch(
        "Manual safety test."
    )

    print("\nAfter kill switch:")
    print(safety.status())
    
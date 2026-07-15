"""
Controlled integration tests for SafetyManager.

No real Groww orders are placed.
"""

from core.safety_manager import SafetyManager


def test_initial_state() -> None:
    safety = SafetyManager(
        max_trades_per_day=3,
        max_daily_loss=1000.0,
        max_consecutive_losses=2,
        max_api_failures=3,
        max_broker_failures=2,
    )

    decision = safety.can_open_trade()

    assert decision["allowed"] is True
    assert safety.should_shutdown()["shutdown"] is False

    print("Initial safety state passed.")


def test_daily_trade_limit() -> None:
    safety = SafetyManager(
        max_trades_per_day=3,
    )

    safety.record_trade_opened()
    safety.record_trade_opened()
    safety.record_trade_opened()

    decision = safety.can_open_trade()

    assert decision["allowed"] is False
    assert "trade limit" in decision["reason"].lower()

    print("Daily trade limit passed.")


def test_consecutive_loss_breaker() -> None:
    safety = SafetyManager(
        max_consecutive_losses=2,
    )

    safety.record_trade_closed(-200.0)
    safety.record_trade_closed(-300.0)

    decision = safety.can_open_trade()

    assert decision["allowed"] is False
    assert "consecutive" in decision["reason"].lower()
    assert safety.should_shutdown()["shutdown"] is False

    print("Consecutive-loss breaker passed.")


def test_daily_loss_shutdown() -> None:
    safety = SafetyManager(
        max_daily_loss=1000.0,
    )

    safety.record_trade_closed(-400.0)
    safety.record_trade_closed(-650.0)

    trade_decision = safety.can_open_trade()
    shutdown_decision = safety.should_shutdown()

    assert trade_decision["allowed"] is False
    assert shutdown_decision["shutdown"] is True
    assert "loss" in shutdown_decision["reason"].lower()

    print("Daily-loss shutdown passed.")


def test_kill_switch() -> None:
    safety = SafetyManager()

    safety.enable_kill_switch(
        "Manual emergency test."
    )

    trade_decision = safety.can_open_trade()
    shutdown_decision = safety.should_shutdown()

    assert trade_decision["allowed"] is False
    assert shutdown_decision["shutdown"] is True
    assert (
        shutdown_decision["reason"]
        == "Manual emergency test."
    )

    safety.disable_kill_switch()

    assert safety.can_open_trade()["allowed"] is True

    print("Kill-switch test passed.")


def test_api_failure_limit() -> None:
    safety = SafetyManager(
        max_api_failures=3,
    )

    safety.record_api_failure()
    safety.record_api_failure()
    safety.record_api_failure()

    assert safety.can_open_trade()["allowed"] is False
    assert safety.should_shutdown()["shutdown"] is True

    safety.clear_api_failures()

    assert safety.can_open_trade()["allowed"] is True

    print("API-failure protection passed.")


def test_broker_failure_limit() -> None:
    safety = SafetyManager(
        max_broker_failures=2,
    )

    safety.record_broker_failure()
    safety.record_broker_failure()

    assert safety.can_open_trade()["allowed"] is False
    assert safety.should_shutdown()["shutdown"] is True

    safety.clear_broker_failures()

    assert safety.can_open_trade()["allowed"] is True

    print("Broker-failure protection passed.")


def main() -> None:
    print("=" * 60)
    print("SAFETY MANAGER INTEGRATION TESTS")
    print("=" * 60)

    test_initial_state()
    test_daily_trade_limit()
    test_consecutive_loss_breaker()
    test_daily_loss_shutdown()
    test_kill_switch()
    test_api_failure_limit()
    test_broker_failure_limit()

    print("\nAll SafetyManager tests passed.")


if __name__ == "__main__":
    main()
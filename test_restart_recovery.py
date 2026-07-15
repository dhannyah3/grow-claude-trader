"""
Restart recovery integration test.

This verifies that:
- an open paper position is persisted;
- PaperTrader restores it after restart;
- TradeLifecycle is rebuilt;
- the same symbol is not opened twice.

No real Groww order is placed.
"""

from pathlib import Path

from core.paper_trader import PaperTrader
from core.trade_lifecycle import TradeLifecycle


TRADES_FILE = Path(
    "logs/test_restart_recovery_trades.csv"
)

POSITIONS_FILE = Path(
    "logs/test_restart_recovery_positions.json"
)

JOURNAL_FILE = Path(
    "logs/test_restart_recovery_journal.json"
)


def remove_old_test_files() -> None:
    for path in (
        TRADES_FILE,
        POSITIONS_FILE,
        JOURNAL_FILE,
    ):
        if path.exists():
            path.unlink()


def rebuild_lifecycle(
    trader: PaperTrader,
) -> TradeLifecycle:
    lifecycle = TradeLifecycle()

    for symbol, position in (
        trader.open_positions.items()
    ):
        metadata = position.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        opened = lifecycle.open_trade(
            symbol=symbol,
            strategy=str(
                metadata.get(
                    "strategy",
                    "UNKNOWN",
                )
            ),
            quantity=int(
                position["quantity"]
            ),
            entry_price=float(
                position["entry_price"]
            ),
            stop_loss=float(
                position["stop_loss"]
            ),
            target=float(
                position["target"]
            ),
            metadata=metadata,
        )

        assert opened is True

    return lifecycle


def main() -> None:
    print("=" * 60)
    print("RESTART RECOVERY INTEGRATION TEST")
    print("=" * 60)

    remove_old_test_files()

    # ---------------------------------------------
    # First runtime
    # ---------------------------------------------

    first_trader = PaperTrader(
        starting_balance=100000.0,
        log_file=str(TRADES_FILE),
        positions_file=str(
            POSITIONS_FILE
        ),
        journal_file=str(
            JOURNAL_FILE
        ),
    )

    opened = first_trader.open_trade(
        symbol="RELIANCE",
        quantity=10,
        entry_price=1500.0,
        stop_loss=1485.0,
        target=1530.0,
        metadata={
            "strategy": "ORB_BREAKOUT",
            "market_condition": "TRENDING",
            "sector": "ENERGY",
            "internal_order_id": (
                "TEST-BUY-ORDER-001"
            ),
            "order_status": "SIMULATED",
            "paper_trade": True,
        },
    )

    assert opened is True
    assert (
        first_trader.get_open_position(
            "RELIANCE"
        )
        is not None
    )
    assert POSITIONS_FILE.exists()

    print(
        "First runtime: position opened "
        "and persisted."
    )

    # ---------------------------------------------
    # Simulated restart
    # ---------------------------------------------

    restarted_trader = PaperTrader(
        starting_balance=100000.0,
        log_file=str(TRADES_FILE),
        positions_file=str(
            POSITIONS_FILE
        ),
        journal_file=str(
            JOURNAL_FILE
        ),
    )

    restored_position = (
        restarted_trader
        .get_open_position(
            "RELIANCE"
        )
    )

    assert restored_position is not None
    assert restored_position[
        "quantity"
    ] == 10
    assert restored_position[
        "entry_price"
    ] == 1500.0
    assert restored_position[
        "stop_loss"
    ] == 1485.0
    assert restored_position[
        "target"
    ] == 1530.0

    metadata = restored_position.get(
        "metadata",
        {},
    )

    assert (
        metadata.get(
            "internal_order_id"
        )
        == "TEST-BUY-ORDER-001"
    )

    print(
        "Restarted runtime: paper "
        "position restored."
    )

    # ---------------------------------------------
    # Rebuild lifecycle
    # ---------------------------------------------

    lifecycle = rebuild_lifecycle(
        restarted_trader
    )

    assert lifecycle.has_open_trade(
        "RELIANCE"
    )

    print(
        "Restarted runtime: lifecycle "
        "state rebuilt."
    )

    # ---------------------------------------------
    # Duplicate-order protection
    # ---------------------------------------------

    duplicate_opened = (
        restarted_trader.open_trade(
            symbol="RELIANCE",
            quantity=10,
            entry_price=1501.0,
            stop_loss=1486.0,
            target=1531.0,
            metadata={
                "strategy": (
                    "ORB_BREAKOUT"
                ),
                "paper_trade": True,
            },
        )
    )

    assert duplicate_opened is False
    assert len(
        restarted_trader.open_positions
    ) == 1

    print(
        "Duplicate protection: second "
        "position was rejected."
    )

    print(
        "\nRESTART RECOVERY "
        "integration test passed."
    )


if __name__ == "__main__":
    main()
    
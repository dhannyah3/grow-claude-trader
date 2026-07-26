from decision.position_sizer import PositionSizer


def main():
    sizer = PositionSizer()

    result = sizer.size_position(
        symbol="ICICIBANK",
        allocation_cash=40000,
        entry_price=1425.50,
        stop_loss=1415.50,
        target_price=1445.50,
    )

    print("\n===== POSITION SIZE RESULT =====\n")

    print(result.to_dict())

    assert result.approved is True
    assert result.final_quantity > 0
    assert result.position_value <= result.allocation_cash

    summary = sizer.summarize([result])

    print("\n===== SUMMARY =====\n")

    print(summary.to_dict())

    print("\n✅ Position sizer test passed.")


if __name__ == "__main__":
    main()
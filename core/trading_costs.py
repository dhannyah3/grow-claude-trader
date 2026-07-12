from typing import Dict


def calculate_intraday_costs(
    buy_price: float,
    sell_price: float,
    quantity: int,
    brokerage_rate: float = 0.0003,
    brokerage_cap_per_order: float = 20.0,
) -> Dict[str, float]:
    """
    Estimate Indian equity intraday trading charges.

    The rates are configurable and should be checked against
    the broker's latest published charges before live use.
    """

    buy_turnover = buy_price * quantity
    sell_turnover = sell_price * quantity
    total_turnover = buy_turnover + sell_turnover

    buy_brokerage = min(
        buy_turnover * brokerage_rate,
        brokerage_cap_per_order,
    )

    sell_brokerage = min(
        sell_turnover * brokerage_rate,
        brokerage_cap_per_order,
    )

    brokerage = buy_brokerage + sell_brokerage

    # Configurable estimates
    stt = sell_turnover * 0.00025
    exchange_charges = total_turnover * 0.0000297
    sebi_charges = total_turnover * 0.000001
    stamp_duty = buy_turnover * 0.00003

    gst = 0.18 * (
        brokerage
        + exchange_charges
        + sebi_charges
    )

    total_costs = (
        brokerage
        + stt
        + exchange_charges
        + sebi_charges
        + stamp_duty
        + gst
    )

    return {
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "exchange_charges": round(
            exchange_charges,
            2,
        ),
        "sebi_charges": round(
            sebi_charges,
            2,
        ),
        "stamp_duty": round(
            stamp_duty,
            2,
        ),
        "gst": round(gst, 2),
        "total_costs": round(
            total_costs,
            2,
        ),
    }
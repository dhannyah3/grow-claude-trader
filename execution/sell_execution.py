from typing import Any, Dict, Optional

def execute_paper_sell(
    controller,
    symbol: str,
    quantity: int,
    price: float,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    Execute a SELL through the execution layer.

    In paper mode this registers the simulated
    execution before the PaperTrader closes
    the position.
    """

    metadata = metadata or {}

    return controller.execute_sell(
        symbol=symbol,
        quantity=quantity,
        price=price,
        metadata={
            **metadata,
            "exit_reason": reason,
            "paper_trade": True,
        },
    )
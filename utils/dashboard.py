import os
from datetime import datetime


class Dashboard:

    @staticmethod
    def clear():
        os.system("clear")

    @staticmethod
    def show(
        balance,
        pnl,
        positions,
        watchlist,
    ):
        Dashboard.clear()

        print("=" * 60)
        print("        GROWW AI PAPER TRADER")
        print("=" * 60)

        print(f"Time          : {datetime.now().strftime('%H:%M:%S')}")
        print(f"Balance       : ₹{balance:,.2f}")
        print(f"Today's P&L   : ₹{pnl:,.2f}")
        print(f"Open Positions: {len(positions)}")

        print("\nOPEN POSITIONS")
        print("-" * 60)

        if not positions:
            print("No open positions.")

        for symbol, pos in positions.items():
            print(
                f"{symbol:12}"
                f"Qty:{pos['quantity']:4}"
                f" Entry: ₹{pos['entry_price']:.2f}"
                f" SL: ₹{pos['stop_loss']:.2f}"
                f" Target: ₹{pos['target']:.2f}"
            )

        print("\nWATCHLIST")
        print("-" * 60)

        for stock in watchlist:
            print(stock)

        print("=" * 60)
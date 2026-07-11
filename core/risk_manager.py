from typing import Dict


class RiskManager:
    def __init__(
        self,
        account_balance: float = 100000.0,
        risk_per_trade_percent: float = 0.5,
        max_daily_loss_percent: float = 2.0,
        max_position_percent: float = 20.0,
        max_open_positions: int = 2,
    ):
        self.account_balance = float(account_balance)
        self.risk_per_trade_percent = float(risk_per_trade_percent)
        self.max_daily_loss_percent = float(max_daily_loss_percent)
        self.max_position_percent = float(max_position_percent)
        self.max_open_positions = int(max_open_positions)

    def risk_amount_per_trade(self) -> float:
        return (
            self.account_balance
            * self.risk_per_trade_percent
            / 100
        )

    def maximum_daily_loss(self) -> float:
        return (
            self.account_balance
            * self.max_daily_loss_percent
            / 100
        )

    def maximum_position_value(self) -> float:
        return (
            self.account_balance
            * self.max_position_percent
            / 100
        )

    def calculate_quantity(
        self,
        entry_price: float,
        stop_loss: float,
    ) -> int:
        entry_price = float(entry_price)
        stop_loss = float(stop_loss)

        risk_per_share = abs(entry_price - stop_loss)

        if entry_price <= 0 or risk_per_share <= 0:
            return 0

        quantity_by_risk = int(
            self.risk_amount_per_trade()
            / risk_per_share
        )

        quantity_by_position_limit = int(
            self.maximum_position_value()
            / entry_price
        )

        return max(
            0,
            min(
                quantity_by_risk,
                quantity_by_position_limit,
            ),
        )

    def can_open_trade(
        self,
        daily_realized_pnl: float,
        current_open_positions: int,
    ) -> bool:
        if current_open_positions >= self.max_open_positions:
            print("Trade blocked: maximum open positions reached.")
            return False

        if daily_realized_pnl <= -self.maximum_daily_loss():
            print("Trade blocked: maximum daily loss reached.")
            return False

        return True

    def trade_plan(
        self,
        entry_price: float,
        stop_loss: float,
        target_price: float,
    ) -> Dict[str, float]:
        quantity = self.calculate_quantity(
            entry_price=entry_price,
            stop_loss=stop_loss,
        )

        risk_per_share = abs(entry_price - stop_loss)
        reward_per_share = abs(target_price - entry_price)

        risk_reward_ratio = (
            reward_per_share / risk_per_share
            if risk_per_share > 0
            else 0
        )

        return {
            "entry_price": round(entry_price, 2),
            "stop_loss": round(stop_loss, 2),
            "target_price": round(target_price, 2),
            "quantity": quantity,
            "risk_amount": round(
                quantity * risk_per_share,
                2,
            ),
            "position_value": round(
                quantity * entry_price,
                2,
            ),
            "risk_reward_ratio": round(
                risk_reward_ratio,
                2,
            ),
        }


if __name__ == "__main__":
    risk_manager = RiskManager()

    plan = risk_manager.trade_plan(
        entry_price=1300.0,
        stop_loss=1290.0,
        target_price=1320.0,
    )

    print("\n===== PAPER TRADE RISK PLAN =====\n")

    for key, value in plan.items():
        print(f"{key}: {value}")
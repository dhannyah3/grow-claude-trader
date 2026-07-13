from strategies.orb_breakout import ORBBreakoutStrategy
from strategies.vwap_pullback import VWAPPullbackStrategy


class StrategyFactory:
    """
    Creates strategy instances by name.
    """

    _strategies = {
        "ORB_BREAKOUT": ORBBreakoutStrategy,
        "VWAP_PULLBACK": VWAPPullbackStrategy,
    }

    @classmethod
    def get(
        cls,
        strategy_name: str,
    ):
        normalized_name = strategy_name.upper()

        if normalized_name not in cls._strategies:
            raise ValueError(
                f"Unknown strategy: {normalized_name}"
            )

        strategy_class = cls._strategies[
            normalized_name
        ]

        return strategy_class()
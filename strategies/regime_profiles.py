from copy import deepcopy
from typing import Any, Dict

from strategies.strategy_profiles import (
    get_strategy_profile,
)


REGIME_OVERRIDES: Dict[
    str,
    Dict[str, Any],
] = {
    "TRENDING": {
        "atr_multiplier": 3.0,
        "max_hold_minutes": 90,
        "profit_targets": [
            {
                "r": 2.0,
                "fraction": 0.25,
            },
            {
                "r": 4.0,
                "fraction": 0.25,
            },
            {
                "r": 6.0,
                "fraction": 0.25,
            },
        ],
    },

    "RANGE_BOUND": {
        "atr_multiplier": 1.5,
        "max_hold_minutes": 40,
        "max_wait_for_1r": 10,
        "max_no_new_high_minutes": 12,
        "profit_targets": [
            {
                "r": 1.5,
                "fraction": 0.25,
            },
            {
                "r": 2.0,
                "fraction": 0.25,
            },
            {
                "r": 3.0,
                "fraction": 0.25,
            },
        ],
    },

    "HIGH_VOLATILITY": {
        "atr_multiplier": 3.5,
        "max_hold_minutes": 90,
    },

    "LOW_VOLATILITY": {
        "atr_multiplier": 1.2,
        "max_hold_minutes": 60,
    },
}


def get_regime_profile(
    strategy: str,
    regime: str,
) -> Dict[str, Any]:
    """
    Apply market-regime overrides to the
    selected strategy's base lifecycle profile.
    """
    base_profile = get_strategy_profile(
        strategy
    )

    normalized_regime = str(
        regime
    ).strip().upper()

    override = REGIME_OVERRIDES.get(
        normalized_regime,
        {},
    )

    final_profile = deepcopy(
        base_profile
    )

    for key, value in override.items():
        final_profile[key] = deepcopy(
            value
        )

    return final_profile


if __name__ == "__main__":
    print(
        "\nORB + TRENDING\n"
    )

    print(
        get_regime_profile(
            "ORB_BREAKOUT",
            "TRENDING",
        )
    )

    print(
        "\nORB + RANGE_BOUND\n"
    )

    print(
        get_regime_profile(
            "ORB_BREAKOUT",
            "RANGE_BOUND",
        )
    )

    print(
        "\nVWAP + HIGH_VOLATILITY\n"
    )

    print(
        get_regime_profile(
            "VWAP_PULLBACK",
            "HIGH_VOLATILITY",
        )
    )

    print(
        "\nUNKNOWN REGIME\n"
    )

    print(
        get_regime_profile(
            "ORB_BREAKOUT",
            "UNKNOWN",
        )
    )

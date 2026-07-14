from copy import deepcopy
from typing import Any, Dict


DEFAULT_PROFILE: Dict[str, Any] = {
    "atr_multiplier": 2.0,
    "max_hold_minutes": 90,
    "max_wait_for_1r": 15,
    "max_no_new_high_minutes": 20,
    "profit_targets": [
        {
            "r": 2.0,
            "fraction": 0.25,
        },
        {
            "r": 3.0,
            "fraction": 0.25,
        },
        {
            "r": 4.0,
            "fraction": 0.25,
        },
    ],
}


STRATEGY_PROFILES: Dict[
    str,
    Dict[str, Any],
] = {
    "ORB_BREAKOUT": {
        "atr_multiplier": 2.5,
        "max_hold_minutes": 75,
        "max_wait_for_1r": 15,
        "max_no_new_high_minutes": 20,
        "profit_targets": [
            {
                "r": 2.0,
                "fraction": 0.25,
            },
            {
                "r": 3.0,
                "fraction": 0.25,
            },
            {
                "r": 5.0,
                "fraction": 0.25,
            },
        ],
    },

    "VWAP_PULLBACK": {
        "atr_multiplier": 1.5,
        "max_hold_minutes": 45,
        "max_wait_for_1r": 12,
        "max_no_new_high_minutes": 15,
        "profit_targets": [
            {
                "r": 1.5,
                "fraction": 0.25,
            },
            {
                "r": 2.5,
                "fraction": 0.25,
            },
            {
                "r": 3.5,
                "fraction": 0.25,
            },
        ],
    },
}


def get_strategy_profile(
    strategy: str,
) -> Dict[str, Any]:
    """
    Return a safe copy of the selected strategy profile.

    Unknown strategy names automatically use the
    default lifecycle configuration.
    """
    normalized_strategy = str(
        strategy
    ).strip().upper()

    profile = STRATEGY_PROFILES.get(
        normalized_strategy,
        DEFAULT_PROFILE,
    )

    return deepcopy(
        profile
    )


def validate_strategy_profile(
    profile: Dict[str, Any],
) -> bool:
    """
    Validate the minimum required strategy-profile
    structure before it is used by TradeLifecycle.
    """
    if not isinstance(
        profile,
        dict,
    ):
        return False

    required_numeric_fields = [
        "atr_multiplier",
        "max_hold_minutes",
        "max_wait_for_1r",
        "max_no_new_high_minutes",
    ]

    for field in required_numeric_fields:
        value = profile.get(
            field
        )

        if not isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            return False

        if value <= 0:
            return False

    profit_targets = profile.get(
        "profit_targets"
    )

    if not isinstance(
        profit_targets,
        list,
    ):
        return False

    if not profit_targets:
        return False

    total_fraction = 0.0

    for target in profit_targets:
        if not isinstance(
            target,
            dict,
        ):
            return False

        r_multiple = target.get(
            "r"
        )

        fraction = target.get(
            "fraction"
        )

        if not isinstance(
            r_multiple,
            (
                int,
                float,
            ),
        ):
            return False

        if not isinstance(
            fraction,
            (
                int,
                float,
            ),
        ):
            return False

        if r_multiple <= 0:
            return False

        if not (
            0 < fraction < 1
        ):
            return False

        total_fraction += float(
            fraction
        )

    if total_fraction >= 1.0:
        return False

    return True


def validate_all_profiles() -> Dict[
    str,
    bool,
]:
    """
    Validate every registered strategy profile
    including the default profile.
    """
    validation_results = {
        "DEFAULT_PROFILE": (
            validate_strategy_profile(
                DEFAULT_PROFILE
            )
        )
    }

    for strategy, profile in (
        STRATEGY_PROFILES.items()
    ):
        validation_results[
            strategy
        ] = validate_strategy_profile(
            profile
        )

    return validation_results


if __name__ == "__main__":
    print(
        "\nORB PROFILE:"
    )

    print(
        get_strategy_profile(
            "ORB_BREAKOUT"
        )
    )

    print(
        "\nVWAP PROFILE:"
    )

    print(
        get_strategy_profile(
            "VWAP_PULLBACK"
        )
    )

    print(
        "\nDEFAULT PROFILE:"
    )

    print(
        get_strategy_profile(
            "UNKNOWN_STRATEGY"
        )
    )

    print(
        "\nPROFILE VALIDATION:"
    )

    print(
        validate_all_profiles()
    )
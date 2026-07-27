"""
Live Snapshot Builder.

Converts live scanner results into the canonical
MarketIntelligenceSnapshot consumed by StockSelector and the
portfolio decision pipeline.
"""

from typing import Any, Dict, List, Mapping

import pandas as pd

from market_intelligence.intelligence_manager import (
    MarketIntelligenceSnapshot,
)


class LiveSnapshotBuilder:
    """
    Build ranked relative-strength and sector-strength intelligence
    from live scanner results.
    """

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip().upper()

    @staticmethod
    def _normalize_sector(value: Any) -> str:
        normalized = str(
            value or "UNKNOWN"
        ).strip().upper()

        return normalized or "UNKNOWN"

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError):
            return float(default)

        if converted != converted:
            return float(default)

        return converted

    @classmethod
    def _extract_relative_strength(
        cls,
        result: Mapping[str, Any],
    ) -> float:
        """
        Read relative strength from scanner output.

        Strategy score is used only as a temporary fallback when the
        scanner does not yet provide a dedicated relative-strength value.
        """

        return cls._safe_float(
            result.get(
                "relative_strength",
                result.get(
                    "strategy_score",
                    result.get(
                        "score",
                        0.0,
                    ),
                ),
            )
        )

    @staticmethod
    def _percentile(
        position: int,
        total: int,
    ) -> float:
        """
        Convert a one-based descending rank into a percentile.

        Rank 1 receives 100. Lower-ranked items receive progressively
        lower percentiles.
        """

        if total <= 1:
            return 100.0

        return round(
            (
                (total - position)
                / (total - 1)
            )
            * 100.0,
            2,
        )

    @classmethod
    def build(
        cls,
        scan_results: List[Dict[str, Any]],
    ) -> MarketIntelligenceSnapshot:
        """
        Build the canonical intelligence snapshot.

        The scanner results are ranked by relative strength. Sector
        strength is derived from the average relative strength of the
        stocks belonging to each sector.
        """

        prepared_stocks: List[
            Dict[str, Any]
        ] = []

        for result in scan_results:
            if not isinstance(result, Mapping):
                continue

            symbol = cls._normalize_symbol(
                result.get("symbol")
            )

            if not symbol:
                continue

            sector = cls._normalize_sector(
                result.get("sector")
            )

            relative_return = (
                cls._extract_relative_strength(
                    result
                )
            )

            prepared_stocks.append(
                {
                    "symbol": symbol,
                    "sector": sector,
                    "relative_return": (
                        relative_return
                    ),
                }
            )

        prepared_stocks.sort(
            key=lambda item: (
                item["relative_return"]
            ),
            reverse=True,
        )

        relative_strength: List[
            Dict[str, object]
        ] = []

        total_stocks = len(prepared_stocks)

        for position, item in enumerate(
            prepared_stocks,
            start=1,
        ):
            relative_strength.append(
                {
                    "symbol": item["symbol"],
                    "rank": position,
                    "percentile_rank": (
                        cls._percentile(
                            position,
                            total_stocks,
                        )
                    ),
                    "relative_return": (
                        item["relative_return"]
                    ),
                }
            )

        sector_members: Dict[
            str,
            List[Dict[str, Any]],
        ] = {}

        for item in prepared_stocks:
            sector_members.setdefault(
                item["sector"],
                [],
            ).append(item)

        prepared_sectors: List[
            Dict[str, Any]
        ] = []

        for sector, members in (
            sector_members.items()
        ):
            average_return = (
                sum(
                    member[
                        "relative_return"
                    ]
                    for member in members
                )
                / len(members)
            )

            ordered_members = sorted(
                members,
                key=lambda member: (
                    member[
                        "relative_return"
                    ]
                ),
                reverse=True,
            )

            prepared_sectors.append(
                {
                    "sector": sector,
                    "sector_relative_return": (
                        average_return
                    ),
                    "strongest_stock": (
                        ordered_members[0][
                            "symbol"
                        ]
                    ),
                    "weakest_stock": (
                        ordered_members[-1][
                            "symbol"
                        ]
                    ),
                }
            )

        prepared_sectors.sort(
            key=lambda item: (
                item[
                    "sector_relative_return"
                ]
            ),
            reverse=True,
        )

        sector_strength: List[
            Dict[str, object]
        ] = []

        total_sectors = len(
            prepared_sectors
        )

        for position, item in enumerate(
            prepared_sectors,
            start=1,
        ):
            percentile = cls._percentile(
                position,
                total_sectors,
            )

            if percentile >= 70.0:
                classification = "LEADING"
            elif percentile <= 30.0:
                classification = "LAGGING"
            else:
                classification = "NEUTRAL"

            sector_strength.append(
                {
                    "sector": item["sector"],
                    "rank": position,
                    "percentile_rank": (
                        percentile
                    ),
                    "sector_relative_return": (
                        item[
                            "sector_relative_return"
                        ]
                    ),
                    "classification": (
                        classification
                    ),
                    "strongest_stock": (
                        item[
                            "strongest_stock"
                        ]
                    ),
                    "weakest_stock": (
                        item[
                            "weakest_stock"
                        ]
                    ),
                }
            )

        market_regime = (
            cls._build_market_regime(
                scan_results
            )
        )

        return MarketIntelligenceSnapshot(
            timestamp=pd.Timestamp.now(
                tz="Asia/Kolkata"
            ),
            benchmark_returns={},
            market_regime=market_regime,
            relative_strength=(
                relative_strength
            ),
            sector_strength=sector_strength,
            symbols_analyzed=total_stocks,
            sectors_analyzed=total_sectors,
            metadata={
                "source": (
                    "live_snapshot_builder"
                ),
                "relative_strength_fallback": (
                    "strategy_score"
                ),
            },
        )

    @classmethod
    def _build_market_regime(
        cls,
        scan_results: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, object]:
        """
        Extract a broad market regime from available scanner results.
        """

        for result in scan_results:
            if not isinstance(result, Mapping):
                continue

            regime_value = result.get(
                "market_regime"
            )

            if isinstance(
                regime_value,
                Mapping,
            ):
                regime = dict(
                    regime_value
                )

                regime.setdefault(
                    "regime",
                    regime.get(
                        "trend",
                        "UNKNOWN",
                    ),
                )

                return regime

            if regime_value:
                normalized = str(
                    regime_value
                ).strip().upper()

                return {
                    "regime": normalized,
                    "trend": normalized,
                    "volatility": (
                        "UNKNOWN"
                    ),
                }

        return {
            "regime": "UNKNOWN",
            "trend": "UNKNOWN",
            "volatility": "UNKNOWN",
        }
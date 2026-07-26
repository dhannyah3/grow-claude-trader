"""
Stock selection for the trading decision layer.

The StockSelector combines:

- Individual relative strength
- Sector strength
- Sector classification
- Broad market regime

It produces a ranked list of symbols for downstream strategy
selection, risk allocation, and execution.
"""

from dataclasses import asdict, dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Union

from market_intelligence.intelligence_manager import (
    MarketIntelligenceSnapshot,
)


@dataclass(frozen=True)
class StockSelectionResult:
    """
    Final stock-selection result for one symbol.
    """

    symbol: str
    sector: str
    score: float
    confidence: int
    relative_strength_rank: int
    relative_strength_percentile: float
    relative_strength_score: float
    relative_return: float
    sector_rank: Optional[int]
    sector_percentile: Optional[float]
    sector_strength_score: Optional[float]
    sector_relative_return: Optional[float]
    sector_classification: str
    market_regime: str
    selected: bool
    reasons: List[str]

    def to_dict(
        self,
    ) -> Dict[str, object]:
        """
        Convert the result into a serializable dictionary.
        """

        return asdict(self)


class StockSelector:
    """
    Rank stocks using unified market-intelligence data.

    Parameters
    ----------
    minimum_score:
        Minimum score required for a candidate to be marked selected.

    maximum_candidates:
        Optional maximum number of selected candidates. The complete
        ranking is still returned, but only the highest-ranked eligible
        candidates are marked selected.

    relative_strength_weight:
        Maximum contribution from individual relative strength.

    sector_strength_weight:
        Maximum contribution from sector strength.

    market_regime_weight:
        Maximum contribution from broad market conditions.

    classification_weight:
        Maximum contribution from sector classification.

    stock_position_weight:
        Maximum contribution from strongest/weakest sector position.
    """

    def __init__(
        self,
        minimum_score: float = 55.0,
        maximum_candidates: Optional[int] = 5,
        relative_strength_weight: float = 40.0,
        sector_strength_weight: float = 25.0,
        market_regime_weight: float = 20.0,
        classification_weight: float = 10.0,
        stock_position_weight: float = 5.0,
    ) -> None:
        self.minimum_score = float(
            minimum_score
        )

        self.maximum_candidates = (
            int(maximum_candidates)
            if maximum_candidates is not None
            else None
        )

        self.relative_strength_weight = float(
            relative_strength_weight
        )

        self.sector_strength_weight = float(
            sector_strength_weight
        )

        self.market_regime_weight = float(
            market_regime_weight
        )

        self.classification_weight = float(
            classification_weight
        )

        self.stock_position_weight = float(
            stock_position_weight
        )

        self._validate_configuration()

    def _validate_configuration(
        self,
    ) -> None:
        """
        Validate selector configuration.
        """

        if not (
            0.0
            <= self.minimum_score
            <= 100.0
        ):
            raise ValueError(
                "minimum_score must be between 0 and 100."
            )

        if (
            self.maximum_candidates is not None
            and self.maximum_candidates <= 0
        ):
            raise ValueError(
                "maximum_candidates must be positive "
                "or None."
            )

        weights = [
            self.relative_strength_weight,
            self.sector_strength_weight,
            self.market_regime_weight,
            self.classification_weight,
            self.stock_position_weight,
        ]

        if any(
            weight < 0
            for weight in weights
        ):
            raise ValueError(
                "Selection weights cannot be negative."
            )

        total_weight = sum(
            weights
        )

        if total_weight <= 0:
            raise ValueError(
                "Selection weights must total more than zero."
            )

    def configuration(
        self,
    ) -> Dict[str, object]:
        """
        Return active selector configuration.
        """

        return {
            "minimum_score": self.minimum_score,
            "maximum_candidates": (
                self.maximum_candidates
            ),
            "weights": {
                "relative_strength": (
                    self.relative_strength_weight
                ),
                "sector_strength": (
                    self.sector_strength_weight
                ),
                "market_regime": (
                    self.market_regime_weight
                ),
                "classification": (
                    self.classification_weight
                ),
                "stock_position": (
                    self.stock_position_weight
                ),
            },
        }

    @staticmethod
    def _normalize_symbol(
        symbol: object,
    ) -> str:
        """
        Normalize a trading symbol.
        """

        return str(
            symbol
        ).strip().upper()

    @staticmethod
    def _normalize_sector(
        sector: object,
    ) -> str:
        """
        Normalize a sector name.
        """

        normalized = str(
            sector
        ).strip().upper()

        return normalized or "UNKNOWN"

    @staticmethod
    def _safe_float(
        value: object,
        default: float = 0.0,
    ) -> float:
        """
        Convert a value to float safely.
        """

        try:
            converted = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return float(
                default
            )

        if converted != converted:
            return float(
                default
            )

        return converted

    @staticmethod
    def _safe_int(
        value: object,
        default: int = 0,
    ) -> int:
        """
        Convert a value to integer safely.
        """

        try:
            return int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return int(
                default
            )

    @staticmethod
    def _clamp(
        value: float,
        minimum: float = 0.0,
        maximum: float = 100.0,
    ) -> float:
        """
        Restrict a number to the requested range.
        """

        return max(
            minimum,
            min(
                float(value),
                maximum,
            ),
        )

    def _snapshot_to_dict(
        self,
        snapshot: Union[
            MarketIntelligenceSnapshot,
            Mapping[str, object],
        ],
    ) -> Dict[str, object]:
        """
        Normalize dataclass and dictionary snapshot inputs.
        """

        if isinstance(
            snapshot,
            MarketIntelligenceSnapshot,
        ):
            return snapshot.to_dict()

        if isinstance(
            snapshot,
            Mapping,
        ):
            return dict(
                snapshot
            )

        raise TypeError(
            "snapshot must be a "
            "MarketIntelligenceSnapshot or mapping."
        )

    def _build_sector_lookup(
        self,
        sector_strength: Sequence[
            Mapping[str, object]
        ],
    ) -> Dict[str, Dict[str, object]]:
        """
        Build a sector-name to sector-result lookup.
        """

        lookup: Dict[
            str,
            Dict[str, object],
        ] = {}

        for result in sector_strength:
            if not isinstance(
                result,
                Mapping,
            ):
                continue

            sector = self._normalize_sector(
                result.get(
                    "sector",
                    "UNKNOWN",
                )
            )

            lookup[sector] = dict(
                result
            )

        return lookup

    def _market_regime_details(
        self,
        market_regime: Mapping[
            str,
            object,
        ],
    ) -> Dict[str, str]:
        """
        Extract normalized regime values.

        Different engines may use slightly different field names, so
        this method safely supports common alternatives.
        """

        primary_regime = str(
            market_regime.get(
                "regime",
                market_regime.get(
                    "trend",
                    market_regime.get(
                        "classification",
                        "UNKNOWN",
                    ),
                ),
            )
        ).strip().upper()

        trend = str(
            market_regime.get(
                "trend",
                primary_regime,
            )
        ).strip().upper()

        volatility = str(
            market_regime.get(
                "volatility",
                "UNKNOWN",
            )
        ).strip().upper()

        return {
            "regime": primary_regime,
            "trend": trend,
            "volatility": volatility,
        }

    def _score_relative_strength(
        self,
        result: Mapping[
            str,
            object,
        ],
        reasons: List[str],
    ) -> float:
        """
        Score individual stock relative strength.
        """

        percentile = self._clamp(
            self._safe_float(
                result.get(
                    "percentile_rank",
                    0.0,
                )
            )
        )

        rank = self._safe_int(
            result.get(
                "rank",
                0,
            )
        )

        relative_return = self._safe_float(
            result.get(
                "relative_return",
                0.0,
            )
        )

        contribution = (
            percentile
            / 100.0
            * self.relative_strength_weight
        )

        if rank == 1:
            reasons.append(
                "Top-ranked stock by relative strength."
            )
        elif 0 < rank <= 3:
            reasons.append(
                "Stock is among the top three "
                "relative-strength candidates."
            )
        elif percentile >= 70.0:
            reasons.append(
                "Stock has strong relative-strength "
                "percentile."
            )
        elif percentile <= 30.0:
            reasons.append(
                "Stock has weak relative strength."
            )

        if relative_return > 0:
            reasons.append(
                "Stock is outperforming the benchmark."
            )
        elif relative_return < 0:
            reasons.append(
                "Stock is underperforming the benchmark."
            )

        return contribution

    def _score_sector_strength(
        self,
        sector_result: Optional[
            Mapping[str, object]
        ],
        reasons: List[str],
    ) -> float:
        """
        Score the stock's sector ranking.
        """

        if not sector_result:
            reasons.append(
                "Sector intelligence was unavailable."
            )
            return 0.0

        percentile = self._clamp(
            self._safe_float(
                sector_result.get(
                    "percentile_rank",
                    0.0,
                )
            )
        )

        rank = self._safe_int(
            sector_result.get(
                "rank",
                0,
            )
        )

        contribution = (
            percentile
            / 100.0
            * self.sector_strength_weight
        )

        if rank == 1:
            reasons.append(
                "Stock belongs to the strongest sector."
            )
        elif 0 < rank <= 3:
            reasons.append(
                "Stock belongs to a highly ranked sector."
            )
        elif percentile <= 30.0:
            reasons.append(
                "Stock belongs to a weak sector."
            )

        return contribution

    def _score_sector_classification(
        self,
        classification: str,
        reasons: List[str],
    ) -> float:
        """
        Score sector classification.
        """

        normalized = str(
            classification
        ).strip().upper()

        if normalized == "LEADING":
            reasons.append(
                "Sector is classified as LEADING."
            )
            return self.classification_weight

        if normalized == "NEUTRAL":
            reasons.append(
                "Sector is classified as NEUTRAL."
            )
            return (
                self.classification_weight
                * 0.50
            )

        if normalized == "LAGGING":
            reasons.append(
                "Sector is classified as LAGGING."
            )
            return 0.0

        reasons.append(
            "Sector classification is unknown."
        )

        return 0.0

    def _score_market_regime(
        self,
        regime_details: Mapping[
            str,
            str,
        ],
        reasons: List[str],
    ) -> float:
        """
        Score broad market conditions.
        """

        regime = str(
            regime_details.get(
                "regime",
                "UNKNOWN",
            )
        ).upper()

        trend = str(
            regime_details.get(
                "trend",
                regime,
            )
        ).upper()

        volatility = str(
            regime_details.get(
                "volatility",
                "UNKNOWN",
            )
        ).upper()

        contribution = 0.0

        bullish_values = {
            "BULLISH",
            "UPTREND",
            "TRENDING",
            "STRONG_UPTREND",
        }

        neutral_values = {
            "NEUTRAL",
            "SIDEWAYS",
            "RANGE_BOUND",
            "RANGING",
            "MIXED",
        }

        bearish_values = {
            "BEARISH",
            "DOWNTREND",
            "STRONG_DOWNTREND",
        }

        combined_values = {
            regime,
            trend,
        }

        if combined_values & bullish_values:
            contribution = (
                self.market_regime_weight
            )
            reasons.append(
                "Broad market regime supports "
                "long momentum trades."
            )

        elif combined_values & neutral_values:
            contribution = (
                self.market_regime_weight
                * 0.50
            )
            reasons.append(
                "Broad market regime is neutral "
                "or range-bound."
            )

        elif combined_values & bearish_values:
            contribution = 0.0
            reasons.append(
                "Broad market regime is unfavorable "
                "for long-only trades."
            )

        else:
            contribution = (
                self.market_regime_weight
                * 0.25
            )
            reasons.append(
                "Broad market regime is unclear."
            )

        if volatility == "HIGH":
            contribution *= 0.75
            reasons.append(
                "High volatility reduced the "
                "market-regime contribution."
            )

        elif volatility == "LOW":
            contribution *= 0.85
            reasons.append(
                "Low volatility slightly reduced "
                "momentum potential."
            )

        return contribution

    def _score_stock_position(
        self,
        symbol: str,
        sector_result: Optional[
            Mapping[str, object]
        ],
        reasons: List[str],
    ) -> float:
        """
        Apply a bonus or penalty based on strongest/weakest stock data.
        """

        if not sector_result:
            return 0.0

        strongest_stock = self._normalize_symbol(
            sector_result.get(
                "strongest_stock",
                "",
            )
        )

        weakest_stock = self._normalize_symbol(
            sector_result.get(
                "weakest_stock",
                "",
            )
        )

        if strongest_stock and symbol == strongest_stock:
            reasons.append(
                "Stock is the strongest constituent "
                "in its sector."
            )
            return self.stock_position_weight

        if weakest_stock and symbol == weakest_stock:
            reasons.append(
                "Stock is the weakest constituent "
                "in its sector."
            )
            return 0.0

        return (
            self.stock_position_weight
            * 0.50
        )

    def _score_stock(
        self,
        relative_result: Mapping[
            str,
            object,
        ],
        sector: str,
        sector_result: Optional[
            Mapping[str, object]
        ],
        regime_details: Mapping[
            str,
            str,
        ],
    ) -> StockSelectionResult:
        """
        Calculate the final score for one stock.
        """

        symbol = self._normalize_symbol(
            relative_result.get(
                "symbol",
                "",
            )
        )

        reasons: List[str] = []

        raw_score = 0.0

        raw_score += (
            self._score_relative_strength(
                result=relative_result,
                reasons=reasons,
            )
        )

        raw_score += (
            self._score_sector_strength(
                sector_result=sector_result,
                reasons=reasons,
            )
        )

        classification = "UNKNOWN"

        if sector_result:
            classification = str(
                sector_result.get(
                    "classification",
                    "UNKNOWN",
                )
            ).upper()

        raw_score += (
            self._score_sector_classification(
                classification=classification,
                reasons=reasons,
            )
        )

        raw_score += (
            self._score_market_regime(
                regime_details=regime_details,
                reasons=reasons,
            )
        )

        raw_score += (
            self._score_stock_position(
                symbol=symbol,
                sector_result=sector_result,
                reasons=reasons,
            )
        )

        total_configured_weight = (
            self.relative_strength_weight
            + self.sector_strength_weight
            + self.market_regime_weight
            + self.classification_weight
            + self.stock_position_weight
        )

        if total_configured_weight <= 0:
            normalized_score = 0.0
        else:
            normalized_score = (
                raw_score
                / total_configured_weight
                * 100.0
            )

        final_score = round(
            self._clamp(
                normalized_score
            ),
            2,
        )

        confidence = int(
            round(
                final_score
            )
        )

        relative_rank = self._safe_int(
            relative_result.get(
                "rank",
                0,
            )
        )

        relative_percentile = self._safe_float(
            relative_result.get(
                "percentile_rank",
                0.0,
            )
        )

        relative_strength_score = (
            self._safe_float(
                relative_result.get(
                    "relative_strength_score",
                    0.0,
                )
            )
        )

        relative_return = self._safe_float(
            relative_result.get(
                "relative_return",
                0.0,
            )
        )

        sector_rank: Optional[int] = None
        sector_percentile: Optional[float] = None
        sector_strength_score: Optional[
            float
        ] = None
        sector_relative_return: Optional[
            float
        ] = None

        if sector_result:
            sector_rank = self._safe_int(
                sector_result.get(
                    "rank",
                    0,
                )
            )

            sector_percentile = (
                self._safe_float(
                    sector_result.get(
                        "percentile_rank",
                        0.0,
                    )
                )
            )

            sector_strength_score = (
                self._safe_float(
                    sector_result.get(
                        "sector_score",
                        0.0,
                    )
                )
            )

            sector_relative_return = (
                self._safe_float(
                    sector_result.get(
                        "relative_return",
                        0.0,
                    )
                )
            )

        return StockSelectionResult(
            symbol=symbol,
            sector=sector,
            score=final_score,
            confidence=confidence,
            relative_strength_rank=relative_rank,
            relative_strength_percentile=round(
                relative_percentile,
                2,
            ),
            relative_strength_score=round(
                relative_strength_score,
                4,
            ),
            relative_return=round(
                relative_return,
                4,
            ),
            sector_rank=sector_rank,
            sector_percentile=(
                round(
                    sector_percentile,
                    2,
                )
                if sector_percentile is not None
                else None
            ),
            sector_strength_score=(
                round(
                    sector_strength_score,
                    4,
                )
                if sector_strength_score is not None
                else None
            ),
            sector_relative_return=(
                round(
                    sector_relative_return,
                    4,
                )
                if sector_relative_return is not None
                else None
            ),
            sector_classification=classification,
            market_regime=str(
                regime_details.get(
                    "regime",
                    "UNKNOWN",
                )
            ),
            selected=False,
            reasons=reasons,
        )

    def select(
        self,
        snapshot: Union[
            MarketIntelligenceSnapshot,
            Mapping[str, object],
        ],
        sector_map: Mapping[
            str,
            str,
        ],
    ) -> List[StockSelectionResult]:
        """
        Rank all stocks and mark eligible candidates as selected.
        """

        if not sector_map:
            raise ValueError(
                "sector_map cannot be empty."
            )

        snapshot_data = self._snapshot_to_dict(
            snapshot
        )

        relative_strength = snapshot_data.get(
            "relative_strength",
            [],
        )

        sector_strength = snapshot_data.get(
            "sector_strength",
            [],
        )

        market_regime = snapshot_data.get(
            "market_regime",
            {},
        )

        if not isinstance(
            relative_strength,
            Sequence,
        ):
            raise TypeError(
                "snapshot relative_strength must "
                "be a sequence."
            )

        if not isinstance(
            sector_strength,
            Sequence,
        ):
            raise TypeError(
                "snapshot sector_strength must "
                "be a sequence."
            )

        if not isinstance(
            market_regime,
            Mapping,
        ):
            raise TypeError(
                "snapshot market_regime must "
                "be a mapping."
            )

        normalized_sector_map = {
            self._normalize_symbol(
                symbol
            ): self._normalize_sector(
                sector
            )
            for symbol, sector
            in sector_map.items()
        }

        sector_lookup = (
            self._build_sector_lookup(
                sector_strength=[
                    result
                    for result in sector_strength
                    if isinstance(
                        result,
                        Mapping,
                    )
                ]
            )
        )

        regime_details = (
            self._market_regime_details(
                market_regime
            )
        )

        results: List[
            StockSelectionResult
        ] = []

        for relative_result in relative_strength:
            if not isinstance(
                relative_result,
                Mapping,
            ):
                continue

            symbol = self._normalize_symbol(
                relative_result.get(
                    "symbol",
                    "",
                )
            )

            if not symbol:
                continue

            sector = normalized_sector_map.get(
                symbol,
                "UNKNOWN",
            )

            sector_result = sector_lookup.get(
                sector
            )

            result = self._score_stock(
                relative_result=relative_result,
                sector=sector,
                sector_result=sector_result,
                regime_details=regime_details,
            )

            results.append(
                result
            )

        results.sort(
            key=lambda item: (
                item.score,
                -item.relative_strength_rank
                if item.relative_strength_rank > 0
                else float("-inf"),
            ),
            reverse=True,
        )

        selected_count = 0
        final_results: List[
            StockSelectionResult
        ] = []

        for result in results:
            eligible = (
                result.score
                >= self.minimum_score
            )

            within_limit = (
                self.maximum_candidates is None
                or selected_count
                < self.maximum_candidates
            )

            selected = (
                eligible
                and within_limit
            )

            reasons = list(
                result.reasons
            )

            if selected:
                selected_count += 1
                reasons.append(
                    "Candidate passed the stock-selection "
                    "threshold."
                )

            elif not eligible:
                reasons.append(
                    "Candidate did not meet the minimum "
                    "selection score."
                )

            else:
                reasons.append(
                    "Candidate passed the score threshold "
                    "but exceeded the candidate limit."
                )

            final_results.append(
                StockSelectionResult(
                    symbol=result.symbol,
                    sector=result.sector,
                    score=result.score,
                    confidence=result.confidence,
                    relative_strength_rank=(
                        result.relative_strength_rank
                    ),
                    relative_strength_percentile=(
                        result.relative_strength_percentile
                    ),
                    relative_strength_score=(
                        result.relative_strength_score
                    ),
                    relative_return=(
                        result.relative_return
                    ),
                    sector_rank=(
                        result.sector_rank
                    ),
                    sector_percentile=(
                        result.sector_percentile
                    ),
                    sector_strength_score=(
                        result.sector_strength_score
                    ),
                    sector_relative_return=(
                        result.sector_relative_return
                    ),
                    sector_classification=(
                        result.sector_classification
                    ),
                    market_regime=(
                        result.market_regime
                    ),
                    selected=selected,
                    reasons=reasons,
                )
            )

        return final_results

    def select_as_dicts(
        self,
        snapshot: Union[
            MarketIntelligenceSnapshot,
            Mapping[str, object],
        ],
        sector_map: Mapping[
            str,
            str,
        ],
    ) -> List[Dict[str, object]]:
        """
        Return stock-selection results as dictionaries.
        """

        return [
            result.to_dict()
            for result in self.select(
                snapshot=snapshot,
                sector_map=sector_map,
            )
        ]

    def selected_candidates(
        self,
        snapshot: Union[
            MarketIntelligenceSnapshot,
            Mapping[str, object],
        ],
        sector_map: Mapping[
            str,
            str,
        ],
    ) -> List[StockSelectionResult]:
        """
        Return only candidates marked selected.
        """

        return [
            result
            for result in self.select(
                snapshot=snapshot,
                sector_map=sector_map,
            )
            if result.selected
        ]

    def best_candidate(
        self,
        snapshot: Union[
            MarketIntelligenceSnapshot,
            Mapping[str, object],
        ],
        sector_map: Mapping[
            str,
            str,
        ],
    ) -> Optional[StockSelectionResult]:
        """
        Return the highest-ranked selected candidate.
        """

        candidates = self.selected_candidates(
            snapshot=snapshot,
            sector_map=sector_map,
        )

        if not candidates:
            return None

        return candidates[0]

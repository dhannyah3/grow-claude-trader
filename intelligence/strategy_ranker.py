from typing import Any, Dict, List
from analytics.performance_coach import PerformanceCoach

class StrategyRanker:
    """
    Scores every registered strategy against the
    current market regime and intelligence state.
    """
    def __init__(
        self,
        journal_file: str = "logs/trade_journal.json",
        minimum_learning_sample: int = 20,
        maximum_learning_adjustment: int = 10,
    ) -> None:
        self.performance_coach = PerformanceCoach(
            journal_file=journal_file,
        )

        self.minimum_learning_sample = int(
            minimum_learning_sample
        )

        self.maximum_learning_adjustment = int(
            maximum_learning_adjustment
        )

    def rank(
        self,
        regime_data: Dict[str, Any],
        intelligence: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        trend = str(
            regime_data.get(
                "trend",
                "UNKNOWN",
            )
        ).upper()

        volatility = str(
            regime_data.get(
                "volatility",
                "UNKNOWN",
            )
        ).upper()

        gap = str(
            regime_data.get(
                "gap",
                "UNKNOWN",
            )
        ).upper()

        rsi_state = str(
            intelligence.get(
                "rsi_state",
                "UNKNOWN",
            )
        ).upper()

        macd_state = str(
            intelligence.get(
                "macd_state",
                "UNKNOWN",
            )
        ).upper()

        vwap_state = str(
            intelligence.get(
                "vwap_state",
                "UNKNOWN",
            )
        ).upper()

        volume_state = str(
            intelligence.get(
                "volume_state",
                "UNKNOWN",
            )
        ).upper()

        market_quality = int(
            intelligence.get(
                "market_quality",
                0,
            )
            or 0
        )

        rankings = [
            self._score_orb(
                trend=trend,
                volatility=volatility,
                gap=gap,
                rsi_state=rsi_state,
                macd_state=macd_state,
                vwap_state=vwap_state,
                volume_state=volume_state,
                market_quality=market_quality,
            ),
            self._score_vwap(
                trend=trend,
                volatility=volatility,
                gap=gap,
                rsi_state=rsi_state,
                macd_state=macd_state,
                vwap_state=vwap_state,
                volume_state=volume_state,
                market_quality=market_quality,
            ),
        ]

        performance_report = (
            self.performance_coach.analyze()
        )

        strategy_performance = (
            performance_report.get(
                "strategy_performance",
                {},
            )
        )

        learned_rankings = [
            self._apply_historical_learning(
                ranking=ranking,
                strategy_performance=(
                    strategy_performance
                ),
            )
            for ranking in rankings
        ]

        learned_rankings.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return learned_rankings

    def _apply_historical_learning(
        self,
        ranking: Dict[str, Any],
        strategy_performance: Dict[
            str,
            Dict[str, Any],
        ],
    ) -> Dict[str, Any]:
        strategy = str(
            ranking.get(
                "strategy",
                "UNKNOWN",
            )
        )

        base_score = int(
            ranking.get(
                "score",
                0,
            )
            or 0
        )

        reasons = list(
            ranking.get(
                "reasons",
                [],
            )
        )

        stats = strategy_performance.get(
            strategy,
            {},
        )

        trades = int(
            stats.get(
                "trades",
                0,
            )
            or 0
        )

        adjustment = 0

        if trades < self.minimum_learning_sample:
            reasons.append(
                "Historical learning inactive: "
                f"{trades}/"
                f"{self.minimum_learning_sample} "
                "required trades."
            )

        else:
            win_rate = float(
                stats.get(
                    "win_rate",
                    0.0,
                )
                or 0.0
            )

            profit_factor_raw = stats.get(
                "profit_factor",
                0.0,
            )

            if profit_factor_raw == "Infinity":
                profit_factor = 3.0

            else:
                try:
                    profit_factor = float(
                        profit_factor_raw
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    profit_factor = 0.0

            if win_rate >= 60:
                adjustment += 6

            elif win_rate >= 55:
                adjustment += 3

            elif win_rate < 40:
                adjustment -= 6

            elif win_rate < 45:
                adjustment -= 3

            if profit_factor >= 1.5:
                adjustment += 4

            elif profit_factor >= 1.2:
                adjustment += 2

            elif profit_factor < 0.8:
                adjustment -= 4

            elif profit_factor < 1.0:
                adjustment -= 2

            adjustment = max(
                -self.maximum_learning_adjustment,
                min(
                    adjustment,
                    self.maximum_learning_adjustment,
                ),
            )

            reasons.append(
                "Historical adjustment: "
                f"{adjustment:+d} from "
                f"{trades} trades, "
                f"{win_rate:.1f}% win rate, "
                f"{profit_factor:.2f} "
                "profit factor."
            )

        final_score = max(
            0,
            min(
                base_score + adjustment,
                100,
            ),
        )

        return {
            **ranking,
            "base_score": base_score,
            "historical_adjustment": adjustment,
            "historical_sample_size": trades,
            "learning_active": (
                trades
                >= self.minimum_learning_sample
            ),
            "score": final_score,
            "reasons": reasons,
        }

    def _score_orb(
        self,
        trend: str,
        volatility: str,
        gap: str,
        rsi_state: str,
        macd_state: str,
        vwap_state: str,
        volume_state: str,
        market_quality: int,
    ) -> Dict[str, Any]:
        score = 0
        reasons = []

        if trend == "TRENDING":
            score += 30
            reasons.append(
                "Trending market supports breakout trading."
            )

        elif trend == "RANGE_BOUND":
            score -= 20
            reasons.append(
                "Range-bound conditions weaken ORB."
            )

        elif trend == "DOWNTREND":
            score -= 30
            reasons.append(
                "Downtrend is unsuitable for long-only ORB."
            )

        if volume_state == "HIGH":
            score += 20
            reasons.append(
                "High volume supports breakout confirmation."
            )

        elif volume_state == "LOW":
            score -= 10
            reasons.append(
                "Low volume weakens breakout quality."
            )

        if macd_state == "BULLISH":
            score += 15
            reasons.append(
                "Bullish MACD supports momentum."
            )

        if vwap_state == "ABOVE":
            score += 15
            reasons.append(
                "Price above VWAP supports bullish continuation."
            )

        if rsi_state == "BULLISH":
            score += 10
            reasons.append(
                "Bullish RSI supports the setup."
            )

        elif rsi_state == "OVERBOUGHT":
            score -= 10
            reasons.append(
                "Overbought RSI increases chase risk."
            )

        if volatility == "MEDIUM":
            score += 10
            reasons.append(
                "Moderate volatility is favorable for ORB."
            )

        elif volatility == "HIGH":
            score -= 10
            reasons.append(
                "High volatility increases false-breakout risk."
            )

        if gap in {
            "GAP_UP",
            "GAP_DOWN",
        }:
            score -= 5
            reasons.append(
                "Opening gap adds breakout risk."
            )

        score += int(
            market_quality * 0.20
        )

        score = max(
            0,
            min(
                score,
                100,
            ),
        )

        return {
            "strategy": "ORB_BREAKOUT",
            "score": score,
            "reasons": reasons,
        }

    def _score_vwap(
        self,
        trend: str,
        volatility: str,
        gap: str,
        rsi_state: str,
        macd_state: str,
        vwap_state: str,
        volume_state: str,
        market_quality: int,
    ) -> Dict[str, Any]:
        score = 0
        reasons = []

        if trend == "RANGE_BOUND":
            score += 30
            reasons.append(
                "Range-bound conditions favor VWAP pullbacks."
            )

        elif trend == "TRENDING":
            score += 10
            reasons.append(
                "VWAP pullbacks can work within a trend."
            )

        elif trend == "DOWNTREND":
            score -= 25
            reasons.append(
                "Downtrend weakens long-only VWAP setups."
            )

        if vwap_state == "NEAR":
            score += 25
            reasons.append(
                "Price is near VWAP."
            )

        elif vwap_state == "ABOVE":
            score += 10
            reasons.append(
                "Price is holding above VWAP."
            )

        elif vwap_state == "BELOW":
            score -= 10
            reasons.append(
                "Price remains below VWAP."
            )

        if rsi_state == "BULLISH":
            score += 15
            reasons.append(
                "Bullish RSI supports a reclaim."
            )

        elif rsi_state == "NEUTRAL":
            score += 10
            reasons.append(
                "Neutral RSI leaves room for recovery."
            )

        elif rsi_state == "OVERBOUGHT":
            score -= 10
            reasons.append(
                "Overbought RSI weakens pullback quality."
            )

        if macd_state == "BULLISH":
            score += 10
            reasons.append(
                "Bullish MACD supports the reclaim."
            )

        if volume_state in {
            "NORMAL",
            "HIGH",
        }:
            score += 10
            reasons.append(
                "Volume is sufficient for VWAP confirmation."
            )

        if volatility == "LOW":
            score += 10
            reasons.append(
                "Low volatility favors controlled pullbacks."
            )

        elif volatility == "HIGH":
            score -= 10
            reasons.append(
                "High volatility increases VWAP failure risk."
            )

        if gap in {
            "GAP_UP",
            "GAP_DOWN",
        }:
            score -= 5
            reasons.append(
                "Opening gap adds mean-reversion uncertainty."
            )

        score += int(
            market_quality * 0.15
        )

        score = max(
            0,
            min(
                score,
                100,
            ),
        )

        return {
            "strategy": "VWAP_PULLBACK",
            "score": score,
            "reasons": reasons,
        }
"""
Final Decision Engine.

This module orchestrates the complete decision pipeline:

    StockSelector
        -> PortfolioAllocator
        -> PositionSizer
        -> TradePriorityEngine
        -> RiskBudgetAllocator
        -> Execution Queue

The individual decision modules remain responsible for their own business
rules. This engine converts the output of one stage into the input required
by the next stage.
"""

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from decision.portfolio_allocator import PortfolioAllocator
from decision.position_sizer import PositionSizer
from decision.risk_budget_allocator import RiskBudgetAllocator
from decision.stock_selector import StockSelector
from decision.trade_priority_engine import TradePriorityEngine


@dataclass
class FinalDecisionSummary:
    """
    High-level summary of one complete decision-engine run.
    """

    selected_candidates: int
    allocated_positions: int
    approved_position_sizes: int
    executable_priority_trades: int
    risk_approved_trades: int
    risk_rejected_trades: int
    total_execution_value: float
    total_execution_risk: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FinalDecisionResult:
    """
    Complete result returned by FinalDecisionEngine.
    """

    stock_selection: List[Any]
    portfolio_allocation: List[Any]
    position_sizing: List[Any]
    trade_priority: List[Any]
    risk_budget: List[Any]
    execution_queue: List[Dict[str, Any]]
    summary: FinalDecisionSummary

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stock_selection": [
                FinalDecisionEngine.object_to_dict(item)
                for item in self.stock_selection
            ],
            "portfolio_allocation": [
                FinalDecisionEngine.object_to_dict(item)
                for item in self.portfolio_allocation
            ],
            "position_sizing": [
                FinalDecisionEngine.object_to_dict(item)
                for item in self.position_sizing
            ],
            "trade_priority": [
                FinalDecisionEngine.object_to_dict(item)
                for item in self.trade_priority
            ],
            "risk_budget": [
                FinalDecisionEngine.object_to_dict(item)
                for item in self.risk_budget
            ],
            "execution_queue": list(self.execution_queue),
            "summary": self.summary.to_dict(),
        }


class FinalDecisionEngine:
    """
    Coordinates all decision-layer modules.

    The engine does not replace the logic inside the individual modules.
    Its main purpose is to:

    1. Run each decision stage in the correct order.
    2. Translate result objects between stages.
    3. Preserve useful metadata.
    4. Produce a final execution queue.
    5. Produce a combined summary.
    """

    def __init__(
        self,
        stock_selector: Optional[StockSelector] = None,
        portfolio_allocator: Optional[PortfolioAllocator] = None,
        position_sizer: Optional[PositionSizer] = None,
        trade_priority_engine: Optional[TradePriorityEngine] = None,
        risk_budget_allocator: Optional[RiskBudgetAllocator] = None,
        default_stop_loss_percent: float = 1.0,
        default_risk_reward_ratio: float = 2.0,
        round_values: int = 2,
    ) -> None:
        self.stock_selector = stock_selector or StockSelector()
        self.portfolio_allocator = (
            portfolio_allocator or PortfolioAllocator()
        )
        self.position_sizer = position_sizer or PositionSizer()
        self.trade_priority_engine = (
            trade_priority_engine or TradePriorityEngine()
        )
        self.risk_budget_allocator = (
            risk_budget_allocator or RiskBudgetAllocator()
        )

        self.default_stop_loss_percent = self._positive_float(
            default_stop_loss_percent,
            "default_stop_loss_percent",
        )
        self.default_risk_reward_ratio = self._positive_float(
            default_risk_reward_ratio,
            "default_risk_reward_ratio",
        )
        self.round_values = max(0, int(round_values))

    @staticmethod
    def object_to_dict(value: Any) -> Dict[str, Any]:
        """
        Convert a supported result object into a dictionary.
        """

        if value is None:
            return {}

        if isinstance(value, Mapping):
            return dict(value)

        if hasattr(value, "to_dict"):
            converted = value.to_dict()

            if isinstance(converted, Mapping):
                return dict(converted)

        if is_dataclass(value):
            converted = asdict(value)

            if isinstance(converted, Mapping):
                return dict(converted)

        if hasattr(value, "__dict__"):
            return {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }

        raise TypeError(
            "Unable to convert object to dictionary: "
            f"{type(value).__name__}"
        )

    @staticmethod
    def _positive_float(
        value: Any,
        field_name: str,
    ) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError):
            raise ValueError(
                f"{field_name} must be a valid number."
            )

        if converted <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return converted

    @staticmethod
    def _non_negative_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            converted = float(value)
        except (TypeError, ValueError):
            return float(default)

        return max(0.0, converted)

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        if value is None:
            return ""

        return str(value).strip().upper()

    @staticmethod
    def _first_value(
        mapping: Mapping[str, Any],
        keys: Iterable[str],
        default: Any = None,
    ) -> Any:
        for key in keys:
            if key in mapping and mapping[key] is not None:
                return mapping[key]

        return default

    @staticmethod
    def _result_is_selected(result: Any) -> bool:
        data = FinalDecisionEngine.object_to_dict(result)

        value = FinalDecisionEngine._first_value(
            data,
            (
                "selected",
                "approved",
                "approved_by_sizer",
                "execute",
                "requested_execute",
            ),
            False,
        )

        return bool(value)

    def _snapshot_to_dict(
        self,
        snapshot: Any,
    ) -> Dict[str, Any]:
        try:
            return self.object_to_dict(snapshot)
        except TypeError:
            return {}

    def _snapshot_stock_lookup(
        self,
        snapshot: Any,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build a symbol-to-stock-data lookup from common snapshot layouts.
        """

        snapshot_data = self._snapshot_to_dict(snapshot)

        possible_collections = (
            "stocks",
            "stock_data",
            "symbols",
            "candidates",
            "relative_strength",
            "stock_strength",
            "stock_results",
        )

        collection = None

        for key in possible_collections:
            value = snapshot_data.get(key)

            if isinstance(value, (Mapping, list, tuple)):
                collection = value
                break

        lookup: Dict[str, Dict[str, Any]] = {}

        if isinstance(collection, Mapping):
            for symbol, data in collection.items():
                normalized_symbol = self._normalize_symbol(symbol)

                if not normalized_symbol:
                    continue

                if isinstance(data, Mapping):
                    lookup[normalized_symbol] = dict(data)
                else:
                    try:
                        lookup[normalized_symbol] = self.object_to_dict(
                            data
                        )
                    except TypeError:
                        lookup[normalized_symbol] = {}

        elif isinstance(collection, (list, tuple)):
            for item in collection:
                try:
                    item_data = self.object_to_dict(item)
                except TypeError:
                    continue

                symbol = self._normalize_symbol(
                    self._first_value(
                        item_data,
                        (
                            "symbol",
                            "trading_symbol",
                            "ticker",
                        ),
                    )
                )

                if symbol:
                    lookup[symbol] = item_data

        return lookup

    def _price_lookup(
        self,
        prices: Optional[Mapping[str, Any]],
    ) -> Dict[str, float]:
        lookup: Dict[str, float] = {}

        if not prices:
            return lookup

        for raw_symbol, raw_price in prices.items():
            symbol = self._normalize_symbol(raw_symbol)

            if not symbol:
                continue

            if isinstance(raw_price, Mapping):
                value = self._first_value(
                    raw_price,
                    (
                        "last_price",
                        "ltp",
                        "price",
                        "close",
                        "entry_price",
                    ),
                )
            else:
                value = raw_price

            price = self._non_negative_float(value)

            if price > 0:
                lookup[symbol] = price

        return lookup

    def _prepare_allocation_candidates(
        self,
        stock_selection: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Convert StockSelectionResult objects into allocator candidates.
        """

        candidates: List[Dict[str, Any]] = []

        for result in stock_selection:
            data = self.object_to_dict(result)

            symbol = self._normalize_symbol(data.get("symbol"))

            if not symbol:
                continue

            data["symbol"] = symbol
            candidates.append(data)

        return candidates

    def _resolve_entry_price(
        self,
        symbol: str,
        allocation: Mapping[str, Any],
        stock_data: Mapping[str, Any],
        price_lookup: Mapping[str, float],
    ) -> float:
        price = self._first_value(
            allocation,
            (
                "entry_price",
                "last_price",
                "price",
                "ltp",
            ),
        )

        if price is None:
            price = self._first_value(
                stock_data,
                (
                    "entry_price",
                    "last_price",
                    "ltp",
                    "price",
                    "close",
                ),
            )

        if price is None:
            price = price_lookup.get(symbol)

        return self._non_negative_float(price)

    def _resolve_stop_loss(
        self,
        entry_price: float,
        allocation: Mapping[str, Any],
        stock_data: Mapping[str, Any],
    ) -> float:
        stop_loss = self._first_value(
            allocation,
            (
                "stop_loss",
                "stop_price",
                "sl",
            ),
        )

        if stop_loss is None:
            stop_loss = self._first_value(
                stock_data,
                (
                    "stop_loss",
                    "stop_price",
                    "sl",
                    "opening_low",
                    "swing_low",
                ),
            )

        resolved = self._non_negative_float(stop_loss)

        if resolved <= 0 or resolved >= entry_price:
            stop_distance = (
                entry_price
                * self.default_stop_loss_percent
                / 100.0
            )
            resolved = entry_price - stop_distance

        return round(resolved, self.round_values)

    def _resolve_target_price(
        self,
        entry_price: float,
        stop_loss: float,
        allocation: Mapping[str, Any],
        stock_data: Mapping[str, Any],
    ) -> float:
        target_price = self._first_value(
            allocation,
            (
                "target_price",
                "target",
                "take_profit",
            ),
        )

        if target_price is None:
            target_price = self._first_value(
                stock_data,
                (
                    "target_price",
                    "target",
                    "take_profit",
                    "opening_high",
                    "resistance",
                ),
            )

        resolved = self._non_negative_float(target_price)

        if resolved <= entry_price:
            risk_per_share = entry_price - stop_loss
            resolved = (
                entry_price
                + risk_per_share
                * self.default_risk_reward_ratio
            )

        return round(resolved, self.round_values)

    def _prepare_position_requests(
        self,
        portfolio_allocation: Iterable[Any],
        stock_selection: Iterable[Any],
        snapshot: Any,
        prices: Optional[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convert allocation results into PositionSizer requests.
        """

        selection_lookup = {
            self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            ): self.object_to_dict(item)
            for item in stock_selection
            if self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            )
        }

        snapshot_lookup = self._snapshot_stock_lookup(snapshot)
        prices_lookup = self._price_lookup(prices)

        requests: List[Dict[str, Any]] = []

        for result in portfolio_allocation:
            allocation = self.object_to_dict(result)

            if not bool(allocation.get("selected", False)):
                continue

            symbol = self._normalize_symbol(
                allocation.get("symbol")
            )

            if not symbol:
                continue

            selection_data = selection_lookup.get(symbol, {})
            snapshot_data = snapshot_lookup.get(symbol, {})

            combined_stock_data = dict(snapshot_data)
            combined_stock_data.update(selection_data)

            entry_price = self._resolve_entry_price(
                symbol=symbol,
                allocation=allocation,
                stock_data=combined_stock_data,
                price_lookup=prices_lookup,
            )

            if entry_price <= 0:
                continue

            stop_loss = self._resolve_stop_loss(
                entry_price=entry_price,
                allocation=allocation,
                stock_data=combined_stock_data,
            )

            target_price = self._resolve_target_price(
                entry_price=entry_price,
                stop_loss=stop_loss,
                allocation=allocation,
                stock_data=combined_stock_data,
            )

            allocation_cash = self._non_negative_float(
                self._first_value(
                    allocation,
                    (
                        "cash_used",
                        "capped_allocation",
                        "requested_allocation",
                        "allocation_cash",
                    ),
                )
            )

            allocation_quantity = self._safe_int(
                self._first_value(
                    allocation,
                    (
                        "quantity",
                        "allocation_quantity",
                    ),
                )
            )

            request = dict(allocation)

            request.update(
                {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "target_price": target_price,
                    "allocation_cash": allocation_cash,
                    "allocation_quantity": allocation_quantity,
                    "sector": selection_data.get(
                        "sector",
                        combined_stock_data.get("sector", ""),
                    ),
                    "score": selection_data.get(
                        "score",
                        allocation.get("score", 0.0),
                    ),
                    "confidence": selection_data.get(
                        "confidence",
                        allocation.get("confidence", 0.0),
                    ),
                }
            )

            requests.append(request)

        return requests

    def _prepare_priority_candidates(
        self,
        position_sizing: Iterable[Any],
        stock_selection: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Convert PositionSizeResult objects into priority candidates.
        """

        selection_lookup = {
            self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            ): self.object_to_dict(item)
            for item in stock_selection
            if self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            )
        }

        candidates: List[Dict[str, Any]] = []

        for original_rank, result in enumerate(
            position_sizing,
            start=1,
        ):
            sizing = self.object_to_dict(result)

            symbol = self._normalize_symbol(
                sizing.get("symbol")
            )

            if not symbol:
                continue

            selection = selection_lookup.get(symbol, {})

            sector_strength = self._non_negative_float(
                self._first_value(
                    selection,
                    (
                        "sector_strength_score",
                        "sector_percentile",
                    ),
                )
            )

            relative_strength = self._non_negative_float(
                self._first_value(
                    selection,
                    (
                        "relative_strength_score",
                        "relative_strength_percentile",
                    ),
                )
            )

            market_strength = self._non_negative_float(
                self._first_value(
                    selection,
                    (
                        "market_strength",
                        "market_regime_score",
                    ),
                    selection.get("score", 0.0),
                )
            )

            candidate = dict(sizing)

            candidate.update(
                {
                    "symbol": symbol,
                    "original_rank": original_rank,
                    "approved_by_sizer": bool(
                        sizing.get("approved", False)
                    ),
                    "approved": bool(
                        sizing.get("approved", False)
                    ),
                    "strategy_score": self._non_negative_float(
                        self._first_value(
                            selection,
                            (
                                "strategy_score",
                                "score",
                            ),
                        )
                    ),
                    "score": self._non_negative_float(
                        selection.get("score", 0.0)
                    ),
                    "confidence": self._non_negative_float(
                        selection.get("confidence", 0.0)
                    ),
                    "market_strength": market_strength,
                    "sector_strength": sector_strength,
                    "relative_strength": relative_strength,
                    "sector": selection.get("sector", ""),
                    "market_regime": selection.get(
                        "market_regime",
                        "",
                    ),
                }
            )

            candidates.append(candidate)

        return candidates

    def _prepare_risk_candidates(
        self,
        trade_priority: Iterable[Any],
        position_sizing: Iterable[Any],
        stock_selection: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Convert priority results into RiskBudgetAllocator candidates.
        """

        sizing_lookup = {
            self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            ): self.object_to_dict(item)
            for item in position_sizing
            if self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            )
        }

        selection_lookup = {
            self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            ): self.object_to_dict(item)
            for item in stock_selection
            if self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            )
        }

        candidates: List[Dict[str, Any]] = []

        for priority_result in trade_priority:
            priority = self.object_to_dict(priority_result)

            symbol = self._normalize_symbol(
                priority.get("symbol")
            )

            if not symbol:
                continue

            sizing = sizing_lookup.get(symbol, {})
            selection = selection_lookup.get(symbol, {})

            entry_price = self._non_negative_float(
                self._first_value(
                    sizing,
                    (
                        "entry_price",
                        "last_price",
                        "price",
                    ),
                )
            )

            stop_loss = self._non_negative_float(
                self._first_value(
                    sizing,
                    (
                        "stop_loss",
                        "stop_price",
                    ),
                )
            )

            final_quantity = self._safe_int(
                self._first_value(
                    sizing,
                    (
                        "final_quantity",
                        "quantity",
                    ),
                )
            )

            risk_per_share = self._non_negative_float(
                sizing.get("risk_per_share")
            )

            if risk_per_share <= 0 and entry_price > stop_loss:
                risk_per_share = entry_price - stop_loss

            position_value = self._non_negative_float(
                sizing.get("position_value")
            )

            if position_value <= 0:
                position_value = entry_price * final_quantity

            risk_amount = self._non_negative_float(
                sizing.get("risk_amount")
            )

            if risk_amount <= 0:
                risk_amount = risk_per_share * final_quantity

            candidate = dict(priority)

            candidate.update(
                {
                    "symbol": symbol,
                    "sector": selection.get("sector", ""),
                    "requested_execute": bool(
                        priority.get("execute", False)
                    ),
                    "execute": bool(
                        priority.get("execute", False)
                    ),
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "target_price": sizing.get(
                        "target_price",
                        0.0,
                    ),
                    "risk_per_share": risk_per_share,
                    "final_quantity": final_quantity,
                    "quantity": final_quantity,
                    "position_value": position_value,
                    "risk_amount": risk_amount,
                }
            )

            candidates.append(candidate)

        return candidates

    def _build_execution_queue(
        self,
        risk_budget: Iterable[Any],
        position_sizing: Iterable[Any],
        trade_priority: Iterable[Any],
        stock_selection: Iterable[Any],
    ) -> List[Dict[str, Any]]:
        """
        Build the final broker-ready execution queue.
        """

        sizing_lookup = {
            self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            ): self.object_to_dict(item)
            for item in position_sizing
            if self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            )
        }

        priority_lookup = {
            self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            ): self.object_to_dict(item)
            for item in trade_priority
            if self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            )
        }

        selection_lookup = {
            self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            ): self.object_to_dict(item)
            for item in stock_selection
            if self._normalize_symbol(
                self.object_to_dict(item).get("symbol")
            )
        }

        queue: List[Dict[str, Any]] = []

        for risk_result in risk_budget:
            risk = self.object_to_dict(risk_result)

            if not bool(risk.get("approved", False)):
                continue

            adjusted_quantity = self._safe_int(
                risk.get("adjusted_quantity")
            )

            if adjusted_quantity <= 0:
                continue

            symbol = self._normalize_symbol(
                risk.get("symbol")
            )

            if not symbol:
                continue

            sizing = sizing_lookup.get(symbol, {})
            priority = priority_lookup.get(symbol, {})
            selection = selection_lookup.get(symbol, {})

            queue.append(
                {
                    "symbol": symbol,
                    "side": "BUY",
                    "quantity": adjusted_quantity,
                    "entry_price": self._non_negative_float(
                        risk.get(
                            "entry_price",
                            sizing.get("entry_price", 0.0),
                        )
                    ),
                    "stop_loss": self._non_negative_float(
                        risk.get(
                            "stop_loss",
                            sizing.get("stop_loss", 0.0),
                        )
                    ),
                    "target_price": self._non_negative_float(
                        sizing.get("target_price")
                    ),
                    "position_value": self._non_negative_float(
                        risk.get("adjusted_position_value")
                    ),
                    "risk_amount": self._non_negative_float(
                        risk.get("allocated_risk_amount")
                    ),
                    "priority_rank": self._safe_int(
                        risk.get(
                            "priority_rank",
                            priority.get("priority_rank", 0),
                        )
                    ),
                    "priority_score": self._non_negative_float(
                        risk.get(
                            "priority_score",
                            priority.get("priority_score", 0.0),
                        )
                    ),
                    "strategy_score": self._non_negative_float(
                        priority.get("strategy_score")
                    ),
                    "confidence": self._non_negative_float(
                        priority.get(
                            "confidence",
                            selection.get("confidence", 0.0),
                        )
                    ),
                    "sector": risk.get(
                        "sector",
                        selection.get("sector", ""),
                    ),
                    "market_regime": selection.get(
                        "market_regime",
                        "",
                    ),
                    "relative_strength": self._non_negative_float(
                        priority.get("relative_strength")
                    ),
                    "sector_strength": self._non_negative_float(
                        priority.get("sector_strength")
                    ),
                    "scaled_by_risk_budget": bool(
                        risk.get("scaled", False)
                    ),
                    "approved": True,
                    "reasons": list(
                        risk.get("reasons", [])
                    ),
                }
            )

        queue.sort(
            key=lambda item: (
                item.get("priority_rank", 999999),
                -item.get("priority_score", 0.0),
            )
        )

        return queue

    def _build_summary(
        self,
        stock_selection: Iterable[Any],
        portfolio_allocation: Iterable[Any],
        position_sizing: Iterable[Any],
        trade_priority: Iterable[Any],
        risk_budget: Iterable[Any],
        execution_queue: Iterable[Mapping[str, Any]],
    ) -> FinalDecisionSummary:
        stock_selection_list = list(stock_selection)
        allocation_list = list(portfolio_allocation)
        sizing_list = list(position_sizing)
        priority_list = list(trade_priority)
        risk_list = list(risk_budget)
        queue_list = list(execution_queue)

        selected_candidates = sum(
            1
            for item in stock_selection_list
            if bool(
                self.object_to_dict(item).get(
                    "selected",
                    False,
                )
            )
        )

        allocated_positions = sum(
            1
            for item in allocation_list
            if bool(
                self.object_to_dict(item).get(
                    "selected",
                    False,
                )
            )
        )

        approved_position_sizes = sum(
            1
            for item in sizing_list
            if bool(
                self.object_to_dict(item).get(
                    "approved",
                    False,
                )
            )
        )

        executable_priority_trades = sum(
            1
            for item in priority_list
            if bool(
                self.object_to_dict(item).get(
                    "execute",
                    False,
                )
            )
        )

        risk_approved_trades = sum(
            1
            for item in risk_list
            if bool(
                self.object_to_dict(item).get(
                    "approved",
                    False,
                )
            )
        )

        risk_rejected_trades = len(risk_list) - risk_approved_trades

        total_execution_value = round(
            sum(
                self._non_negative_float(
                    item.get("position_value")
                )
                for item in queue_list
            ),
            self.round_values,
        )

        total_execution_risk = round(
            sum(
                self._non_negative_float(
                    item.get("risk_amount")
                )
                for item in queue_list
            ),
            self.round_values,
        )

        return FinalDecisionSummary(
            selected_candidates=selected_candidates,
            allocated_positions=allocated_positions,
            approved_position_sizes=approved_position_sizes,
            executable_priority_trades=(
                executable_priority_trades
            ),
            risk_approved_trades=risk_approved_trades,
            risk_rejected_trades=risk_rejected_trades,
            total_execution_value=total_execution_value,
            total_execution_risk=total_execution_risk,
        )

    def run(
        self,
        snapshot: Any,
        sector_map: Mapping[str, str],
        total_capital: float,
        prices: Optional[Mapping[str, Any]],
        current_open_positions: int = 0,
        maximum_open_positions: Optional[int] = None,
        existing_daily_risk: float = 0.0,
        existing_portfolio_exposure: float = 0.0,
        existing_sector_exposure: Optional[
            Mapping[str, float]
        ] = None,
        available_capital: Optional[float] = None,
    ) -> FinalDecisionResult:
        """
        Execute the complete decision pipeline.
        """

        resolved_total_capital = self._positive_float(
            total_capital,
            "total_capital",
        )

        if available_capital is None:
            resolved_available_capital = resolved_total_capital
        else:
            resolved_available_capital = self._non_negative_float(
                available_capital
            )

        resolved_existing_sector_exposure = dict(
            existing_sector_exposure or {}
        )

        # ---------------------------------------------------------
        # Stage 1: Stock selection
        # ---------------------------------------------------------

        stock_selection = self.stock_selector.select(
            snapshot=snapshot,
            sector_map=sector_map,
        )

        # ---------------------------------------------------------
        # Stage 2: Portfolio allocation
        # ---------------------------------------------------------

        allocation_candidates = (
            self._prepare_allocation_candidates(
                stock_selection
            )
        )

        portfolio_allocation = self.portfolio_allocator.allocate(
            candidates=allocation_candidates,
            total_capital=resolved_total_capital,
            prices=prices,
        )

        # ---------------------------------------------------------
        # Stage 3: Position sizing
        # ---------------------------------------------------------

        position_requests = self._prepare_position_requests(
            portfolio_allocation=portfolio_allocation,
            stock_selection=stock_selection,
            snapshot=snapshot,
            prices=prices,
        )

        position_sizing = self.position_sizer.size_positions(
            requests=position_requests
        )

        # ---------------------------------------------------------
        # Stage 4: Trade priority ranking
        # ---------------------------------------------------------

        priority_candidates = self._prepare_priority_candidates(
            position_sizing=position_sizing,
            stock_selection=stock_selection,
        )

        trade_priority = (
            self.trade_priority_engine.rank_trades(
                candidates=priority_candidates,
                current_open_positions=max(
                    0,
                    self._safe_int(current_open_positions),
                ),
                maximum_open_positions=maximum_open_positions,
            )
        )

        # ---------------------------------------------------------
        # Stage 5: Risk-budget allocation
        # ---------------------------------------------------------

        risk_candidates = self._prepare_risk_candidates(
            trade_priority=trade_priority,
            position_sizing=position_sizing,
            stock_selection=stock_selection,
        )

        risk_budget = self.risk_budget_allocator.allocate(
            candidates=risk_candidates,
            starting_capital=resolved_total_capital,
            available_capital=resolved_available_capital,
            existing_daily_risk=self._non_negative_float(
                existing_daily_risk
            ),
            existing_portfolio_exposure=(
                self._non_negative_float(
                    existing_portfolio_exposure
                )
            ),
            existing_sector_exposure=(
                resolved_existing_sector_exposure
            ),
        )

        # ---------------------------------------------------------
        # Stage 6: Final execution queue
        # ---------------------------------------------------------

        execution_queue = self._build_execution_queue(
            risk_budget=risk_budget,
            position_sizing=position_sizing,
            trade_priority=trade_priority,
            stock_selection=stock_selection,
        )

        summary = self._build_summary(
            stock_selection=stock_selection,
            portfolio_allocation=portfolio_allocation,
            position_sizing=position_sizing,
            trade_priority=trade_priority,
            risk_budget=risk_budget,
            execution_queue=execution_queue,
        )

        return FinalDecisionResult(
            stock_selection=stock_selection,
            portfolio_allocation=portfolio_allocation,
            position_sizing=position_sizing,
            trade_priority=trade_priority,
            risk_budget=risk_budget,
            execution_queue=execution_queue,
            summary=summary,
        )
Final Decision Engine Pipeline

1. StockSelector.select(snapshot, sector_map)

↓

2. Convert StockSelectionResult
   -> PortfolioAllocator input

↓

3. PortfolioAllocator.allocate()

↓

4. Convert PortfolioAllocationResult
   -> PositionSizer input
   (add stop loss, target, entry price)

↓

5. PositionSizer.size_positions()

↓

6. Convert PositionSizeResult
   -> TradePriorityEngine input

↓

7. TradePriorityEngine.rank_trades()

↓

8. Convert TradePriorityResult
   -> RiskBudgetAllocator input

↓

9. RiskBudgetAllocator.allocate()

↓

10. Build execution queue

↓

11. Return FinalDecisionResult
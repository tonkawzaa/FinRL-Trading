from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
import pandas as pd

@dataclass
class StrategyResult:
    strategy_name: str
    weights: pd.DataFrame
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class StrategyConfig:
    name: str = "BaseStrategy"

class BaseStrategy:
    """Minimal base strategy interface."""

    def __init__(self, config: StrategyConfig):
        self.config = config

    def generate_weights(self, data: Dict[str, pd.DataFrame], target_date: Optional[str] = None) -> StrategyResult:
        raise NotImplementedError("generate_weights must be implemented by subclasses")

class EqualWeightStrategy(BaseStrategy):
    """A simple equal weight strategy for testing."""
    def generate_weights(self, data: Dict[str, pd.DataFrame], target_date: Optional[str] = None) -> StrategyResult:
        return StrategyResult(self.config.name, pd.DataFrame())

def create_strategy(strategy_type: str, config: StrategyConfig) -> BaseStrategy:
    """Factory function to create a strategy instance."""
    if strategy_type == "equal_weight":
        return EqualWeightStrategy(config)
    # Default fallback
    return EqualWeightStrategy(config)

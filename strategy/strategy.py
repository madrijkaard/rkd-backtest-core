# strategy.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
import pandas as pd
import vectorbt as vbt

# ----------- CONDITION CONTRACT -----------
class Condition(ABC):
    @abstractmethod
    def evaluate(self, zones: pd.Series, price: float) -> bool:
        pass


# ----------- BASE CLASSES FOR BUY AND SELL -----------
@dataclass
class Buy(Condition):
    pass


@dataclass
class Sell(Condition):
    pass


# ----------- GENERIC TRADE -----------
@dataclass
class Trade:
    buy: Buy
    sell: Sell
    active: bool = False
    size: float = 0.0


# ----------- ABSTRACT BASE STRATEGY -----------
class Strategy(ABC):
    def __init__(self):
        self.trades: list[Trade] = []
        self.in_position: bool = False

    @abstractmethod
    def execute(self, close: pd.Series, zones_df: pd.DataFrame) -> vbt.Portfolio:
        pass

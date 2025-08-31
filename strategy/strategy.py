from abc import ABC, abstractmethod
from dataclasses import dataclass
import pandas as pd
import vectorbt as vbt

# ----------- CONDITION CONTRACT -----------
class Condition(ABC):
    @abstractmethod
    def evaluate(self, zones: pd.Series, price: float) -> bool:
        pass


# ----------- BASE CLASSES FOR IN AND OUT -----------
@dataclass
class In(Condition):
    pass


@dataclass
class Out(Condition):
    pass


# ----------- GENERIC TRADE -----------
@dataclass
class Trade:
    entry: In
    exit: Out
    active: bool = False
    size: float = 0.0


# ----------- ABSTRACT BASE STRATEGY -----------
class Strategy(ABC):
    def __init__(self):
        self.trades: list[Trade] = []
        self.in_position: bool = False

    @abstractmethod
    def execute(self, close: pd.Series, zones_df: pd.DataFrame, freq: str) -> vbt.Portfolio:
        pass

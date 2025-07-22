from abc import ABC, abstractmethod
from dataclasses import dataclass
import pandas as pd
import vectorbt as vbt

# ----------- CONTRATO DE CONDIÇÃO -----------
class Condicao(ABC):
    @abstractmethod
    def avaliar(self, zonas: pd.Series, preco: float) -> bool:
        pass


# ----------- CLASSES BASE DE COMPRA E VENDA -----------
@dataclass
class Compra(Condicao):
    pass


@dataclass
class Venda(Condicao):
    pass


# ----------- TRADE GENÉRICO -----------
@dataclass
class Trade:
    compra: Compra
    venda: Venda
    ativo: bool = False
    tamanho: float = 0.0


# ----------- ESTRATÉGIA BASE ABSTRATA -----------
class Estrategia(ABC):
    def __init__(self):
        self.trades: list[Trade] = []
        self.em_posicao: bool = False

    @abstractmethod
    def executar(self, close: pd.Series, zonas_df: pd.DataFrame) -> vbt.Portfolio:
        pass

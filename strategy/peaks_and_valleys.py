# strategy/peaks_and_valleys.py

import numpy as np
import pandas as pd
import vectorbt as vbt

from strategy.estrategia import Estrategia, Compra, Venda

# ----------- CÁLCULO DAS ZONAS LOGARÍTMICAS -----------
def calculate_log_zones(row: pd.Series) -> pd.Series:
    min_, max_ = row['min'], row['max']
    log_min = np.log(min_)
    log_max = np.log(max_)
    log_middle = (log_min + log_max) / 2
    log_mid_min = (log_min + log_middle) / 2
    log_mid_max = (log_max + log_middle) / 2
    log_mid_min_inner = (log_mid_min + log_middle) / 2
    log_mid_max_inner = (log_mid_max + log_middle) / 2
    log_below_min = (log_min + log_mid_min) / 2
    log_above_max = (log_max + log_mid_max) / 2
    return pd.Series([
        min_,
        np.exp(log_below_min),
        np.exp(log_mid_min),
        np.exp(log_mid_min_inner),
        np.exp(log_middle),
        np.exp(log_mid_max_inner),
        np.exp(log_mid_max),
        np.exp(log_above_max),
        max_
    ], index=[f'line_{i}' for i in range(1, 10)])


# ----------- CONDIÇÕES DE COMPRA E VENDA -----------
class EntradaLinha4(Compra):
    def avaliar(self, zonas: pd.Series, preco: float) -> bool:
        return preco >= zonas['line_4']

class StopLinha2(Venda):
    def avaliar(self, zonas: pd.Series, preco: float) -> bool:
        return preco <= zonas['line_2']

class AlvoLinha9(Venda):
    def avaliar(self, zonas: pd.Series, preco: float) -> bool:
        return preco >= zonas['line_9']


# ----------- ESTRATÉGIA ORIENTADA A OBJETOS -----------
class PeaksAndValleysStrategy(Estrategia):
    def executar(self, close: pd.Series, zonas_df: pd.DataFrame, freq: str) -> vbt.Portfolio:
        entries = pd.Series(False, index=zonas_df.index)
        exits = pd.Series(False, index=zonas_df.index)
        position_size = pd.Series(0.0, index=zonas_df.index)

        is_in_position = False
        drop_below_line2_flag = False

        for i in range(len(zonas_df)):
            index = zonas_df.index[i]
            preco = close.loc[index]
            zonas = zonas_df.iloc[i]

            if not is_in_position and preco <= zonas['line_2']:
                drop_below_line2_flag = True

            if not is_in_position and drop_below_line2_flag and EntradaLinha4().avaliar(zonas, preco):
                entries.loc[index] = True
                position_size.loc[index] = 1.0
                is_in_position = True
                drop_below_line2_flag = False
                continue

            if is_in_position and AlvoLinha9().avaliar(zonas, preco):
                exits.loc[index] = True
                is_in_position = False
                continue

            if is_in_position and StopLinha2().avaliar(zonas, preco):
                exits.loc[index] = True
                is_in_position = False
                drop_below_line2_flag = True
                continue

        return vbt.Portfolio.from_signals(
            close.loc[zonas_df.index],
            entries,
            exits,
            size=position_size,
            fees=0.001,
            slippage=0.001,
            freq=freq
        )


# ----------- FUNÇÃO COMPATÍVEL COM executor.py -----------
def backtest_strategy(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    rolling_min = close.rolling(lookback).min()
    rolling_max = close.rolling(lookback).max()
    zone_input = pd.concat([rolling_min.rename('min'), rolling_max.rename('max')], axis=1)
    zonas_df = zone_input.dropna().apply(calculate_log_zones, axis=1)

    strategy = PeaksAndValleysStrategy()
    return strategy.executar(close, zonas_df, freq=freq)

import numpy as np
import pandas as pd
import vectorbt as vbt

from strategy.strategy import Estrategia, Compra, Venda


# ----------- CÁLCULO DAS ZONAS LOGARÍTMICAS ----------- #
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


# ----------- NOVA ESTRATÉGIA COM FLAGS ----------- #
class PeaksAndValleysStrategy(Estrategia):
    def executar(self, close: pd.Series, zonas_df: pd.DataFrame, freq: str) -> vbt.Portfolio:
        entries = pd.Series(False, index=zonas_df.index)
        exits = pd.Series(False, index=zonas_df.index)
        position_size = pd.Series(0.0, index=zonas_df.index)

        is_in_position = False
        preco_entrada = None

        flag_1_ativa = False
        flag_2_ativa = False

        for i in range(len(zonas_df)):
            index = zonas_df.index[i]
            preco = close.loc[index]
            zonas = zonas_df.iloc[i]

            # → 1. Ativa flag_1 se tocar a linha 1
            if not is_in_position and preco <= zonas['line_1']:
                flag_1_ativa = True

            # → 2. Compra 1x se flag_1 ativa e preço toca linha 4
            if not is_in_position and flag_1_ativa and preco >= zonas['line_4']:
                entries.loc[index] = True
                position_size.loc[index] = 1.0
                is_in_position = True
                preco_entrada = preco
                continue

            # → 3. Stop da compra normal, ativa flag_2
            if is_in_position and flag_1_ativa and preco <= zonas['line_2']:
                exits.loc[index] = True
                is_in_position = False
                preco_entrada = None
                flag_1_ativa = False
                flag_2_ativa = True
                continue

            # → 4. Compra 10x se flag_2 ativa e preço toca linha 4
            if not is_in_position and flag_2_ativa and preco >= zonas['line_4']:
                entries.loc[index] = True
                position_size.loc[index] = 10.0
                is_in_position = True
                preco_entrada = preco
                continue

            # → 5. Stop da compra alavancada, desativa flag_2
            if is_in_position and flag_2_ativa and preco <= zonas['line_2']:
                exits.loc[index] = True
                is_in_position = False
                preco_entrada = None
                flag_2_ativa = False
                continue

            # → 6. Take profit se tocar linha 8, zera tudo
            if is_in_position and preco >= zonas['line_8']:
                exits.loc[index] = True
                is_in_position = False
                preco_entrada = None
                flag_1_ativa = False
                flag_2_ativa = False
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


# ----------- FUNÇÃO COMPATÍVEL COM executor.py ----------- #
def backtest_strategy(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    rolling_min = close.rolling(lookback).min()
    rolling_max = close.rolling(lookback).max()
    zone_input = pd.concat([rolling_min.rename('min'), rolling_max.rename('max')], axis=1)
    zonas_df = zone_input.dropna().apply(calculate_log_zones, axis=1)

    strategy = PeaksAndValleysStrategy()
    return strategy.executar(close, zonas_df, freq=freq)

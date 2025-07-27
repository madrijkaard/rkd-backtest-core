import numpy as np
import pandas as pd
import vectorbt as vbt

from strategy.strategy import Estrategia


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


# ----------- ESTRATÉGIA APENAS SHORT SEM ALAVANCAGEM ----------- #
class PeaksAndValleysStrategy(Estrategia):
    def executar(self, close: pd.Series, zonas_df: pd.DataFrame, freq: str) -> vbt.Portfolio:
        entries = pd.Series(np.nan, index=zonas_df.index)
        exits = pd.Series(False, index=zonas_df.index)

        is_in_position = False
        preco_entrada = None

        stop_losses_consecutivos = 0
        ganhos_consecutivos = 0
        mes_atual = None
        ignorar_mes = False

        aguardando_linha_6 = False
        sequencias_completas = 0

        for i in range(len(zonas_df)):
            index = zonas_df.index[i]
            preco = close.loc[index]
            zonas = zonas_df.iloc[i]
            mes = index.to_period("M")

            # Novo mês
            if mes != mes_atual:
                mes_atual = mes
                stop_losses_consecutivos = 0
                ganhos_consecutivos = 0
                ignorar_mes = False
                aguardando_linha_6 = False
                sequencias_completas = 0

            if ignorar_mes:
                continue

            # ---------- ENTRADA SHORT ----------
            if not is_in_position:
                if not aguardando_linha_6 and preco >= zonas['line_8']:
                    aguardando_linha_6 = True
                    continue

                if aguardando_linha_6 and preco <= zonas['line_6']:
                    sequencias_completas += 1
                    aguardando_linha_6 = False

                    if sequencias_completas == 3:
                        entries.loc[index] = -1  # Short com 1x
                        is_in_position = True
                        preco_entrada = preco
                        sequencias_completas = 0
                        continue

            # ---------- EXIT SHORT ----------
            if is_in_position:
                if preco >= zonas['line_8']:  # stop loss
                    exits.loc[index] = True
                    is_in_position = False
                    preco_entrada = None
                    aguardando_linha_6 = False
                    sequencias_completas = 0
                    stop_losses_consecutivos += 1
                    ganhos_consecutivos = 0
                    if stop_losses_consecutivos >= 2:
                        ignorar_mes = True
                    continue

                if preco <= zonas['line_3']:  # take profit
                    exits.loc[index] = True
                    is_in_position = False
                    preco_entrada = None
                    aguardando_linha_6 = False
                    sequencias_completas = 0
                    stop_losses_consecutivos = 0
                    ganhos_consecutivos += 1
                    if ganhos_consecutivos >= 2:
                        ignorar_mes = True
                    continue

        return vbt.Portfolio.from_signals(
            close.loc[zonas_df.index],
            entries=entries,
            exits=exits,
            fees=0.001,
            slippage=0.001,
            freq=freq
            # Sem 'size': assume tamanho 1x por padrão
        )


# ----------- FUNÇÃO COMPATÍVEL COM executor.py ----------- #
def backtest_strategy(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    rolling_min = close.rolling(lookback).min()
    rolling_max = close.rolling(lookback).max()
    zone_input = pd.concat([rolling_min.rename('min'), rolling_max.rename('max')], axis=1)
    zonas_df = zone_input.dropna().apply(calculate_log_zones, axis=1)

    strategy = PeaksAndValleysStrategy()
    return strategy.executar(close, zonas_df, freq=freq)

import numpy as np
import pandas as pd
import vectorbt as vbt
from collections import defaultdict

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


# ----------- CONDIÇÕES DE COMPRA E VENDA ----------- #
class EntradaLinha4(Compra):
    def avaliar(self, zonas: pd.Series, preco: float) -> bool:
        return preco >= zonas['line_4']


class StopLinha2(Venda):
    def avaliar(self, zonas: pd.Series, preco: float) -> bool:
        return preco <= zonas['line_2']


# ----------- FUNÇÃO PARA IDENTIFICAR ZONA DO CORPO ----------- #
def identificar_zona(zonas: pd.Series, preco1: float, preco2: float) -> int | None:
    corpo_min = min(preco1, preco2)
    corpo_max = max(preco1, preco2)
    for i in range(1, 9):
        linha_inferior = zonas[f'line_{i}']
        linha_superior = zonas[f'line_{i + 1}']
        if corpo_min >= linha_inferior and corpo_max <= linha_superior:
            return i
    return None


# ----------- ESTRATÉGIA PRINCIPAL ----------- #
class PeaksAndValleysStrategy(Estrategia):
    def executar(self, close: pd.Series, zonas_df: pd.DataFrame, freq: str) -> vbt.Portfolio:
        entries = pd.Series(False, index=zonas_df.index)
        exits = pd.Series(False, index=zonas_df.index)
        position_size = pd.Series(0.0, index=zonas_df.index)

        is_in_position = False
        preco_entrada = None
        preco_anterior = None

        drop_below_line1_flag = False
        primeira_ocorrencia_flag = False
        entrada_alavancada_feita = False

        ciclo_bloqueado = False
        zona_anterior = None
        contador_zona = 0

        stop_count = 0

        trades_por_mes = defaultdict(int)
        lucro_por_mes = defaultdict(float)

        for i in range(len(zonas_df)):
            index = zonas_df.index[i]
            preco = close.loc[index]
            zonas = zonas_df.iloc[i]
            ano_mes = index.strftime('%Y-%m')

            # 🔒 Bloqueio mensal se já teve 2 trades e está positivo
            if not is_in_position and trades_por_mes[ano_mes] >= 2 and lucro_por_mes[ano_mes] > 0:
                preco_anterior = preco
                continue

            # 🔓 Desbloqueio após 20 candles na mesma zona
            zona_atual = identificar_zona(zonas, preco, preco_anterior if preco_anterior else preco)
            if ciclo_bloqueado:
                if zona_atual is not None and zona_atual == zona_anterior:
                    contador_zona += 1
                else:
                    contador_zona = 1
                    zona_anterior = zona_atual

                if contador_zona >= 20:
                    ciclo_bloqueado = False
                    contador_zona = 0
                    zona_anterior = None
                else:
                    preco_anterior = preco
                    continue

            # 🎯 Gatilho de queda abaixo da line_1
            if not is_in_position and preco_anterior is not None:
                if preco_anterior > zonas['line_1'] and preco <= zonas['line_1']:
                    drop_below_line1_flag = True

            # ✅ Entrada normal
            if not is_in_position and drop_below_line1_flag and EntradaLinha4().avaliar(zonas, preco):
                if not primeira_ocorrencia_flag:
                    primeira_ocorrencia_flag = True
                    drop_below_line1_flag = False
                else:
                    entries.loc[index] = True
                    position_size.loc[index] = 1.0
                    is_in_position = True
                    preco_entrada = preco
                    drop_below_line1_flag = False
                    primeira_ocorrencia_flag = False
                preco_anterior = preco
                continue

            # ⚡ Entrada alavancada após 1º stop
            if not is_in_position and stop_count == 1 and not entrada_alavancada_feita and EntradaLinha4().avaliar(zonas, preco):
                entries.loc[index] = True
                position_size.loc[index] = 5.0
                is_in_position = True
                preco_entrada = preco
                entrada_alavancada_feita = True
                preco_anterior = preco
                continue

            # 💰 Take Profit
            if is_in_position and preco_entrada is not None and preco >= preco_entrada * 1.02:
                exits.loc[index] = True
                is_in_position = False
                lucro = (preco - preco_entrada) * position_size.loc[index]
                lucro_por_mes[ano_mes] += lucro
                trades_por_mes[ano_mes] += 1
                preco_entrada = None
                stop_count = 0
                entrada_alavancada_feita = False
                preco_anterior = preco
                continue

            # ❌ Stop Loss
            if is_in_position and StopLinha2().avaliar(zonas, preco):
                exits.loc[index] = True
                is_in_position = False
                lucro = (preco - preco_entrada) * position_size.loc[index]
                lucro_por_mes[ano_mes] += lucro
                trades_por_mes[ano_mes] += 1
                preco_entrada = None
                stop_count += 1
                preco_anterior = preco

                if stop_count >= 2:
                    ciclo_bloqueado = True
                    contador_zona = 0
                    zona_anterior = None
                continue

            preco_anterior = preco

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

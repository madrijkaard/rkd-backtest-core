import numpy as np
import pandas as pd
import vectorbt as vbt

def calc_zonas(row: pd.Series) -> pd.Series:
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

def estrategia_duplo_reteste(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    price_min = close.rolling(lookback).min()
    price_max = close.rolling(lookback).max()
    zona_df = pd.concat([price_min.rename('min'), price_max.rename('max')], axis=1)
    zonas = zona_df.dropna().apply(calc_zonas, axis=1)
    ma200 = close.rolling(200).mean()

    entries = pd.Series(False, index=zonas.index)
    exits = pd.Series(False, index=zonas.index)
    position_size = pd.Series(0.0, index=zonas.index)

    comprado = False
    contador_padroes = 0
    flag_queda = False
    preco_entrada = None
    entrou_por_line9 = False

    for i in range(lookback + 200, len(zonas)):
        idx = close.index[i]
        preco = close.iloc[i]
        z = zonas.iloc[i]
        media = ma200.iloc[i]

        # ---------- Entrada pela estratégia de duplo reteste ----------
        if preco <= z['line_2']:
            flag_queda = True

        elif preco >= z['line_4'] and flag_queda:
            contador_padroes += 1
            flag_queda = False

            if not comprado and contador_padroes == 2:
                entries[idx] = True
                comprado = True
                preco_entrada = preco
                position_size[idx] = 30
                entrou_por_line9 = False
                contador_padroes = 0
                continue

        # ---------- Entrada pela line_9 acima da média ----------
        if not comprado and preco >= z['line_9'] and preco > media:
            entries[idx] = True
            comprado = True
            preco_entrada = preco
            position_size[idx] = 1
            entrou_por_line9 = True
            contador_padroes = 0
            continue

        # ---------- Saída (STOP) para duplo reteste ----------
        if comprado and preco <= z['line_2'] and not entrou_por_line9:
            exits[idx] = True
            comprado = False
            preco_entrada = None
            contador_padroes = 0
            entrou_por_line9 = False
            continue

        # ---------- Saída (STOP) para entrada por line_9 ----------
        if comprado and entrou_por_line9 and preco <= z['line_6']:
            exits[idx] = True
            comprado = False
            preco_entrada = None
            contador_padroes = 0
            entrou_por_line9 = False
            continue

        # ---------- Saída (ALVO de 4%) para entrada por line_9 ----------
        if comprado and entrou_por_line9 and preco_entrada and preco >= preco_entrada * 1.04:
            exits[idx] = True
            comprado = False
            preco_entrada = None
            contador_padroes = 0
            entrou_por_line9 = False
            continue

        # ---------- Saída (ALVO de 5%) para entrada por reteste ----------
        if comprado and not entrou_por_line9 and preco_entrada and preco >= preco_entrada * 1.05:
            exits[idx] = True
            comprado = False
            preco_entrada = None
            contador_padroes = 0
            entrou_por_line9 = False
            continue

    pf = vbt.Portfolio.from_signals(
        close.loc[zonas.index],
        entries,
        exits,
        size=position_size,
        fees=0.001,
        slippage=0.001,
        freq=freq
    )

    return pf

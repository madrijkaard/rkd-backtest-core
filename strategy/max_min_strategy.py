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

def estrategia_max_min(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    price_min = close.rolling(lookback).min()
    price_max = close.rolling(lookback).max()
    zona_df = pd.concat([price_min.rename('min'), price_max.rename('max')], axis=1)
    zonas = zona_df.dropna().apply(calc_zonas, axis=1)

    entries = pd.Series(False, index=zonas.index)
    exits = pd.Series(False, index=zonas.index)
    position_size = pd.Series(0.0, index=zonas.index)

    comprado = False
    queda_recente_abaixo_line2 = False
    modo_alavancagem_10x = False
    alavancagem = 1
    stop_loss_count = 0

    for i in range(lookback, len(zonas)):
        idx = close.index[i]
        preco = close.iloc[i]
        z = zonas.iloc[i]
        alvo = z['line_5'] if stop_loss_count >= 2 else z['line_9']

        if preco <= z['line_2']:
            queda_recente_abaixo_line2 = True
            if comprado:
                exits[idx] = True
                comprado = False
                stop_loss_count += 1
                modo_alavancagem_10x = True
                continue

        if not comprado and queda_recente_abaixo_line2 and preco >= z['line_4']:
            entries[idx] = True
            comprado = True
            alavancagem = 10 if modo_alavancagem_10x else 1
            position_size[idx] = alavancagem
            queda_recente_abaixo_line2 = False
            continue

        if comprado and preco >= alvo:
            exits[idx] = True
            comprado = False
            alavancagem = 1
            stop_loss_count = 0
            modo_alavancagem_10x = False
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

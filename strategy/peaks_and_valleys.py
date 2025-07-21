import numpy as np
import pandas as pd
import vectorbt as vbt

# Calculate logarithmic zones between rolling min and max
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

# Check if all real candle bodies are inside the same zone (exclude wicks)
def are_real_bodies_inside_same_zone(open_, close_, zones):
    body_low = np.minimum(open_, close_)
    body_high = np.maximum(open_, close_)
    for i in range(1, 9):
        lower = zones[f'line_{i}']
        upper = zones[f'line_{i+1}']
        if np.all((body_low >= lower) & (body_high <= upper)):
            return True
    return False

# Main backtest strategy
def backtest_strategy(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    rolling_min = close.rolling(lookback).min()
    rolling_max = close.rolling(lookback).max()
    zone_input = pd.concat([rolling_min.rename('min'), rolling_max.rename('max')], axis=1)
    zones = zone_input.dropna().apply(calculate_log_zones, axis=1)
    ma_200 = close.rolling(200).mean()

    entries = pd.Series(False, index=zones.index)
    exits = pd.Series(False, index=zones.index)
    position_size = pd.Series(0.0, index=zones.index)

    is_in_position = False
    recent_drop_below_line2 = False
    event_counter = 0
    consolidation_entry_active = False
    consolidation_entry_price = None

    touched_line_9 = False
    entry_after_line9 = False
    entry_price_line9 = None

    for i in range(lookback, len(zones)):
        current_index = close.index[i]
        current_price = close.iloc[i]
        current_zone = zones.iloc[i]

        # -------- FLAG TOQUE NA LINE 9 --------
        if not touched_line_9 and current_price >= current_zone['line_9'] and current_price > ma_200.iloc[i]:
            touched_line_9 = True

        # -------- ENTRADA APÓS TOQUE LINE 9 + PULLBACK EM LINE 6 --------
        if not is_in_position and touched_line_9 and current_price <= current_zone['line_6'] and current_price > ma_200.iloc[i]:
            entries[current_index] = True
            is_in_position = True
            position_size[current_index] = 1
            entry_after_line9 = True
            entry_price_line9 = current_price
            continue

        # -------- SAÍDA SE TOCAR LINE 5 APÓS ENTRADA PÓS LINE 9 --------
        if is_in_position and entry_after_line9 and current_price <= current_zone['line_5']:
            exits[current_index] = True
            is_in_position = False
            entry_after_line9 = False
            touched_line_9 = False
            entry_price_line9 = None
            continue

        # -------- GAIN DE 8% APÓS ENTRADA PÓS LINE 9 --------
        if is_in_position and entry_after_line9 and entry_price_line9 and current_price >= entry_price_line9 * 1.08:
            exits[current_index] = True
            is_in_position = False
            entry_after_line9 = False
            touched_line_9 = False
            entry_price_line9 = None
            continue

        # -------- ENTRADA POR CONSOLIDAÇÃO --------
        if not is_in_position and i >= 200 + 20:
            window_indices = close.index[i-20:i]
            recent_opens = close.loc[window_indices].shift(1)
            recent_closes = close.loc[window_indices]
            recent_zones = zones.iloc[i-20:i]

            if current_price > ma_200.iloc[i]:
                all_bodies_in_same_zone = all([
                    are_real_bodies_inside_same_zone(
                        recent_opens.values, recent_closes.values, recent_zones.iloc[j]
                    ) for j in range(20)
                ])
                if all_bodies_in_same_zone:
                    entries[current_index] = True
                    is_in_position = True
                    position_size[current_index] = 1
                    consolidation_entry_active = True
                    consolidation_entry_price = current_price
                    continue

        # -------- DROP-RECOVERY ENTRY --------
        if current_price <= current_zone['line_2']:
            recent_drop_below_line2 = True

            if is_in_position:
                exits[current_index] = True
                is_in_position = False

                if position_size.iloc[i - 1] == 30:
                    event_counter = 0
                else:
                    event_counter += 1

                consolidation_entry_active = False
                consolidation_entry_price = None
                continue

        if not is_in_position and recent_drop_below_line2 and current_price >= current_zone['line_4']:
            event_counter += 1
            recent_drop_below_line2 = False

            if event_counter == 2:
                entries[current_index] = True
                is_in_position = True
                position_size[current_index] = 1
                continue

            if event_counter == 3:
                entries[current_index] = True
                is_in_position = True
                position_size[current_index] = 30
                continue

        # -------- TAKE PROFIT PADRÃO PARA DROP-RECOVERY --------
        if is_in_position and current_price >= current_zone['line_6'] and not consolidation_entry_active and not entry_after_line9:
            exits[current_index] = True
            is_in_position = False
            event_counter = 0
            continue

        # -------- SAÍDA CONSOLIDAÇÃO --------
        if is_in_position and consolidation_entry_active:
            if current_price < current_zone['line_3']:
                exits[current_index] = True
                is_in_position = False
                consolidation_entry_active = False
                consolidation_entry_price = None
                continue

            if consolidation_entry_price and current_price >= consolidation_entry_price * 1.08:
                exits[current_index] = True
                is_in_position = False
                consolidation_entry_active = False
                consolidation_entry_price = None
                continue

    portfolio = vbt.Portfolio.from_signals(
        close.loc[zones.index],
        entries,
        exits,
        size=position_size,
        fees=0.001,
        slippage=0.001,
        freq=freq
    )

    return portfolio

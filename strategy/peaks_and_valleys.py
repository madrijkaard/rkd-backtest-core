import numpy as np
import pandas as pd
import vectorbt as vbt

from strategy.strategy import Strategy


# ----------- LOGARITHMIC ZONE CALCULATION ----------- #
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


# ----------- SHORT-ONLY STRATEGY WITHOUT LEVERAGE ----------- #
class PeaksAndValleysStrategy(Strategy):
    def execute(self, close: pd.Series, zones_df: pd.DataFrame, freq: str) -> vbt.Portfolio:
        entries = pd.Series(np.nan, index=zones_df.index)
        exits = pd.Series(False, index=zones_df.index)

        in_position = False
        entry_price = None

        consecutive_losses = 0
        consecutive_wins = 0
        current_month = None
        ignore_month = False

        waiting_line_6 = False
        complete_sequences = 0

        for i in range(len(zones_df)):
            index = zones_df.index[i]
            price = close.loc[index]
            zones = zones_df.iloc[i]
            month = index.to_period("M")

            # New month: reset counters
            if month != current_month:
                current_month = month
                consecutive_losses = 0
                consecutive_wins = 0
                ignore_month = False
                waiting_line_6 = False
                complete_sequences = 0

            if ignore_month:
                continue

            # ---------- SHORT ENTRY ----------
            if not in_position:
                if not waiting_line_6 and price >= zones['line_8']:
                    waiting_line_6 = True
                    continue

                if waiting_line_6 and price <= zones['line_6']:
                    complete_sequences += 1
                    waiting_line_6 = False

                    if complete_sequences == 3:
                        entries.loc[index] = -1  # Short with 1x
                        in_position = True
                        entry_price = price
                        complete_sequences = 0
                        continue

            # ---------- SHORT EXIT ----------
            if in_position:
                if price >= zones['line_8']:  # Stop loss
                    exits.loc[index] = True
                    in_position = False
                    entry_price = None
                    waiting_line_6 = False
                    complete_sequences = 0
                    consecutive_losses += 1
                    consecutive_wins = 0
                    if consecutive_losses >= 2:
                        ignore_month = True
                    continue

                if price <= zones['line_3']:  # Take profit
                    exits.loc[index] = True
                    in_position = False
                    entry_price = None
                    waiting_line_6 = False
                    complete_sequences = 0
                    consecutive_losses = 0
                    consecutive_wins += 1
                    if consecutive_wins >= 2:
                        ignore_month = True
                    continue

        return vbt.Portfolio.from_signals(
            close.loc[zones_df.index],
            entries=entries,
            exits=exits,
            fees=0.001,
            slippage=0.001,
            freq=freq
        )


# ----------- FUNCTION COMPATIBLE WITH executor.py ----------- #
def backtest_strategy(close: pd.Series, lookback: int, freq: str) -> vbt.Portfolio:
    rolling_min = close.rolling(lookback).min()
    rolling_max = close.rolling(lookback).max()
    zone_input = pd.concat([rolling_min.rename('min'), rolling_max.rename('max')], axis=1)
    zones_df = zone_input.dropna().apply(calculate_log_zones, axis=1)

    strategy = PeaksAndValleysStrategy()
    return strategy.execute(close, zones_df, freq=freq)

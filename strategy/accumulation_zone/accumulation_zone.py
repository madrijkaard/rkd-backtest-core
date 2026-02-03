# strategy/accumulation_zone/accumulation_zone.py

import numpy as np
import yaml
import os
import random

# ============================================================
# LOAD STRATEGY CONFIG
# ============================================================

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

STRATEGY_CFG = config["strategy"]

TOTAL_ZONES = STRATEGY_CFG["zones"]["total"]
TOP_ACTIVE = STRATEGY_CFG["zones"]["top_active"]
BOTTOM_ACTIVE = STRATEGY_CFG["zones"]["bottom_active"]

TARGET_LONG_OFFSET = STRATEGY_CFG["targets"]["long"]
TARGET_SHORT_OFFSET = STRATEGY_CFG["targets"]["short"]

# ============================================================
# Helpers
# ============================================================

def zones_in_sequence(zones):
    zones = sorted(zones)
    return zones[1] == zones[0] + 1 and zones[2] == zones[1] + 1


def percentage_since_last_extreme(window):
    high_idx = np.argmax(window)
    low_idx = np.argmin(window)
    last_extreme_idx = max(high_idx, low_idx)
    dist = len(window) - last_extreme_idx - 1
    return (dist / len(window)) * 100


def compute_log_zones(price_min, price_max, n_zones):
    log_min = np.log(price_min)
    log_max = np.log(price_max)
    levels = np.linspace(log_min, log_max, n_zones + 1)
    return np.exp(levels)


def get_less_active_zones(activity, bottom_active):
    sorted_indices = np.argsort(activity)
    cutoff_index = sorted_indices[bottom_active - 1]
    cutoff_value = activity[cutoff_index]

    strictly_lower = np.where(activity < cutoff_value)[0].tolist()
    equal_cutoff = np.where(activity == cutoff_value)[0].tolist()

    remaining = bottom_active - len(strictly_lower)
    selected_equal = random.sample(equal_cutoff, remaining) if remaining > 0 else []

    return sorted(strictly_lower + selected_equal)

# ============================================================
# Estratégia principal (MODELO REATIVO)
# ============================================================

def log_zones_activity_strategy(
    open_,
    high,
    low,
    close,
    lookback=200,
    max_loss_percent=None,
    min_percent_from_extreme=55.0
):
    n = len(close)

    entries_long = np.zeros(n, dtype=bool)
    exits_long = np.zeros(n, dtype=bool)
    entries_short = np.zeros(n, dtype=bool)
    exits_short = np.zeros(n, dtype=bool)

    in_long = False
    in_short = False

    entry_price = None
    stop_price = None
    target_price = None

    for i in range(lookback - 1, n):

        # ====================================================
        # Gerenciamento de posição (intra-candle)
        # ====================================================
        if in_long:
            if low[i] <= stop_price:
                exits_long[i] = True
                in_long = False
            elif high[i] >= target_price:
                exits_long[i] = True
                in_long = False

        if in_short:
            if high[i] >= stop_price:
                exits_short[i] = True
                in_short = False
            elif low[i] <= target_price:
                exits_short[i] = True
                in_short = False

        if in_long or in_short:
            continue

        # ====================================================
        # Janela REATIVA (inclui candle atual)
        # ====================================================
        start = i - lookback + 1
        end = i + 1

        window_close = close[start:end]
        window_open  = open_[start:end]
        window_low   = low[start:end]
        window_high  = high[start:end]

        if percentage_since_last_extreme(window_close) < min_percent_from_extreme:
            continue

        price_min = window_low.min()
        price_max = window_high.max()

        limits = compute_log_zones(price_min, price_max, TOTAL_ZONES)
        activity = np.zeros(TOTAL_ZONES)

        for j in range(len(window_close)):
            body_low = min(window_open[j], window_close[j])
            body_high = max(window_open[j], window_close[j])

            for z in range(TOTAL_ZONES):
                overlap_low = max(body_low, limits[z])
                overlap_high = min(body_high, limits[z + 1])

                if overlap_high > overlap_low:
                    activity[z] += (overlap_high - overlap_low) / body_low

        top_zones = np.argsort(activity)[-TOP_ACTIVE:]

        if TOP_ACTIVE != 3 or not zones_in_sequence(top_zones):
            continue

        top_sorted = sorted(top_zones)
        central_zone = top_sorted[1]

        less_active = get_less_active_zones(activity, BOTTOM_ACTIVE)

        # ====================================================
        # LONG
        # ====================================================
        if central_zone + TARGET_LONG_OFFSET < len(limits):
            level = limits[central_zone + 1]

            crossed_up = close[i - 1] <= level and close[i] > level

            if crossed_up:
                entry_price = level
                stop_price = (limits[central_zone] + level) / 2
                target_price = limits[central_zone + TARGET_LONG_OFFSET]

                if max_loss_percent:
                    loss = (entry_price - stop_price) / entry_price * 100
                    if loss > max_loss_percent:
                        continue

                entries_long[i] = True
                in_long = True
                continue

        # ====================================================
        # SHORT
        # ====================================================
        if central_zone - TARGET_SHORT_OFFSET >= 0:
            level = limits[central_zone]

            crossed_down = close[i - 1] >= level and close[i] < level

            if crossed_down:
                entry_price = level
                stop_price = (limits[central_zone] + limits[central_zone + 1]) / 2
                target_price = limits[central_zone - TARGET_SHORT_OFFSET]

                if max_loss_percent:
                    loss = (stop_price - entry_price) / entry_price * 100
                    if loss > max_loss_percent:
                        continue

                entries_short[i] = True
                in_short = True
                continue

    exits_long |= entries_short
    exits_short |= entries_long

    conflict = entries_long & entries_short
    entries_long[conflict] = False
    entries_short[conflict] = False
    exits_long[conflict] = False
    exits_short[conflict] = False

    return entries_long, exits_long, entries_short, exits_short


def backtest_strategy(
    data,
    lookback=200,
    max_loss_percent=None,
    min_percent_from_extreme=55.0
):
    return log_zones_activity_strategy(
        open_=data["open"].values,
        high=data["high"].values,
        low=data["low"].values,
        close=data["close"].values,
        lookback=lookback,
        max_loss_percent=max_loss_percent,
        min_percent_from_extreme=min_percent_from_extreme
    )

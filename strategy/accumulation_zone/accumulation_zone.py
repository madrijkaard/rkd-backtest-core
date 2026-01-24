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

# ----------------------------
# Core params
# ----------------------------
TOTAL_ZONES = STRATEGY_CFG["zones"]["total"]
TOP_ACTIVE = STRATEGY_CFG["zones"]["top_active"]
BOTTOM_ACTIVE = STRATEGY_CFG["zones"]["bottom_active"]

# ----------------------------
# Targets (ZONE OFFSETS)
# ----------------------------
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


def get_less_active_zones(activity: np.ndarray, bottom_active: int):
    """
    Retorna exatamente 'bottom_active' zonas menos ativas.
    Em caso de empate que exceda o limite, sorteia.
    """
    sorted_indices = np.argsort(activity)
    cutoff_index = sorted_indices[bottom_active - 1]
    cutoff_value = activity[cutoff_index]

    strictly_lower = np.where(activity < cutoff_value)[0].tolist()
    equal_cutoff = np.where(activity == cutoff_value)[0].tolist()

    remaining = bottom_active - len(strictly_lower)

    if remaining > 0:
        selected_equal = random.sample(equal_cutoff, remaining)
    else:
        selected_equal = []

    return sorted(strictly_lower + selected_equal)

# ============================================================
# Estratégia principal
# ============================================================

def log_zones_activity_strategy(
    close,
    open_,
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

    stop_long = None
    stop_short = None
    target_long = None
    target_short = None

    for i in range(lookback, n):

        price_prev = close[i - 1]
        price_now = close[i]

        # ====================================================
        # Gerenciamento de posição
        # ====================================================
        if in_long:
            if price_now <= stop_long or price_now >= target_long:
                exits_long[i] = True
                in_long = False
                stop_long = None
                target_long = None

        if in_short:
            if price_now >= stop_short or price_now <= target_short:
                exits_short[i] = True
                in_short = False
                stop_short = None
                target_short = None

        if in_long or in_short:
            continue

        # ====================================================
        # Janela de candles
        # ====================================================
        window_close = close[i - lookback:i]
        window_open = open_[i - lookback:i]

        if percentage_since_last_extreme(window_close) < min_percent_from_extreme:
            continue

        price_min = window_close.min()
        price_max = window_close.max()

        limits = compute_log_zones(price_min, price_max, TOTAL_ZONES)
        activity = np.zeros(TOTAL_ZONES)

        # ====================================================
        # Calcular atividade por zona
        # ====================================================
        for j in range(lookback):
            body_low = min(window_open[j], window_close[j])
            body_high = max(window_open[j], window_close[j])

            for z in range(TOTAL_ZONES):
                zone_low = limits[z]
                zone_high = limits[z + 1]

                overlap_low = max(body_low, zone_low)
                overlap_high = min(body_high, zone_high)

                if overlap_high > overlap_low:
                    activity[z] += (overlap_high - overlap_low) / body_low

        # ====================================================
        # Top zonas mais ativas
        # ====================================================
        sorted_zones = np.argsort(activity)
        top_zones = sorted_zones[-TOP_ACTIVE:]

        if TOP_ACTIVE != 3 or not zones_in_sequence(top_zones):
            continue

        top_sorted = sorted(top_zones)
        central_zone = top_sorted[1]

        # ====================================================
        # Zonas menos ativas (bloqueio)
        # ====================================================
        less_active_zones = get_less_active_zones(activity, BOTTOM_ACTIVE)

        above_zone = top_sorted[-1] + 1
        below_zone = top_sorted[0] - 1

        block_long = above_zone in less_active_zones
        block_short = below_zone in less_active_zones

        # ====================================================
        # LONG
        # ====================================================
        if not block_long and central_zone + TARGET_LONG_OFFSET < len(limits):
            crossed_up = (
                price_prev <= limits[central_zone + 1]
                and price_now > limits[central_zone + 1]
            )

            if crossed_up:
                stop_candidate = (
                    limits[central_zone] + limits[central_zone + 1]
                ) / 2

                target_candidate = limits[central_zone + TARGET_LONG_OFFSET]

                if max_loss_percent is not None:
                    stop_loss_percent = (
                        (price_now - stop_candidate) / price_now
                    ) * 100

                    if stop_loss_percent > max_loss_percent:
                        continue

                entries_long[i] = True
                in_long = True
                stop_long = stop_candidate
                target_long = target_candidate
                continue

        # ====================================================
        # SHORT
        # ====================================================
        if not block_short and central_zone - TARGET_SHORT_OFFSET >= 0:
            crossed_down = (
                price_prev >= limits[central_zone]
                and price_now < limits[central_zone]
            )

            if crossed_down:
                stop_candidate = (
                    limits[central_zone] + limits[central_zone + 1]
                ) / 2

                target_candidate = limits[central_zone - TARGET_SHORT_OFFSET]

                if max_loss_percent is not None:
                    stop_loss_percent = (
                        (stop_candidate - price_now) / price_now
                    ) * 100

                    if stop_loss_percent > max_loss_percent:
                        continue

                entries_short[i] = True
                in_short = True
                stop_short = stop_candidate
                target_short = target_candidate
                continue

    # ========================================================
    # Flip de posição
    # ========================================================
    exits_long |= entries_short
    exits_short |= entries_long

    conflict = entries_long & entries_short
    entries_long[conflict] = False
    entries_short[conflict] = False
    exits_long[conflict] = False
    exits_short[conflict] = False

    return entries_long, exits_long, entries_short, exits_short

# ============================================================
# Wrapper esperado por outros módulos
# ============================================================

def backtest_strategy(
    data,
    lookback=200,
    max_loss_percent=None,
    min_percent_from_extreme=55.0
):
    close = data["close"].values
    open_ = data["open"].values

    return log_zones_activity_strategy(
        close=close,
        open_=open_,
        lookback=lookback,
        max_loss_percent=max_loss_percent,
        min_percent_from_extreme=min_percent_from_extreme
    )

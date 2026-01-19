# strategy/log_zones_activity.py

import numpy as np
import yaml
import os

# ============================================================
# LOAD CONFIG (para pegar zones.total e min_percent_from_extreme)
# ============================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

TOTAL_ZONES = config["strategy"]["zones"]["total"]  # usa valor do YAML
MIN_PERCENT_FROM_EXTREME = config["strategy"]["activity"]["min_percent_from_extreme"]

# ============================================================
# Helpers
# ============================================================

def zones_in_sequence(zones):
    """Verifica se 3 zonas estão em sequência."""
    zones = sorted(zones)
    return zones[1] == zones[0] + 1 and zones[2] == zones[1] + 1

def percentage_since_last_extreme(window):
    """Calcula o percentual de candles desde o último máximo ou mínimo."""
    high_idx = np.argmax(window)
    low_idx = np.argmin(window)
    last_extreme_idx = max(high_idx, low_idx)
    dist = len(window) - last_extreme_idx - 1
    return (dist / len(window)) * 100

def compute_log_zones(price_min, price_max, n_zones):
    """Calcula os níveis das zonas logarítmicas."""
    log_min = np.log(price_min)
    log_max = np.log(price_max)
    levels = np.linspace(log_min, log_max, n_zones + 1)  # n_zones+1 para criar limites
    return np.exp(levels)

# ============================================================
# Estratégia principal
# ============================================================

def log_zones_activity_strategy(close, open_, lookback=200, max_loss_percent=None):
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

    N_ZONES = TOTAL_ZONES  # usa do YAML, ex: 8

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

        # Usa o valor do YAML para validar trade
        if percentage_since_last_extreme(window_close) < MIN_PERCENT_FROM_EXTREME:
            continue

        price_min = window_close.min()
        price_max = window_close.max()
        limits = compute_log_zones(price_min, price_max, N_ZONES)
        activity = np.zeros(N_ZONES)

        # ====================================================
        # Calcular atividade de cada zona
        # ====================================================
        for j in range(i - lookback, i):
            body_low = min(open_[j], close[j])
            body_high = max(open_[j], close[j])

            for z in range(N_ZONES):
                zone_low = limits[z]
                zone_high = limits[z + 1]
                overlap_low = max(body_low, zone_low)
                overlap_high = min(body_high, zone_high)
                if overlap_high > overlap_low:
                    activity[z] += (overlap_high - overlap_low) / body_low

        # ====================================================
        # Seleção das 3 zonas mais ativas
        # ====================================================
        sorted_zones = np.argsort(activity)
        top3 = sorted_zones[-3:]

        if not zones_in_sequence(top3):
            continue

        top3_sorted = sorted(top3)
        central_zone = top3_sorted[1]  # zona central

        # ====================================================
        # Identificação das zonas menos ativas
        # ====================================================
        min_activity = np.min(activity)
        less_active_zones = np.where(activity == min_activity)[0]

        # ====================================================
        # Critérios de bloqueio
        # ====================================================
        above_zone = top3_sorted[-1] + 1
        below_zone = top3_sorted[0] - 1

        block_long = above_zone in less_active_zones
        block_short = below_zone in less_active_zones

        # ====================================================
        # Long
        # ====================================================
        if not block_long and central_zone + 2 < N_ZONES:
            crossed_up = price_prev <= limits[central_zone + 1] and price_now > limits[central_zone + 1]
            if crossed_up:
                stop_candidate = (limits[central_zone] + limits[central_zone + 1]) / 2
                target_candidate = limits[central_zone + 2 + 1] if (central_zone + 2 + 1 <= N_ZONES) else limits[-1]

                # Checa max_loss_percent
                if max_loss_percent is not None:
                    stop_loss_percent = ((price_now - stop_candidate) / price_now) * 100
                    if stop_loss_percent > max_loss_percent:
                        continue

                entries_long[i] = True
                in_long = True
                stop_long = stop_candidate
                target_long = target_candidate
                continue

        # ====================================================
        # Short
        # ====================================================
        if not block_short and central_zone - 2 >= 0:
            crossed_down = price_prev >= limits[central_zone] and price_now < limits[central_zone]
            if crossed_down:
                stop_candidate = (limits[central_zone] + limits[central_zone + 1]) / 2
                target_candidate = limits[central_zone - 2]

                # Checa max_loss_percent
                if max_loss_percent is not None:
                    stop_loss_percent = ((stop_candidate - price_now) / price_now) * 100
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
# Wrapper esperado pelo executor.py
# ============================================================

def backtest_strategy(data, lookback=200, max_loss_percent=None):
    close = data["close"].values
    open_ = data["open"].values

    return log_zones_activity_strategy(
        close=close,
        open_=open_,
        lookback=lookback,
        max_loss_percent=max_loss_percent
    )

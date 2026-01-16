# strategy/log_zones_activity.py

import numpy as np


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


# ============================================================
# Estratégia principal (MODELO CORRIGIDO – 7 ZONAS REAIS)
# ============================================================

def log_zones_activity_strategy(close, open_, lookback=200):

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

    # 🔴 MODELO CORRETO: 7 zonas (0 a 6)
    N_ZONES = 7

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
        # Estrutura de mercado
        # ====================================================

        window_close = close[i - lookback:i]

        if percentage_since_last_extreme(window_close) < 40:
            continue

        price_min = window_close.min()
        price_max = window_close.max()

        limits = compute_log_zones(price_min, price_max, N_ZONES)
        activity = np.zeros(N_ZONES)

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

        # precisam ser sequenciais
        if not zones_in_sequence(top3):
            continue

        top3_sorted = sorted(top3)
        central_zone = top3_sorted[1]

        central_low = limits[central_zone]
        central_high = limits[central_zone + 1]
        central_mid = (central_low + central_high) / 2

        # ====================================================
        # 🟢 LONG — SÓ SE EXISTIR ZONA +2
        # ====================================================

        if central_zone + 2 < N_ZONES:
            crossed_up = price_prev <= central_high and price_now > central_high

            if crossed_up:
                entries_long[i] = True
                in_long = True
                stop_long = central_mid
                target_long = limits[central_zone + 2 + 1]  # topo da zona +2
                continue

        # ====================================================
        # 🔴 SHORT — SÓ SE EXISTIR ZONA -2
        # ====================================================

        if central_zone - 2 >= 0:
            crossed_down = price_prev >= central_low and price_now < central_low

            if crossed_down:
                entries_short[i] = True
                in_short = True
                stop_short = central_mid
                target_short = limits[central_zone - 2]  # fundo da zona -2
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

def backtest_strategy(data, lookback=200):
    close = data["close"].values
    open_ = data["open"].values

    return log_zones_activity_strategy(
        close=close,
        open_=open_,
        lookback=lookback
    )

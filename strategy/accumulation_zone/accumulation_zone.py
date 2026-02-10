import numpy as np
import yaml
import os

# ============================================================
# LOAD STRATEGY CONFIG
# ============================================================

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

STRATEGY_CFG = config["strategy"]

TOTAL_ZONES = STRATEGY_CFG["zones"]["total"]
TOP_ACTIVE = STRATEGY_CFG["zones"]["top_active"]        # normalmente 3
BOTTOM_ACTIVE = STRATEGY_CFG["zones"]["bottom_active"]  # normalmente 2

TARGET_LONG_OFFSET = STRATEGY_CFG["targets"]["long"]
TARGET_SHORT_OFFSET = STRATEGY_CFG["targets"]["short"]

# ============================================================
# Helpers (Pine-like)
# ============================================================

def zones_in_sequence(zones):
    zones = sorted(zones)
    return zones[1] == zones[0] + 1 and zones[2] == zones[1] + 1


def percentage_since_last_extreme(window):
    high_idx = np.argmax(window)
    low_idx = np.argmin(window)
    last_extreme_idx = max(high_idx, low_idx)
    dist = len(window) - last_extreme_idx - 1
    return (dist / len(window)) * 100.0


def compute_log_zones(price_min, price_max, n_zones):
    log_min = np.log(price_min)
    log_max = np.log(price_max)
    levels = np.linspace(log_min, log_max, n_zones + 1)
    return np.exp(levels)


def select_top_n(activity, n):
    """Seleciona top N de forma determinística (igual Pine)."""
    selected = []
    used = set()

    for _ in range(n):
        max_val = -np.inf
        max_idx = -1
        for i, val in enumerate(activity):
            if i in used:
                continue
            if val > max_val:
                max_val = val
                max_idx = i
        selected.append(max_idx)
        used.add(max_idx)

    return sorted(selected)


def select_bottom_n(activity, n):
    """Seleciona bottom N de forma determinística (igual Pine)."""
    selected = []
    used = set()

    for _ in range(n):
        min_val = np.inf
        min_idx = -1
        for i, val in enumerate(activity):
            if i in used:
                continue
            if val < min_val:
                min_val = val
                min_idx = i
        selected.append(min_idx)
        used.add(min_idx)

    return sorted(selected)

# ============================================================
# Estratégia principal (Python = Pine)
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
        # Gerenciamento de posição
        # ====================================================
        if in_long:
            if low[i] <= stop_price or high[i] >= target_price:
                exits_long[i] = True
                in_long = False

        if in_short:
            if high[i] >= stop_price or low[i] <= target_price:
                exits_short[i] = True
                in_short = False

        if in_long or in_short:
            continue

        # ====================================================
        # Janela reativa
        # ====================================================
        start = i - lookback + 1
        end = i + 1

        w_open  = open_[start:end]
        w_close = close[start:end]
        w_low   = low[start:end]
        w_high  = high[start:end]

        if percentage_since_last_extreme(w_close) < min_percent_from_extreme:
            continue

        price_min = float(w_low.min())
        price_max = float(w_high.max())

        limits = compute_log_zones(price_min, price_max, TOTAL_ZONES)

        activity_up = np.zeros(TOTAL_ZONES, dtype=float)
        activity_down = np.zeros(TOTAL_ZONES, dtype=float)

        # ====================================================
        # CÁLCULO DE ATIVIDADE — 100% IGUAL AO PINE
        #
        # amp = ((inter_high - inter_low) / body_low) * 100
        # ====================================================
        for j in range(len(w_close)):
            o = float(w_open[j])
            c = float(w_close[j])

            if c == o:
                continue

            if c > o:  # candle de alta
                body_low = o
                body_high = c
                target_array = activity_up
            else:      # candle de baixa
                body_low = c
                body_high = o
                target_array = activity_down

            if body_low <= 0:
                continue  # proteção (equivalente implícito do Pine)

            for z in range(TOTAL_ZONES):
                lim_inf = limits[z]
                lim_sup = limits[z + 1]

                inter_low = max(body_low, lim_inf)
                inter_high = min(body_high, lim_sup)

                if inter_high > inter_low:
                    amp = (inter_high - inter_low) / body_low * 100.0
                    target_array[z] += amp

        activity_total = activity_up + activity_down

        # ====================================================
        # Seleção Pine-like das zonas
        # ====================================================
        top_zones = select_top_n(activity_total, TOP_ACTIVE)

        if TOP_ACTIVE != 3 or not zones_in_sequence(top_zones):
            continue

        central_zone = sorted(top_zones)[1]
        bottom_zones = select_bottom_n(activity_total, BOTTOM_ACTIVE)

        # ====================================================
        # LONG
        # ====================================================
        if central_zone + TARGET_LONG_OFFSET < TOTAL_ZONES:
            level = limits[central_zone + 1]
            crossed_up = close[i - 1] <= level and close[i] > level

            if crossed_up:
                entry_price = level
                stop_price = (limits[central_zone] + level) / 2
                target_price = limits[central_zone + TARGET_LONG_OFFSET]

                if max_loss_percent:
                    loss = (entry_price - stop_price) / entry_price * 100.0
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
                    loss = (stop_price - entry_price) / entry_price * 100.0
                    if loss > max_loss_percent:
                        continue

                entries_short[i] = True
                in_short = True
                continue

    # ====================================================
    # Conflitos
    # ====================================================
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

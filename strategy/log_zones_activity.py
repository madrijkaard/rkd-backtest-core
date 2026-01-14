import numpy as np


# ============================================================
# Helpers
# ============================================================

def zones_in_sequence(zones):
    """
    Verifica se as zonas estão em sequência contínua
    """
    zones = sorted(zones)
    return zones[1] == zones[0] + 1 and zones[2] == zones[1] + 1


def percentage_since_last_extreme(window):
    """
    Calcula o percentual de candles desde o último extremo (máximo ou mínimo)
    """
    high_idx = np.argmax(window)
    low_idx = np.argmin(window)
    last_extreme_idx = max(high_idx, low_idx)
    dist = len(window) - last_extreme_idx - 1
    return (dist / len(window)) * 100


def compute_log_zones(price_min, price_max, n_zones=8):
    """
    Calcula os níveis logarítmicos de preço para n_zones
    """
    log_min = np.log(price_min)
    log_max = np.log(price_max)
    levels = np.linspace(log_min, log_max, n_zones + 1)
    return np.exp(levels)


# ============================================================
# Estratégia principal (compatível com Pine Script)
# ============================================================

def log_zones_activity_strategy(close, open_, lookback=200):
    """
    Retorna sinais de Long e Short baseados em zonas logarítmicas.
    """
    entries_long = np.zeros(len(close), dtype=bool)
    entries_short = np.zeros(len(close), dtype=bool)

    for i in range(lookback, len(close)):
        window_close = close[i - lookback:i]
        window_open = open_[i - lookback:i]

        price_min = window_close.min()
        price_max = window_close.max()

        # Filtro: acumulação mínima de candles desde último extremo
        if percentage_since_last_extreme(window_close) < 40:
            continue

        limits = compute_log_zones(price_min, price_max)
        activity = np.zeros(8)

        # Cálculo de atividade por zona (considerando corpo do candle)
        for j in range(i - lookback, i):
            body_low = min(open_[j], close[j])
            body_high = max(open_[j], close[j])
            for z in range(8):
                zone_low = limits[z]
                zone_high = limits[z + 1]
                overlap_low = max(body_low, zone_low)
                overlap_high = min(body_high, zone_high)
                if overlap_high > overlap_low:
                    activity[z] += (overlap_high - overlap_low) / body_low

        # Identifica zonas mais ativas e menos ativas
        sorted_zones = np.argsort(activity)
        top3 = sorted_zones[-3:]
        bottom2 = sorted_zones[:2]

        # Checa se as top3 zonas estão em sequência
        if not zones_in_sequence(top3):
            continue

        central_zone = sorted(top3)[1]  # Zona central entre as top3
        price_prev = close[i - 1]
        price_now = close[i]

        central_low = limits[central_zone]
        central_high = limits[central_zone + 1]

        # ====================================================
        # 🟢 LONG
        # ====================================================
        crossed_up = price_prev <= central_high and price_now > central_high
        if crossed_up:
            zone_above = central_zone + 1
            zone_above_above = central_zone + 2

            # Bloqueia Long se a zona acima da central está entre as menos ativas
            block_long = (
                zone_above in top3 and
                zone_above_above <= 7 and
                zone_above_above in bottom2
            )

            if not block_long:
                entries_long[i] = True

        # ====================================================
        # 🔴 SHORT
        # ====================================================
        crossed_down = price_prev >= central_low and price_now < central_low
        if crossed_down:
            zone_below = central_zone - 1
            zone_below_below = central_zone - 2

            # Bloqueia Short se a zona abaixo da central está entre as menos ativas
            block_short = (
                zone_below in top3 and
                zone_below_below >= 0 and
                zone_below_below in bottom2
            )

            if not block_short:
                entries_short[i] = True

    return entries_long, entries_short


# ============================================================
# Wrapper esperado pelo executor.py
# ============================================================

def backtest_strategy(data, lookback=200):
    """
    Interface padrão esperada pelo executor.py
    """
    close = data["close"].values
    open_ = data["open"].values
    return log_zones_activity_strategy(close=close, open_=open_, lookback=lookback)

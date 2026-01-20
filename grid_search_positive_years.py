# grid_search_positive_years.py

import pandas as pd
import itertools
from tqdm import tqdm
import vectorbt as vbt
import yaml
import os

from exchange import get_exchange
from strategy.log_zones_activity import backtest_strategy

# ============================================================
# LOAD CONFIG
# ============================================================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

SYMBOLS = config["symbols"]
TIMEFRAMES = config["timeframes"]
LOOKBACK = config["strategy"]["lookback_candles"]
INITIAL_BALANCE = config["execution"].get("initial_balance", 10000)
date_cfg = config["date_range"]
START_YEAR = date_cfg["start_year"]
END_YEAR = date_cfg["end_year"]

# ============================================================
# GRID SEARCH PARAMETERS
# ============================================================
MAX_LOSS_VALUES = [1.5]  # percent
MIN_PERCENT_EXTREME_VALUES = [40.0, 45.0, 50.0, 55.0, 60.0]  # percent

# ============================================================
# EXCHANGE
# ============================================================
exchange = get_exchange()

# ============================================================
# Helpers
# ============================================================

def fetch_ohlcv_year(symbol: str, timeframe: str, year: int) -> pd.DataFrame:
    """Carrega OHLCV do símbolo diretamente no timeframe desejado e filtra pelo ano."""
    start_date = pd.Timestamp(year=year, month=1, day=1)
    end_date = pd.Timestamp(year=year, month=12, day=31, hour=23, minute=59)

    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    ohlcv = []

    with tqdm(desc=f"Downloading {symbol} {timeframe} {year}", unit="batch") as pbar:
        while since < end_ts:
            batch = exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                since=since,
                limit=1000
            )
            if not batch:
                break
            ohlcv.extend(batch)
            since = batch[-1][0] + 1
            pbar.update(1)

    if not ohlcv:
        return pd.DataFrame()

    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df.index = df.index.tz_convert(None)

    # Filtra apenas o ano
    df = df.loc[(df.index.year >= year) & (df.index.year <= year)]
    return df

def build_month_ranges(year):
    """Retorna lista de tuplas (início do mês, fim do mês) para o ano."""
    ranges = []
    for month in range(1, 13):
        start = pd.Timestamp(year, month, 1)
        end = start + pd.offsets.MonthEnd(1)
        ranges.append((start, end))
    return ranges

# ============================================================
# MAIN GRID SEARCH
# ============================================================

def run():
    positive_combinations = []

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            for max_loss, min_extreme in itertools.product(MAX_LOSS_VALUES, MIN_PERCENT_EXTREME_VALUES):
                print(f"\n🔹 Running backtest for {symbol} | TF={timeframe} | MaxLoss={max_loss}% | MinExtreme={min_extreme}%")

                all_years_positive = True

                for year in range(START_YEAR, END_YEAR + 1):
                    df_full = fetch_ohlcv_year(symbol, timeframe, year)
                    if df_full.empty or len(df_full) < LOOKBACK + 20:
                        print(f"⚠️ Insufficient data for {symbol} {year} {timeframe}, skipping.")
                        all_years_positive = False
                        continue

                    month_ranges = build_month_ranges(year)
                    annual_return = 0.0
                    all_months_positive = True

                    for month_start, month_end in month_ranges:
                        df_month = df_full.loc[month_start:month_end]
                        if len(df_month) < LOOKBACK + 10:
                            all_months_positive = False
                            continue

                        # Executa a estratégia com os parâmetros da grid
                        entries_l, exits_l, entries_s, exits_s = backtest_strategy(
                            df_month,
                            lookback=LOOKBACK,
                            max_loss_percent=max_loss,
                            min_percent_from_extreme=min_extreme  # ✅ agora dinâmico
                        )

                        portfolio = vbt.Portfolio.from_signals(
                            close=df_month["close"],
                            entries=entries_l,
                            exits=exits_l,
                            short_entries=entries_s,
                            short_exits=exits_s,
                            init_cash=INITIAL_BALANCE,
                            freq=timeframe
                        )

                        # Retorno anual aproximado acumulado
                        annual_return += portfolio.total_return() * 100
                        if portfolio.total_return() <= 0:
                            all_months_positive = False

                    print(
                        f"▶ Processed | Symbol={symbol} | Year={year} | TF={timeframe} "
                        f"| MaxLoss={max_loss}% | MinExtreme={min_extreme}% | AnnualReturn={annual_return:.2f}%"
                        + (" ✅ ALL MONTHS POSITIVE" if all_months_positive else "")
                    )

                    if not all_months_positive:
                        all_years_positive = False

                if all_years_positive:
                    positive_combinations.append({
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "max_loss_percent": max_loss,
                        "min_percent_from_extreme": min_extreme
                    })

    # ============================================================
    # RELATÓRIO FINAL
    # ============================================================
    print("\n\n✅ Combinations with all years positive (2020-2025):")
    for combo in positive_combinations:
        print(
            f"Symbol={combo['symbol']} | TF={combo['timeframe']} "
            f"| MaxLoss={combo['max_loss_percent']}% | MinExtreme={combo['min_percent_from_extreme']}%"
        )

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run()

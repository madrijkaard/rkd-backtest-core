# strategy/accumulation_zone/scanning.py

import os
import sys
import pandas as pd
import itertools
from tqdm import tqdm
import vectorbt as vbt
import yaml

# ============================================================
# Ajuste de import para exchange.py (dois níveis acima)
# ============================================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from exchange import get_exchange
from accumulation_zone import backtest_strategy

# ============================================================
# LOAD GLOBAL CONFIG
# ============================================================
BASE_DIR = os.path.dirname(__file__)

GLOBAL_CONFIG_PATH = os.path.join(BASE_DIR, "../../config.yaml")
with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
    global_config = yaml.safe_load(f)

SYMBOLS = global_config["symbols"]
TIMEFRAMES = global_config["timeframes"]
INITIAL_BALANCE = global_config["execution"].get("initial_balance", 1000.0)

date_cfg = global_config["date_range"]
START_YEAR = date_cfg["start_year"]
END_YEAR = date_cfg["end_year"]

# ============================================================
# LOAD STRATEGY CONFIG
# ============================================================
STRATEGY_CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
with open(STRATEGY_CONFIG_PATH, "r", encoding="utf-8") as f:
    strategy_config = yaml.safe_load(f)

strategy_params = strategy_config["strategy"]
LOOKBACK = strategy_params.get("lookback_candles", 200)

# ============================================================
# GRID SEARCH PARAMETERS
# ============================================================
MAX_LOSS_VALUES = [1.5]
MIN_PERCENT_EXTREME_VALUES = [55.0]

# ============================================================
# EXCHANGE
# ============================================================
exchange = get_exchange()

# ============================================================
# Helpers
# ============================================================

def fetch_ohlcv_year(symbol: str, timeframe: str, year: int) -> pd.DataFrame:
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

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df.index = df.index.tz_convert(None)

    return df.loc[df.index.year == year]


def build_month_ranges(year: int):
    ranges = []
    for month in range(1, 13):
        start = pd.Timestamp(year, month, 1)
        end = start + pd.offsets.MonthEnd(1)
        ranges.append((start, end))
    return ranges

# ============================================================
# MAIN
# ============================================================

def run():
    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            for max_loss, min_extreme in itertools.product(
                MAX_LOSS_VALUES,
                MIN_PERCENT_EXTREME_VALUES
            ):
                print(
                    f"\n🔹 START | {symbol} | TF={timeframe} "
                    f"| MaxLoss={max_loss}% | MinExtreme={min_extreme}%"
                )

                capital = INITIAL_BALANCE
                initial_global_capital = INITIAL_BALANCE
                survived = True

                for year in range(START_YEAR, END_YEAR + 1):
                    df_year = fetch_ohlcv_year(symbol, timeframe, year)

                    if df_year.empty or len(df_year) < LOOKBACK + 20:
                        print(f"⚠️ Insufficient data for {symbol} {year}")
                        survived = False
                        break

                    capital_start_year = capital

                    for month_start, month_end in build_month_ranges(year):
                        df_month = df_year.loc[month_start:month_end]

                        if len(df_month) < LOOKBACK + 10:
                            continue

                        entries_l, exits_l, entries_s, exits_s = backtest_strategy(
                            df_month,
                            lookback=LOOKBACK,
                            max_loss_percent=max_loss,
                            min_percent_from_extreme=min_extreme
                        )

                        portfolio = vbt.Portfolio.from_signals(
                            close=df_month["close"],
                            entries=entries_l,
                            exits=exits_l,
                            short_entries=entries_s,
                            short_exits=exits_s,
                            init_cash=capital,
                            size=1.0,   # 100% do capital
                            freq=timeframe
                        )

                        monthly_return = portfolio.total_return()
                        capital *= (1 + monthly_return)

                        if capital <= 0:
                            survived = False
                            break

                    annual_return = (capital / capital_start_year) - 1
                    total_return = (capital / initial_global_capital) - 1

                    print(
                        f"▶ {year} | "
                        f"FinalBalance={capital:.2f} | "
                        f"AnnualReturn={annual_return * 100:.2f}% | "
                        f"TotalReturn={total_return * 100:.2f}%"
                    )

                    if not survived:
                        break

                if survived:
                    print(
                        f"✅ SURVIVED | {symbol} | TF={timeframe} "
                        f"| MaxLoss={max_loss}% | MinExtreme={min_extreme}% "
                        f"| FinalCapital={capital:.2f}"
                    )
                else:
                    print(
                        f"❌ BROKE | {symbol} | TF={timeframe} "
                        f"| MaxLoss={max_loss}% | MinExtreme={min_extreme}%"
                    )

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run()

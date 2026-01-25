# strategy/accumulation_zone/scanning.py

import os
import sys
import pandas as pd
import itertools
from tqdm import tqdm
import vectorbt as vbt
import yaml

# ============================================================
# Ajuste de import para exchange.py (raiz do projeto)
# ============================================================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(PROJECT_ROOT)

from exchange import get_exchange
from accumulation_zone import backtest_strategy

# ============================================================
# LOAD GLOBAL CONFIG
# ============================================================
BASE_DIR = os.path.dirname(__file__)

GLOBAL_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")
with open(GLOBAL_CONFIG_PATH, "r", encoding="utf-8") as f:
    global_config = yaml.safe_load(f)

SYMBOLS = global_config["symbols"]
TIMEFRAMES = global_config["timeframes"]
INITIAL_BALANCE = global_config["execution"].get("initial_balance", 1000.0)

date_cfg = global_config["date_range"]
START_YEAR = date_cfg["start_year"]
END_YEAR = date_cfg["end_year"]

# 👉 OUTPUT SEMPRE NA RAIZ DO PROJETO
OUTPUT_FOLDER = os.path.join(PROJECT_ROOT, global_config["output"]["folder"])
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

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
MAX_LOSS_VALUES = [2.5]
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
    return [
        (
            pd.Timestamp(year, month, 1),
            pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(1)
        )
        for month in range(1, 13)
    ]

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
                    f"| MaxLoss={max_loss}% | MinExtreme={min_extreme}% \n"
                )

                capital = INITIAL_BALANCE
                rows = []
                broke_early = False

                for year in range(START_YEAR, END_YEAR + 1):
                    df_year = fetch_ohlcv_year(symbol, timeframe, year)

                    if df_year.empty or len(df_year) < LOOKBACK + 20:
                        print(f"⚠️ Insufficient data for {symbol} {year}")
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
                            size=1.0,
                            freq=timeframe
                        )

                        capital *= (1 + portfolio.total_return())

                        if capital <= 0:
                            print(f"💥 BROKE DURING {year}")
                            capital = 0.0
                            broke_early = True
                            break

                    annual_return = (
                        (capital / capital_start_year) - 1
                        if capital_start_year > 0 else -1
                    )
                    total_return = (capital / INITIAL_BALANCE) - 1

                    print(
                        f"▶ {year} | FinalBalance={capital:.2f} | "
                        f"AnnualReturn={annual_return * 100:.2f}% | "
                        f"TotalReturn={total_return * 100:.2f}%"
                    )

                    rows.append({
                        "Pair": symbol,
                        "TF": timeframe,
                        "MaxLoss": f"{max_loss}%",
                        "MinExtreme": f"{min_extreme}%",
                        "Year": year,
                        "FinalBalance": round(capital, 2),
                        "AnnualReturn": round(annual_return * 100, 2),
                        "TotalReturn": round(total_return * 100, 2),
                        "FinalCapital": None,
                        "Status": None
                    })

                    if broke_early:
                        break

                status = "SURVIVED" if capital >= INITIAL_BALANCE else "BROKE"
                rows[-1]["FinalCapital"] = round(capital, 2)
                rows[-1]["Status"] = status

                df_out = pd.DataFrame(rows)

                filename = (
                    f"{symbol.replace('/', '')}_"
                    f"{timeframe}_"
                    f"maxloss_{max_loss}_"
                    f"minext_{min_extreme}.xlsx"
                )

                full_path = os.path.join(OUTPUT_FOLDER, filename)

                with pd.ExcelWriter(
                    full_path,
                    engine="openpyxl",
                    mode="w"
                ) as writer:
                    df_out.to_excel(
                        writer,
                        index=False,
                        sheet_name="results"
                    )

                print(f"\n📊 File generated: {full_path}\n")

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run()

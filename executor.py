# executor.py

import os
import yaml
import shutil
import pandas as pd
import vectorbt as vbt
from tqdm import tqdm

from datetime import datetime, timezone, date
from dateutil.relativedelta import relativedelta

from exchange import get_exchange
from strategy.accumulation_zone.log_zones_activity import (
    log_zones_activity_strategy
)

# =========================================================
# LOAD GLOBAL CONFIG
# =========================================================

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

SYMBOLS = config["symbols"]
TIMEFRAMES = config["timeframes"]
INITIAL_BALANCE = config["execution"].get("initial_balance", 1000.0)

date_cfg = config["date_range"]
OUTPUT_FOLDER = config["output"]["folder"]

# =========================================================
# LOAD STRATEGY CONFIG (EXPLICIT PARAMETERS)
# =========================================================

STRATEGY_CONFIG_PATH = os.path.join(
    BASE_DIR,
    "strategy",
    "accumulation_zone",
    "config.yaml"
)

with open(STRATEGY_CONFIG_PATH, "r", encoding="utf-8") as f:
    strategy_cfg = yaml.safe_load(f)["strategy"]

MAX_LOSS_PERCENT = strategy_cfg.get("max_loss_percent", None)
MIN_PERCENT_FROM_EXTREME = strategy_cfg["activity"]["min_percent_from_extreme"]

# =========================================================
# EXCHANGE
# =========================================================

exchange = get_exchange()

# =========================================================
# HELPERS
# =========================================================

def timeframe_to_label(tf: str) -> str:
    if tf.endswith("m"):
        return tf.replace("m", "min")
    return tf


def build_output_filename(symbol: str) -> str:
    symbol_clean = symbol.replace("/", "")
    return (
        f"{symbol_clean}_"
        f"{date_cfg['start_month']}_{date_cfg['start_year']}_"
        f"{date_cfg['end_month']}_{date_cfg['end_year']}.xlsx"
    )


def generate_month_ranges(start_year, start_month, end_year, end_month):
    ranges = []
    current = date(start_year, start_month, 1)
    end = date(end_year, end_month, 1)

    while current <= end:
        month_start = pd.Timestamp(current)
        month_end = month_start + pd.offsets.MonthEnd(1)
        ranges.append((month_start, month_end))
        current += relativedelta(months=1)

    return ranges

# =========================================================
# CLEAN OUTPUT FOLDER
# =========================================================

def clean_output_folder(path: str):
    if path in ("", ".", "/", ".."):
        raise ValueError(f"Unsafe OUTPUT_FOLDER path: '{path}'")

    if os.path.exists(path):
        for name in os.listdir(path):
            file_path = os.path.join(path, name)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"⚠️ Failed to delete {file_path}: {e}")
    else:
        os.makedirs(path, exist_ok=True)

# =========================================================
# FETCH OHLCV (TZ-NAIVE)
# =========================================================

def fetch_ohlcv(symbol: str, timeframe: str) -> pd.DataFrame:
    start_date = datetime(
        date_cfg["start_year"],
        date_cfg["start_month"],
        1,
        tzinfo=timezone.utc
    )
    end_date = datetime(
        date_cfg["end_year"],
        date_cfg["end_month"],
        28,
        tzinfo=timezone.utc
    )

    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    ohlcv = []

    with tqdm(
        desc=f"Downloading candlesticks {symbol} {timeframe}",
        unit="batch"
    ) as pbar:
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

    return df

# =========================================================
# RUN BACKTEST (MONTHLY)
# =========================================================

def run():
    print(f"\n🧹 Cleaning output folder: {OUTPUT_FOLDER}")
    clean_output_folder(OUTPUT_FOLDER)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    for symbol in SYMBOLS:
        print(f"\n⚙️ Running backtest for {symbol}")

        output_file = os.path.join(
            OUTPUT_FOLDER,
            build_output_filename(symbol)
        )

        if os.path.exists(output_file):
            os.remove(output_file)

        for timeframe in TIMEFRAMES:
            print(f"\n⏱ Timeframe: {timeframe}")

            all_monthly_stats = []

            # =============================
            # FETCH OHLCV
            # =============================
            df_full = fetch_ohlcv(symbol, timeframe)

            if df_full.empty:
                print(" ❌ No data, skipping timeframe.")
                continue

            month_ranges = generate_month_ranges(
                date_cfg["start_year"],
                date_cfg["start_month"],
                date_cfg["end_year"],
                date_cfg["end_month"]
            )

            # =============================
            # MONTHLY LOOP
            # =============================
            for month_start, month_end in tqdm(
                month_ranges,
                desc="Running backtest",
                unit="month"
            ):
                df_month = df_full.loc[month_start:month_end]

                if df_month.empty:
                    continue

                # =============================
                # STRATEGY (PARAMS EXPLICIT)
                # =============================
                entries_l, exits_l, entries_s, exits_s = (
                    log_zones_activity_strategy(
                        close=df_month["close"].values,
                        open_=df_month["open"].values,
                        max_loss_percent=MAX_LOSS_PERCENT,
                        min_percent_from_extreme=MIN_PERCENT_FROM_EXTREME
                    )
                )

                # =============================
                # PORTFOLIO
                # =============================
                portfolio = vbt.Portfolio.from_signals(
                    close=df_month["close"],
                    entries=entries_l,
                    exits=exits_l,
                    short_entries=entries_s,
                    short_exits=exits_s,
                    init_cash=INITIAL_BALANCE,
                    freq=timeframe
                )

                stats = portfolio.stats()
                stats["symbol"] = symbol
                stats["timeframe"] = timeframe
                stats["month"] = month_start.month
                stats["year"] = month_start.year

                all_monthly_stats.append(stats)

            # =============================
            # EXPORT
            # =============================
            if all_monthly_stats:
                stats_df = pd.DataFrame(all_monthly_stats)

                with pd.ExcelWriter(
                    output_file,
                    engine="openpyxl",
                    mode="a" if os.path.exists(output_file) else "w"
                ) as writer:
                    stats_df.to_excel(
                        writer,
                        index=False,
                        sheet_name=timeframe
                    )

                print(f"\n📁 Stats for {timeframe} saved to: {output_file}")

# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print("\n❌ Error during execution:")
        print(e)
        input("\nPress ENTER to exit...")

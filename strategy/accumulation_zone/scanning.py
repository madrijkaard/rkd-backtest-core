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
START_MONTH = date_cfg["start_month"]
END_YEAR = date_cfg["end_year"]
END_MONTH = date_cfg["end_month"]

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

# ----------------------------
# RISK MANAGEMENT
# ----------------------------

risk_cfg = strategy_params.get("risk_management", {})

RISK_ENABLED = risk_cfg.get("enabled", False)
MAX_MONTHLY_DRAWDOWN = risk_cfg.get("max_monthly_drawdown", -3.0)
MAX_RECOVERY_TRADES = risk_cfg.get("max_recovery_trades", 2)

# ----------------------------
# LEVERAGE CONFIG
# ----------------------------

leverage_cfg = strategy_params.get("leverage", {})

LEVERAGE_ENABLED = leverage_cfg.get("enabled", False)
LEVERAGE_VALUE = float(leverage_cfg.get("value", 1.0))

# ============================================================
# GRID SEARCH PARAMETERS
# ============================================================

MAX_LOSS_VALUES = [2.5]
MIN_PERCENT_EXTREME_VALUES = [60.0]

# ============================================================
# EXCHANGE
# ============================================================

exchange = get_exchange()

# ============================================================
# HELPERS
# ============================================================

def fetch_ohlcv_year(symbol: str, timeframe: str, year: int) -> pd.DataFrame:
    start_date = pd.Timestamp(year=year, month=1, day=1)
    end_date = pd.Timestamp(year=year, month=12, day=31, hour=23, minute=59)

    since = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    ohlcv = []

    with tqdm(
        desc=f"Downloading {symbol} {timeframe} {year}",
        unit="batch",
        leave=False
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
# RISK MANAGEMENT (MONTHLY)
# ============================================================

def apply_monthly_risk_management(trades: pd.DataFrame) -> float:
    """
    Retorna o retorno percentual FINAL do mês (ex: 0.012 = +1.2%)
    aplicando regras de gestão de risco por trade.
    """
    cumulative = 0.0
    trades_taken = 0
    recovery_trades = 0

    for _, trade in trades.iterrows():
        trade_return = (trade["pnl"] / trade["entry_price"]) * 100

        # Aplica alavancagem por trade
        if LEVERAGE_ENABLED:
            trade_return *= LEVERAGE_VALUE

        trades_taken += 1
        cumulative += trade_return

        # 🟢 Primeiro trade positivo → encerra mês
        if trades_taken == 1 and trade_return > 0:
            break

        # 🔴 Primeiro trade negativo → entra em recuperação
        if trades_taken == 1 and trade_return < 0:
            continue

        # 🚀 Recuperou
        if cumulative > 0:
            break

        # 💥 Estourou drawdown mensal
        if cumulative <= MAX_MONTHLY_DRAWDOWN:
            break

        recovery_trades += 1
        if recovery_trades >= MAX_RECOVERY_TRADES:
            break

    return cumulative / 100.0


def get_month_return(portfolio, trades) -> float:
    if trades is None or trades.empty:
        return 0.0

    if RISK_ENABLED:
        return apply_monthly_risk_management(trades)

    base_return = portfolio.total_return()

    if LEVERAGE_ENABLED:
        base_return *= LEVERAGE_VALUE

    return base_return


# ============================================================
# MAIN
# ============================================================

def run():
    risk_tag = "riskON" if RISK_ENABLED else "riskOFF"
    lev_tag = f"{LEVERAGE_VALUE}x" if LEVERAGE_ENABLED else "1x"

    for symbol in SYMBOLS:
        for timeframe in TIMEFRAMES:
            for max_loss, min_extreme in itertools.product(
                MAX_LOSS_VALUES,
                MIN_PERCENT_EXTREME_VALUES
            ):
                print(
                    f"\n🔹 START | {symbol} | TF={timeframe} "
                    f"| MaxLoss={max_loss}% | MinExtreme={min_extreme}% "
                    f"| {risk_tag} | Lev={lev_tag}\n"
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

                        trades = portfolio.trades.records
                        month_return = get_month_return(portfolio, trades)

                        # 🚨 Limite de liquidação
                        month_return = max(month_return, -1.0)

                        capital *= (1 + month_return)

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
                        "Risk": risk_tag,
                        "Leverage": lev_tag,
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

                symbol_clean = symbol.replace("/", "")
                filename = (
                    f"{symbol_clean}_"
                    f"{START_MONTH}_{START_YEAR}_"
                    f"{END_MONTH}_{END_YEAR}_"
                    f"{risk_tag}_{lev_tag}_scanning.xlsx"
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

                print(f"\n📊 Scanning generated: {full_path}\n")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    run()

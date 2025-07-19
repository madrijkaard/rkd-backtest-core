import os
import glob
import ccxt
import datetime
import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from tqdm import tqdm

from resources import TIMEFRAMES, START_YEAR, END_YEAR, LOOKBACK, CRYPTOS, OUTPUT_FOLDER
from strategies.strategy_max_min import estrategia_max_min

# Mapeia timeframes para frequências compatíveis com Pandas
TIMEFRAME_TO_FREQ = {
    '15m': '15T',
    '30m': '30T',
    '1h': '1H',
    '4h': '4H',
    '1d': '1D'
}

def executar_backtest(binance, symbol, timeframe_str, start_date, estrategia_func, lookback: int, limit=1000):
    since = int(start_date.timestamp() * 1000)
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe_str, since=since, limit=limit)
    except Exception as e:
        print(f"Erro em {symbol} {timeframe_str} {start_date.date()}: {e}")
        return None

    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    close = df['close']

    if len(close) < lookback:
        return None

    freq = TIMEFRAME_TO_FREQ.get(timeframe_str, None)
    pf = estrategia_func(close, lookback, freq=freq)
    stats = pf.stats()
    stats["Data"] = start_date.strftime("%Y-%m-%d")
    return stats

def executar_para_todos():
    # Garante que a pasta existe
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Limpa todos os arquivos existentes na pasta backtest/
    for f in glob.glob(os.path.join(OUTPUT_FOLDER, "*")):
        os.remove(f)
    print(f"🧹 Pasta '{OUTPUT_FOLDER}' limpa com sucesso.")

    binance = ccxt.binance()
    datas = [datetime.datetime(year, month, 1)
             for year in range(START_YEAR, END_YEAR + 1)
             for month in range(1, 13)]

    for symbol in CRYPTOS:
        print(f"\n🔍 Processando {symbol}...")
        wb = Workbook()
        wb.remove(wb.active)

        for tf in TIMEFRAMES:
            resultados = []
            for start_date in tqdm(datas, desc=f"{symbol} {tf}", unit="mês"):
                stats = executar_backtest(
                    binance,
                    symbol.replace("USDT", "/USDT"),
                    tf,
                    start_date,
                    estrategia_func=estrategia_max_min,
                    lookback=LOOKBACK
                )
                if stats is not None:
                    resultados.append(stats)

            if not resultados:
                print(f"⚠ Sem dados suficientes para {symbol} {tf}")
                continue

            df = pd.DataFrame(resultados)
            df.reset_index(inplace=True)
            ws = wb.create_sheet(title=tf)
            for row in dataframe_to_rows(df, index=False, header=True):
                ws.append(row)

        file_path = os.path.join(OUTPUT_FOLDER, f"{symbol}.xlsx")
        wb.save(file_path)
        print(f"✅ Arquivo salvo: {file_path}")

if __name__ == "__main__":
    executar_para_todos()

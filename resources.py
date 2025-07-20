# Períodos gráficos utilizados no backtest
TIMEFRAMES = ['15m', '30m', '1h', '4h']

# Intervalo de anos para o backtest
START_YEAR = 2020
END_YEAR = 2024

# Valor de lookback para cálculo de mínimas/máximas
LOOKBACK = 200

# Quantidade de candles por backtest
CANDLE_LIMIT = 1000

# Lista de criptomoedas a testar
CRYPTOS = [
    "INJUSDT", "NEARUSDT", "SUIUSDT", "UNIUSDT"
]

# Nome da exchange a ser utilizada
EXCHANGE_NAME = "binance"

# Pasta onde estão os arquivos XLSX de resultados gerados pelo core
OUTPUT_FOLDER = "backtest"
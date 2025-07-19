# Período gráfico utilizado no backtest (ex: '15m', '1h', '4h', etc.)
TIMEFRAMES = ['15m', '30m', '1h', '4h']

# Intervalo de anos para o backtest
START_YEAR = 2020
END_YEAR = 2024  # inclusivo

# Valor de lookback para cálculo de mínimas/máximas
LOOKBACK = 200

# Lista de criptomoedas
CRYPTOS = [
    "ETHUSDT",
    "AVAXUSDT",
    "ADAUSDT"
]

# Caminho da pasta onde os arquivos serão salvos
OUTPUT_FOLDER = "backtest"

# Exchange ativa (apenas uma deve estar ativa por vez)
EXCHANGE_NAME = "binance"  # opções: binance, coinbasepro, bybit, huobi

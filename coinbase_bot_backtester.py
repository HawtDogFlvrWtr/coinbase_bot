import argparse
import configparser
import datetime
import sys
import ccxt
import pandas as pd
import pandas_ta as ta
import time
from stockstats import StockDataFrame as Sdf



parser = argparse.ArgumentParser()
parser.add_argument('-t', '--timeframe', help="The timeframe you want to determine macd and rsi from. Default: 1h", choices=['1m', '1h', '1d', '1M', '1y'], default='1h')
parser.add_argument('-o', '--orders_file', help="The json filename for the orders file", default='orders_bt.json')
parser.add_argument('-c', '--config_file', help="The json filename for the orders file", default='config.cfg')
parser.add_argument('-s', '--start', help='The beginning time to backtest in epoch', type=int, default=1514782800)
parser.add_argument('-sa', '--safe', help='Set the backtester to safe', action='store_true')
parser.add_argument('-e', '--end', help='The last date you want to backtest in epoch', type=int, default=time.time())

args = parser.parse_args()
timeframe = args.timeframe
orders_json_filename = args.orders_file
config_file = args.config_file
since_start = args.start
since_end = args.end
safe = args.safe

config = configparser.ConfigParser()
config.read(config_file)
api_key = config.get('api-config', 'api_key')
secret = config.get('api-config', 'secret')

if safe:
    print("Running the bot in less risk mode")
else:
    print("Running the bot in good risk mode")

# Initialize the exchange and API keys
exchange = ccxt.coinbase ()
exchange_id = 'coinbase'
exchange_class = getattr(ccxt, exchange_id)
exchange = exchange_class({
    'apiKey': api_key,
    'secret': secret,
    'options':  {
        'fetchTicker': 'fetchTickerV3',
        'fetchTickers': 'fetchTickersV3',
        'fetchMarkets': 'fetchMarketsV3',
        'advanced': True
    },
    'enableRateLimit': True,
})

# Configuration
symbols = ['BTC/USD','ETH/USD','SHIB/USD', 'DOGE/USD', 'SOL/USD', 'LINK/USD', 'AAVE/USD']
fast_sma_period = 10
slow_sma_period = 20

def fetch_ohlcv_data(symbol, start_time):
    since = datetime.datetime.fromtimestamp(start_time).strftime('%Y-%m-%dT%H:%M:%SZ')
    ohlcv_data = exchange.fetch_ohlcv(symbol, timeframe, exchange.parse8601(since))
    df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    return df

def macd_signals(df, symbol):
    fast = 12
    slow = 26
    signal = 9
    macd = df.ta.macd(fast=fast, slow=slow, signal=signal)
    df = pd.concat([df, macd], axis=1)
    df = pd.concat([df, df.ta.rsi()], axis=1)
    return df

def calculate_sma(df, period):
    return df['close'].rolling(window=period).mean()

def main():
    global since_start
    df_store = pd.DataFrame
    last_buy_price = {}
    last_profit = {}
    while True:
        try:
            for symbol in symbols:
                df = fetch_ohlcv_data(symbol, since_start)
                if len(df) < 1:
                    continue # This symbol doesn't exist.
                df = macd_signals(df,symbol)
                df['fast_sma'] = calculate_sma(df, fast_sma_period)
                df['slow_sma'] = calculate_sma(df, slow_sma_period)
                for index, row in df.iterrows():
                    prev_index = index - 1
                    macd = row['MACD_12_26_9']
                    macd_last = df['MACD_12_26_9'].iloc[prev_index]
                    signal = row['MACDs_12_26_9']
                    signal_last = df['MACDs_12_26_9'].iloc[prev_index]
                    close = row['close']
                    rsi = row['RSI_14']
                    fast_sma_current = row['fast_sma']
                    slow_sma_current = row['slow_sma']
                    fast_sma_previous = df['fast_sma'].iloc[prev_index]
                    slow_sma_previous = df['slow_sma'].iloc[prev_index]
                    since_print = datetime.datetime.fromtimestamp(row['timestamp'] / 1000).strftime('%m-%d-%Y %H:%M:%S')
                    # Check for a buy signal
                    if safe:
                        # Buy Low Risk
                        if fast_sma_previous < slow_sma_previous and fast_sma_current > slow_sma_current and macd > signal:
                            last_buy_price[symbol] = close
                            #print("Buying %s for %s" % (symbol, close))
                        # Sell Low Risk
                        elif fast_sma_previous > slow_sma_previous and fast_sma_current < slow_sma_current and macd < signal:
                            if symbol not in last_buy_price:
                                continue
                                #last_buy_price[symbol] = close
                            if symbol not in last_profit:
                                last_profit[symbol] = 0
                            p_l_a = (close - last_buy_price[symbol])
                            p_l_p = 100 * p_l_a / ((close + last_buy_price[symbol]) / 2)
                            last_profit[symbol] = last_profit[symbol] + p_l_p
                            print(since_print, last_profit)
                            #print("Selling %s for %s" % (symbol, close))
                    else:
                        # Buy Good Risk
                        if macd > signal and macd_last < signal_last and rsi < 50:
                            last_buy_price[symbol] = close
                            #print("Buying %s for %s" % (symbol, close))
                        # Sell Good Risk
                        elif macd < signal and macd_last > signal_last and rsi > 50:
                                if symbol not in last_buy_price:
                                    #last_buy_price[symbol] = close
                                    continue
                                if symbol not in last_profit:
                                    last_profit[symbol] = 0
                                p_l_a = (close - last_buy_price[symbol])
                                p_l_p = 100 * p_l_a / ((close + last_buy_price[symbol]) / 2)
                                last_profit[symbol] = last_profit[symbol] + p_l_p
                                print(since_print, last_profit)
                                #print("Selling %s for %s" % (symbol, close))

                    next_start = row['timestamp']
            since_start = next_start / 1000
            if since_start >= time.time():
                print("Backtesting finished")
                sys.exit(0)
            #time.sleep(60 * 60)  # Sleep for an hour
        except ccxt.RequestTimeout as e:
            # recoverable error, do nothing and retry later
            print(type(e).__name__, str(e))
        except ccxt.DDoSProtection as e:
            # recoverable error, you might want to sleep a bit here and retry later
            print(type(e).__name__, str(e))
        except ccxt.ExchangeNotAvailable as e:
            # recoverable error, do nothing and retry later
            print(type(e).__name__, str(e))
        except ccxt.NetworkError as e:
            # do nothing and retry later...
            print(type(e).__name__, str(e))
        except ValueError as ve:
            print("Done Backtesting")
            sys.exit()
        #except Exception as e:
        #    # panic and halt the execution in case of any other error
        #    since_start = next_start / 1000
        #    print(type(e).__name__, str(e))


if __name__ == "__main__":
    main()

import argparse
import configparser
import datetime
import hashlib
import hmac
import json
import os
import sys
import ccxt
import pandas as pd
import pandas_ta as ta
import time
from prettytable import PrettyTable
from tinydb import TinyDB, Query
from threading import Thread
from websocket import create_connection, WebSocketConnectionClosedException # websocket-client


parser = argparse.ArgumentParser()
parser.add_argument('-o', '--orders_file', help="The json filename for the orders file", default='coinbase_bot_bt.json')
parser.add_argument('-c', '--config_file', help="The json filename for the orders file", default='config.cfg')
parser.add_argument('-s', '--start_time', help="The start time for backtesting", type=int, default=1672531200)
parser.add_argument('-rb', '--rsi_buy_lt', help="The start time for backtesting", type=int, default=50)
parser.add_argument('-rs', '--rsi_sell_gt', help="The start time for backtesting", type=int, default=50)
parser.add_argument('-t', '--take_profit', help="The start time for backtesting", type=int, default=5)
parser.add_argument('-sl', '--stoploss_percent', help="The start time for backtesting", type=int, default=10)

args = parser.parse_args()
orders_json_filename = args.orders_file
config_file = args.config_file
since_start = args.start_time
rsi_buy_lt = args.rsi_buy_lt
rsi_sell_gt = args.rsi_sell_gt
take_profit = args.take_profit
stoploss_percent = -abs(args.stoploss_percent)
sleep_lookup = {'1m': 120, '1h': 3660, '1d': 86460} # Added second to give the exchange time to update the candles

config = configparser.ConfigParser()
config.read(config_file)
api_key = config.get('api-config', 'api_key')
secret = config.get('api-config', 'secret')
risk_level = config.get('bot-config', 'risk_level')
timeframe = config.get('bot-config', 'timeframe')
spend_dollars = int(config.get('spend-config', 'spend_dollars'))
buy_percent = int(config.get('spend-config', 'buy_percent'))
symbols = json.loads(config.get('bot-config', 'symbols'))

allow_duplicates = config.get('spend-config', 'allow_duplicates')
current_prices = {}

max_order_amount = buy_percent / 100 * spend_dollars
max_orders = int(spend_dollars / max_order_amount)

if risk_level == 'safe':
    print("Running the bot in SMA signal mode")
else:
    print("Running the bot in MACD/MACs + RSI mode")

db = TinyDB(orders_json_filename)
db.truncate()
Orders = Query()

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
fast_sma_period = 10
slow_sma_period = 20

def insert_order(status, symbol, buy_amount, buy_time, signal_time, buy_price):
    db.insert({'symbol': symbol, 'status': status, 'buy_amount': buy_amount, 'buy_time': buy_time, 'signal_time': signal_time, 'buy_price': buy_price, 'sell_price': "", 'sell_delta': "", 'sell_profit': 0, 'sell_time': ""})

def update_order(timestamp, sell_price, sell_delta, sell_profit, sell_time):
    db.update({'status': 'closed', 'sell_price': sell_price, 'sell_delta': sell_delta, 'sell_profit': sell_profit, 'sell_time': sell_time}, Orders.buy_time == timestamp)

def search_open_order(symbol):
    results = db.search((Orders.symbol == symbol) & (Orders.status == 'open'))
    if len(results) > 0:
        return True
    else:
        return False
    
def last_order_buy_price(symbol):
    od = sorted(db.search((Orders.symbol == symbol) & (Orders.status == 'open')), key=lambda k: k['buy_time'])
    if not od:
        return False
    else:
        return od[-1]['buy_price']
    
def open_order_count(symbol = None):
    if not symbol:
        return db.count((Orders.status == 'open'))
    else:
        return db.count((Orders.symbol == symbol) & (Orders.status == 'open'))
    
def search_open_duplicate_timestamp(symbol, timestamp):
    results = db.search((Orders.symbol == symbol) & (Orders.signal_time == timestamp) & (Orders.status == 'open'))
    if len(results) > 0:
        return True
    else:
        return False
    
def search_order(symbol):
    results = db.search(Orders.symbol == symbol)
    return results

def return_open_orders():
    results = db.search(Orders.status == 'open')
    return results

def return_closed_profit():
    results = db.all()
    profit_list = []
    for res in results:
            profit_list.append(res['sell_profit'])
    return sum(profit_list)

def fetch_ohlcv_data(symbol, start_time):
    file_path = "backtesting_data/%s_%s.json" % (symbol.replace('/', '-'), timeframe)
    # Lets try to load the data from our saves first and fill in the gap if we don't.
    have_saved = False
    if os.path.isfile(file_path):
        open_json = open(file_path)
        ohlcv_data_load = json.load(open_json)
        last_epoch = ohlcv_data_load[-1][0] / 1000
        if last_epoch > start_time:
            have_saved = True
    if have_saved:
        for i in range(len(ohlcv_data_load)):
            if ohlcv_data_load[i][0] / 1000 >= start_time:
                ohlcv_data = ohlcv_data_load[i:]
                break
    else:
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
    # To preload my order
    #insert_order('open', 'SHIB/USD', 77416742.61585483, 1698787595, 0.00000768)
    global since_start
    last_run = None
    notes = []
    profit_list = []
    last_profit = 0
    #if len(notes) > 5: # Only keep 5 messages
    #    notes = notes[-5:]
    last_timestamp = time.time() # In case nothing comes through, we set this to now.
    try:
        last_last_timestamp = 0
        for symbol in symbols:
            df = fetch_ohlcv_data(symbol, since_start)
            if len(df) < 1:
                continue # This symbol doesn't exist on coinbase.
            last_timestamp = df['timestamp'].iloc[-1]
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
                record_timestamp = row['timestamp']
                last_timestamp = record_timestamp
                note_timestamp = datetime.datetime.fromtimestamp(record_timestamp/ 1000).strftime('%m-%d-%Y %H:%M:%S')
                current_price = close
                # Check for a buy signal
                if risk_level == 'safe':
                    # Buy Low Risk
                    if fast_sma_previous < slow_sma_previous and fast_sma_current > slow_sma_current and macd > signal:
                        if allow_duplicates == 'False' and open_order_count(symbol) > 0: # Prevent duplicate coin
                            print('%s - Skipping buy of symbol %s because we already have an open order' % (note_timestamp, symbol))
                            continue
                        if open_order_count() > max_orders: # Already met our max open orders
                            print('%s - Skipping buy of symbol %s because we are at our max orders.' % (note_timestamp, symbol))
                            continue
                        #if last_order_buy_price(symbol) > current_price: # Don't buy if we paid more for the last order
                        #    print('%s - Skipping buy of symbol %s because a previous buy was at a lower price.' % (note_timestamp, symbol))
                        #    continue
                        # Check for an order that fired at on the same epoch and symbol
                        # DO BUY
                        buy_amount = max_order_amount / current_price
                        buy_time = last_timestamp
                        print('%s - Buying %s %s at %s.' % (note_timestamp, buy_amount, symbol, current_price))
                        insert_order('open', symbol, buy_amount, buy_time, last_timestamp, current_price)
                    # Sell Low Risk
                    elif fast_sma_previous > slow_sma_previous and fast_sma_current < slow_sma_current and macd < signal:
                        # DO SELL
                        if not search_open_order(symbol):
                            continue # No open orders for this coin
                        # DO SELL
                        buy_orders = search_order(symbol)
                        for buy_order in buy_orders:
                            if buy_order['status'] == 'closed':
                                continue
                            timestamp = buy_order['buy_time']
                            buy_price = buy_order['buy_price']
                            buy_amount = buy_order['buy_amount']
                            p_l_a = (current_price - buy_price)
                            profit = (buy_amount * current_price) - (buy_price * buy_amount)
                            if profit < 0:
                                continue
                            profit_list.append(profit)
                            print('%s - Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                            update_order(timestamp, current_price, p_l_a, profit, last_timestamp)
                else:
                    # Buy Good Risk
                    if macd > signal and macd_last < signal_last and rsi < rsi_buy_lt:
                        # Prevent duplicate coin
                        if allow_duplicates == 'False' and open_order_count(symbol) > 0: # Prevent duplicate coin
                            print('%s - Skipping buy of symbol %s because we already have an open order' % (note_timestamp, symbol))
                            continue
                        if open_order_count() > max_orders: # Already met our max open orders
                            print('%s - Skipping buy of symbol %s because we are at our max orders.' % (note_timestamp, symbol))
                            continue
                        #if last_order_buy_price(symbol) > current_price: # Don't buy if we paid more for the last order
                        #    print('%s - Skipping buy of symbol %s because a previous buy was at a lower price.' % (note_timestamp, symbol))
                        #    continue
                        # DO BUY
                        buy_amount = max_order_amount / current_price
                        buy_time = last_timestamp
                        print('%s - Buying %s %s at %s.' % (note_timestamp, buy_amount, symbol, current_price))
                        insert_order('open', symbol, buy_amount, buy_time, last_timestamp, current_price)
                    # Sell Good Risk
                    elif macd < signal and macd_last > signal_last and rsi > rsi_sell_gt:
                        # DO SELL
                        if not search_open_order(symbol):
                            continue
                        buy_orders = search_order(symbol)
                        for buy_order in buy_orders:
                            if buy_order['status'] == 'closed':
                                continue
                            timestamp = buy_order['buy_time']
                            buy_price = buy_order['buy_price']
                            buy_amount = buy_order['buy_amount']
                            p_l_a = (current_price - buy_price)
                            profit = (buy_amount * current_price) - (buy_price * buy_amount)
                            if profit < 0:
                                continue
                            profit_list.append(profit)
                            print('%s - Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                            update_order(timestamp, current_price, p_l_a, profit, last_timestamp)
            buy_orders = search_order(symbol)
            for buy_order in buy_orders:
                if buy_order['status'] == 'closed':
                    continue
                timestamp = buy_order['buy_time']
                buy_price = buy_order['buy_price']
                buy_amount = buy_order['buy_amount']
                p_l_a = (current_price - buy_price)
                profit = (buy_amount * current_price) - (buy_price * buy_amount)
                if int(profit) < stoploss_percent:
                    profit_list.append(profit)
                    print('%s - STOPLOSS Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                    update_order(timestamp, current_price, p_l_a, profit, last_timestamp)
                if int(profit) > take_profit:
                    profit_list.append(profit)
                    print('%s - TAKEPROFIT Selling %s %s at %s. Profit: %s' % (note_timestamp, buy_amount, symbol, current_price, profit))
                    update_order(timestamp, current_price, p_l_a, profit, last_timestamp)
            if last_profit != sum(profit_list):
                print("Profit: %s" % sum(profit_list))
                last_profit = sum(profit_list)
        since_start = last_timestamp / 1000
        if last_timestamp == last_last_timestamp:
            print("Backtesting finished")
            sys.exit(0)
        else:
            last_last_timestamp = last_timestamp
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
    except ccxt.ExchangeError as e:
        print(type(e).__name__, str(e))
        time.sleep(10)
    except ValueError as e:
        since_start = (since_start * (60 * 300)) / 1000
    #except Exception as e:
    #    # panic and halt the execution in case of any other error
    #    print(type(e).__name__, str(e))
    #    sys.exit()


if __name__ == "__main__":
    main()
